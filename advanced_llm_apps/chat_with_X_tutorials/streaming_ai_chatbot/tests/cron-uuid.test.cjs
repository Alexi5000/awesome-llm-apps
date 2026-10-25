const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const { once } = require('node:events');
const { mkdtempSync, writeFileSync, rmSync } = require('node:fs');
const { join } = require('node:path');
const test = require('node:test');

const coreRequire = createRequire(require.resolve('@motiadev/core'));
const cronPath = coreRequire.resolve('node-cron');
const cron = coreRequire('node-cron');
const uuid = createRequire(cronPath)('uuid');

test('scheduler resolves UUID with bounded output-buffer writes', () => {
  for (const generate of [uuid.v3, uuid.v5]) {
    const buffer = Buffer.alloc(16, 0xaa);
    assert.throws(() => generate('test', uuid.v4(), buffer, -1), RangeError);
    assert.deepEqual(buffer, Buffer.alloc(16, 0xaa));
    assert.throws(() => generate('test', uuid.v4(), Buffer.alloc(15)), RangeError);
  }
});

test('foreground scheduler retains generated names, execution, and cancellation', async t => {
  const task = cron.schedule('* * * * * *', () => 'executed', { scheduled: false });
  t.after(() => { task.stop(); cron.getTasks().delete(task.options.name); });
  assert.equal(uuid.validate(task.options.name), true);
  assert.equal(uuid.version(task.options.name), 4);
  assert.equal(cron.getTasks().get(task.options.name), task);
  const completed = once(task, 'task-done', { signal: AbortSignal.timeout(5000) });
  task.start();
  assert.deepEqual(await completed, ['executed']);
  task.stop();
  let laterExecutions = 0;
  task.on('task-done', () => laterExecutions++);
  await new Promise(resolve => setTimeout(resolve, 1200));
  assert.equal(laterExecutions, 0);
});

test('explicit task names are preserved', t => {
  const task = cron.schedule('* * * * * *', () => {}, { scheduled: false, name: 'retained-name' });
  t.after(() => { task.stop(); cron.getTasks().delete(task.options.name); });
  assert.equal(task.options.name, 'retained-name');
  assert.equal(cron.getTasks().get('retained-name'), task);
});

test('background scheduler executes and stops a real child process', async t => {
  const directory = mkdtempSync(join(__dirname, '.cron-fixture-'));
  const fixture = join(directory, 'job.cjs');
  writeFileSync(fixture, "exports.task = () => 'background-executed';\n");
  const task = cron.schedule('* * * * * *', fixture, { scheduled: false });
  t.after(() => { task.stop(); cron.getTasks().delete(task.options.name); rmSync(directory, { recursive: true, force: true }); });
  assert.equal(uuid.validate(task.options.name), true);
  assert.equal(uuid.version(task.options.name), 4);
  const completed = once(task, 'task-done', { signal: AbortSignal.timeout(10000) });
  task.start();
  assert.deepEqual(await completed, ['background-executed']);
  const exited = once(task.forkProcess, 'exit', { signal: AbortSignal.timeout(5000) });
  task.stop();
  await exited;
  assert.equal(task.isRunning(), false);
});
