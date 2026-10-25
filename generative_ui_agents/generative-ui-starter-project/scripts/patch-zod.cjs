const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const app = path.resolve(__dirname, '..');
const lock = JSON.parse(fs.readFileSync(path.join(app, 'package-lock.json'), 'utf8'));
const patches = JSON.parse(fs.readFileSync(path.join(app, 'patches/zod-collection-limits.json'), 'utf8'));
const hash = value => crypto.createHash('sha256').update(value).digest('hex');

function regularFile(filename) {
  const relative = path.relative(app, filename);
  if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error(`Outside app: ${filename}`);
  let current = app;
  for (const part of relative.split(path.sep)) {
    current = path.join(current, part);
    if (fs.lstatSync(current).isSymbolicLink()) throw new Error(`Linked patch path: ${current}`);
  }
  const stat = fs.lstatSync(filename);
  if (!stat.isFile() || stat.nlink !== 1) throw new Error(`Not an unlinked regular file: ${filename}`);
  return stat;
}

const packages = Object.entries(lock.packages).filter(([name]) => name.endsWith('node_modules/zod'));
if (!packages.length) throw new Error('No locked Zod dependencies found');
const writes = [];
for (const [directory, metadata] of packages) {
  const root = path.resolve(app, directory);
  const packageFile = path.join(root, 'package.json');
  regularFile(packageFile);
  const installed = JSON.parse(fs.readFileSync(packageFile, 'utf8'));
  if (installed.name !== 'zod' || installed.version !== metadata.version) throw new Error(`Zod lock mismatch: ${directory}`);
  const patch = patches.versions[installed.version];
  if (!patch || metadata.integrity !== patch.integrity) throw new Error(`Unreviewed Zod artifact: ${directory}`);
  for (const [relative, change] of Object.entries(patch.files)) {
    const filename = path.join(root, relative);
    const stat = regularFile(filename);
    const before = fs.readFileSync(filename, 'utf8');
    if (hash(before) === change.after) continue;
    if (hash(before) !== change.before) throw new Error(`Unreviewed Zod file: ${filename}`);
    let after = before;
    for (const edit of change.edits) {
      if (after.split(edit.from).length !== 2) throw new Error(`Ambiguous Zod patch: ${filename}`);
      after = after.replace(edit.from, edit.to);
    }
    if (hash(after) !== change.after) throw new Error(`Invalid Zod patch output: ${filename}`);
    writes.push({ filename, before, after, mode: stat.mode & 0o777 });
  }
}

const temporary = [];
try {
  for (const write of writes) {
    const filename = `${write.filename}.${crypto.randomUUID()}.tmp`;
    fs.writeFileSync(filename, write.after, { flag: 'wx', mode: write.mode });
    temporary.push({ ...write, temporary: filename });
  }
  for (const write of temporary) {
    regularFile(write.filename);
    if (fs.readFileSync(write.filename, 'utf8') !== write.before) throw new Error(`Zod file changed during patch: ${write.filename}`);
  }
  for (const write of temporary) fs.renameSync(write.temporary, write.filename);
} finally {
  for (const write of temporary) fs.rmSync(write.temporary, { force: true });
}
console.log(`Verified ${packages.length} Zod installations; patched ${writes.length} files`);
