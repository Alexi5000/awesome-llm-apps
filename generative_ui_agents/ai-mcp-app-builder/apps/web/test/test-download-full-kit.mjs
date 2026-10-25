import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import * as tar from "tar";
import { mergeE2bWorkspaceIntoBaseKit } from "../lib/workspace/merge-download-kit.ts";

async function fixture(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "kit-test-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  await fs.mkdir(path.join(root, "base/mcp-apps-starter/apps/mcp-use-server"), { recursive: true });
  await fs.writeFile(path.join(root, "base/mcp-apps-starter/apps/mcp-use-server/old.txt"), "old");
  await fs.mkdir(path.join(root, "input/workspace"), { recursive: true });
  await fs.writeFile(path.join(root, "input/workspace/new.txt"), "sandbox content");
  const base = path.join(root, "base.tgz");
  await tar.c({ cwd: path.join(root, "base"), file: base, gzip: true }, ["mcp-apps-starter"]);
  return { root, base };
}

test("merges the sandbox into the full kit", async (t) => {
  const { root, base } = await fixture(t);
  const archive = path.join(root, "workspace.tgz");
  await tar.c({ cwd: path.join(root, "input"), file: archive, gzip: true }, ["workspace"]);
  const stream = await mergeE2bWorkspaceIntoBaseKit(await fs.readFile(archive), base);
  const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  const merged = path.join(root, "merged.tgz");
  await fs.writeFile(merged, Buffer.concat(chunks));
  const output = path.join(root, "output");
  await fs.mkdir(output);
  await tar.x({ cwd: output, file: merged });
  assert.equal(await fs.readFile(path.join(output, "mcp-apps-starter/apps/mcp-use-server/new.txt"), "utf8"), "sandbox content");
  await assert.rejects(fs.access(path.join(output, "mcp-apps-starter/apps/mcp-use-server/old.txt")));
});

test("rejects a parent-relative archive entry", async (t) => {
  const { root, base } = await fixture(t);
  await fs.writeFile(path.join(root, "outside.txt"), "must remain outside");
  const archive = path.join(root, "escape.tgz");
  await tar.c({ cwd: path.join(root, "input"), file: archive, gzip: true, preservePaths: true }, ["../outside.txt"]);
  await assert.rejects(mergeE2bWorkspaceIntoBaseKit(await fs.readFile(archive), base), /escapes its root/);
  assert.equal(await fs.readFile(path.join(root, "outside.txt"), "utf8"), "must remain outside");
});

test("rejects a symlink outside the workspace root", async (t) => {
  const { root, base } = await fixture(t);
  await fs.symlink("../../outside.txt", path.join(root, "input/workspace/link"));
  const archive = path.join(root, "links.tgz");
  await tar.c({ cwd: path.join(root, "input"), file: archive, gzip: true }, ["workspace"]);
  await assert.rejects(mergeE2bWorkspaceIntoBaseKit(await fs.readFile(archive), base), /escapes its root/);
});
