import { test, expect } from "bun:test";
import { mkdtemp, mkdir, writeFile, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { gzipSync } from "node:zlib";
import * as tar from "tar";
import { mergeE2bWorkspaceIntoBaseKit } from "../lib/workspace/merge-download-kit";

function archive(entries: Array<{ path: string; type?: "File" | "SymbolicLink"; linkpath?: string; body?: string }>) {
  const chunks: Buffer[] = [];
  for (const entry of entries) {
    const body = Buffer.from(entry.body ?? "");
    const header = new tar.Header({ ...entry, type: entry.type ?? "File", size: body.length, mode: 0o600 });
    header.encode();
    chunks.push(header.block!, body, Buffer.alloc((512 - body.length % 512) % 512));
  }
  return gzipSync(Buffer.concat([...chunks, Buffer.alloc(1024)]));
}

test("download merger preserves ordinary source and contains traversal and symlink writes", async () => {
  const root = await mkdtemp(join(tmpdir(), "kit-boundary-"));
  try {
    const base = join(root, "base");
    await mkdir(join(base, "mcp-apps-starter/apps/mcp-use-server"), { recursive: true });
    await writeFile(join(base, "mcp-apps-starter/package.json"), "{}");
    const baseTar = join(root, "base.tar.gz");
    await tar.c({ gzip: true, file: baseTar, cwd: base }, ["mcp-apps-starter"]);
    const outside = join(root, "private.txt");
    await writeFile(outside, "original");
    for (const malicious of [
      { path: "../../private.txt", body: "overwritten" },
      { path: "workspace/link", type: "SymbolicLink" as const, linkpath: root },
      { path: "workspace/link", type: "SymbolicLink" as const, linkpath: "../../" },
    ]) {
      await expect(mergeE2bWorkspaceIntoBaseKit(archive([
        { path: "workspace/index.ts", body: "export const safe = true;" }, malicious,
      ]), baseTar)).rejects.toThrow("escapes its root");
    }
    const stream = await mergeE2bWorkspaceIntoBaseKit(archive([
      { path: "workspace/index.ts", body: "export const safe = true;" },
    ]), baseTar);
    const chunks = [];
    for await (const chunk of stream) chunks.push(Buffer.from(chunk));
    expect(await readFile(outside, "utf8")).toBe("original");
    const output = join(root, "output.tar.gz");
    await writeFile(output, Buffer.concat(chunks));
    const names: string[] = [];
    await tar.t({ file: output, onReadEntry: entry => names.push(entry.path) });
    expect(names).toContain("mcp-apps-starter/apps/mcp-use-server/index.ts");
    expect(names.some(name => name.includes(".."))).toBe(false);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
