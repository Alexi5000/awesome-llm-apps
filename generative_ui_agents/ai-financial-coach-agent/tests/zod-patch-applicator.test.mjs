import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, copyFileSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import test from 'node:test';

const app = resolve('.');
const manifest = JSON.parse(readFileSync('patches/zod-collection-limits.json', 'utf8'));
const lock = JSON.parse(readFileSync('package-lock.json', 'utf8'));
const source = Object.keys(lock.packages).find(name => name.endsWith('node_modules/zod') && lock.packages[name].version === '3.25.76');
assert.ok(source);

function fixture() {
  const root = mkdtempSync(join(tmpdir(), 'zod-patch-test-'));
  mkdirSync(join(root, 'scripts'));
  mkdirSync(join(root, 'patches'));
  copyFileSync(join(app, 'scripts/patch-zod.cjs'), join(root, 'scripts/patch-zod.cjs'));
  copyFileSync(join(app, 'patches/zod-collection-limits.json'), join(root, 'patches/zod-collection-limits.json'));
  const paths = ['node_modules/zod', 'node_modules/consumer/node_modules/zod'];
  const packages = {};
  for (const directory of paths) {
    const target = join(root, directory);
    mkdirSync(target, { recursive: true });
    copyFileSync(join(app, source, 'package.json'), join(target, 'package.json'));
    packages[directory] = lock.packages[source];
    for (const [relative, patch] of Object.entries(manifest.versions['3.25.76'].files)) {
      let content = readFileSync(join(app, source, relative), 'utf8');
      for (const edit of [...patch.edits].reverse()) {
        if (content.includes(edit.to)) content = content.replace(edit.to, edit.from);
      }
      mkdirSync(join(target, relative, '..'), { recursive: true });
      writeFileSync(join(target, relative), content);
    }
  }
  writeFileSync(join(root, 'package-lock.json'), JSON.stringify({ packages }));
  return { root, paths };
}

function run(root) {
  return spawnSync(process.execPath, [join(root, 'scripts/patch-zod.cjs')], { encoding: 'utf8' });
}

test('applicator verifies all files before changing any installed file', () => {
  const { root, paths } = fixture();
  try {
    const first = join(root, paths[0], 'v3/types.js');
    const before = readFileSync(first);
    writeFileSync(join(root, paths[1], 'v3/types.js'), 'unreviewed content');
    assert.notEqual(run(root).status, 0);
    assert.deepEqual(readFileSync(first), before);
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test('applicator is idempotent and rejects linked targets', () => {
  const { root, paths } = fixture();
  try {
    execFileSync(process.execPath, [join(root, 'scripts/patch-zod.cjs')]);
    const second = run(root);
    assert.equal(second.status, 0, second.stderr);
    assert.match(second.stdout, /patched 0 files/);
    const target = join(root, paths[1], 'v3/types.js');
    const outside = join(root, 'outside.js');
    writeFileSync(outside, readFileSync(target));
    rmSync(target);
    symlinkSync(outside, target);
    assert.notEqual(run(root).status, 0);
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test('applicator rejects unreviewed versions and modified patch output', () => {
  const { root, paths } = fixture();
  try {
    const packageFile = join(root, paths[0], 'package.json');
    const original = readFileSync(packageFile, 'utf8');
    writeFileSync(packageFile, original.replace('3.25.76', '3.25.77'));
    assert.notEqual(run(root).status, 0);
    writeFileSync(packageFile, original);
    const patchFile = join(root, 'patches/zod-collection-limits.json');
    const broken = JSON.parse(readFileSync(patchFile, 'utf8'));
    broken.versions['3.25.76'].files['v3/types.js'].edits[0].to += '\n';
    writeFileSync(patchFile, JSON.stringify(broken));
    assert.notEqual(run(root).status, 0);
  } finally { rmSync(root, { recursive: true, force: true }); }
});
