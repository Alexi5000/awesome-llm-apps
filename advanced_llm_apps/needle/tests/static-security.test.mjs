import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, symlink, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn } from "node:child_process";
import { once } from "node:events";

test("production serves a startup snapshot and never follows request-time paths", async () => {
  const root = await mkdtemp(join(tmpdir(), "needle-static-"));
  await mkdir(join(root, "dist"));
  await writeFile(join(root, "dist/index.html"), "safe editor");
  await writeFile(join(root, "secret.txt"), "private token");
  await symlink(join(root, "secret.txt"), join(root, "dist/leak.txt"));
  const port = 20000 + Math.floor(Math.random() * 20000);
  const child = spawn(process.execPath, [new URL("../server/dev.mjs", import.meta.url).pathname, "--production"], {
    cwd: root, env: { ...process.env, PORT: String(port) }, stdio: ["ignore", "pipe", "pipe"],
  });
  try {
    await Promise.race([once(child.stdout, "data"), once(child, "exit").then(() => { throw new Error("server failed"); })]);
    const base = `http://127.0.0.1:${port}`;
    assert.equal(await (await fetch(base)).text(), "safe editor");
    assert.equal((await fetch(base + "/leak.txt")).status, 404);
    await rm(join(root, "dist/index.html"));
    await symlink(join(root, "secret.txt"), join(root, "dist/index.html"));
    assert.equal(await (await fetch(base + "/index.html")).text(), "safe editor");
    assert.equal((await fetch(base + "/%2e%2e%2fsecret.txt")).status, 403);
  } finally {
    child.kill();
    await once(child, "exit");
    await rm(root, { recursive: true, force: true });
  }
});
