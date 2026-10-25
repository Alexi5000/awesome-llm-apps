const assert = require('node:assert/strict');
const { createServer } = require('node:http');
const { createRequire } = require('node:module');
const { once } = require('node:events');
const test = require('node:test');

require('ts-node').register({ transpileOnly: true, compilerOptions: { module: 'CommonJS' } });
const chat = require('../steps/chat-api.step.ts');
const response = require('../steps/ai-response.step.ts');
const { conversationSchema } = require('../steps/conversation.stream.ts');
const logger = { info() {}, error() {} };

function context() {
  const writes = [];
  return {
    writes,
    logger,
    streams: { conversation: { async set(group, id, value) {
      writes.push({ group, id, value: { ...value } });
      return value;
    } } },
  };
}

test('Motia retains required fields and size constraints in JSON Schema conversion', () => {
  const coreRequire = createRequire(require.resolve('@motiadev/core'));
  const { z } = coreRequire('zod');
  const { zodToJsonSchema } = coreRequire('zod-to-json-schema');
  const converted = zodToJsonSchema(z.object({ items: z.array(z.string()).max(2) }));
  assert.deepEqual(converted.required, ['items']);
  assert.equal(converted.properties.items.maxItems, 2);
  assert.equal(converted.properties.items.items.type, 'string');
  assert.equal(chat.config.bodySchema.safeParse({ message: '' }).success, false);
  assert.equal(chat.config.bodySchema.safeParse({ message: 'hello' }).success, true);
  assert.equal(response.config.input.safeParse({ message: 'hello' }).success, false);
});

test('chat handler keeps conversation identity, message state and response-event correlation', async () => {
  const ctx = context();
  const events = [];
  const result = await chat.handler({ body: { message: 'hello', conversationId: 'test-conversation' } }, {
    ...ctx, async emit(event) { events.push(event); },
  });
  assert.equal(result.status, 200);
  assert.equal(conversationSchema.safeParse(result.body).success, true);
  assert.deepEqual(ctx.writes.map(write => [write.group, write.value.from, write.value.status]), [
    ['test-conversation', 'user', 'completed'], ['test-conversation', 'assistant', 'created'],
  ]);
  assert.notEqual(ctx.writes[0].id, ctx.writes[1].id);
  assert.equal(events.length, 1);
  assert.deepEqual(events[0], { topic: 'chat-message', data: {
    message: 'hello', conversationId: 'test-conversation', assistantMessageId: ctx.writes[1].id,
  } });
});

for (const failure of [false, true]) {
  test(`real OpenAI client and handler preserve ${failure ? 'provider error recovery' : 'streaming and completed state'} against a local fake provider`, async t => {
    const requests = [];
    const server = createServer(async (req, res) => {
      let body = '';
      for await (const chunk of req) body += chunk;
      requests.push({ path: req.url, body: JSON.parse(body) });
      if (failure) {
        res.writeHead(401, { 'content-type': 'application/json' });
        res.end(JSON.stringify({ error: { message: 'test denial', type: 'authentication_error' } }));
        return;
      }
      res.writeHead(200, { 'content-type': 'text/event-stream' });
      for (const content of ['Hello', ' world']) {
        res.write(`data: ${JSON.stringify({ choices: [{ index: 0, delta: { content } }] })}\n\n`);
      }
      res.end('data: [DONE]\n\n');
    });
    server.listen(0, '127.0.0.1');
    await once(server, 'listening');
    const previousKey = process.env.OPENAI_API_KEY;
    const previousBase = process.env.OPENAI_BASE_URL;
    process.env.OPENAI_API_KEY = 'local-test-only-not-a-credential';
    process.env.OPENAI_BASE_URL = `http://127.0.0.1:${server.address().port}/v1`;
    t.after(async () => {
      if (previousKey === undefined) delete process.env.OPENAI_API_KEY;
      else process.env.OPENAI_API_KEY = previousKey;
      if (previousBase === undefined) delete process.env.OPENAI_BASE_URL;
      else process.env.OPENAI_BASE_URL = previousBase;
      await new Promise(resolve => server.close(resolve));
    });
    const ctx = context();
    await response.handler({ message: 'hello', conversationId: 'test-conversation', assistantMessageId: 'test-assistant' }, ctx);
    assert.equal(requests.length, 1);
    assert.equal(requests[0].path, '/v1/chat/completions');
    assert.equal(requests[0].body.stream, true);
    assert.equal(requests[0].body.messages.at(-1).content, 'hello');
    assert.ok(ctx.writes.every(write => write.group === 'test-conversation' && write.id === 'test-assistant'));
    assert.ok(ctx.writes.every(write => conversationSchema.safeParse(write.value).success));
    assert.equal(ctx.writes.at(-1).value.status, 'completed');
    if (failure) {
      assert.equal(ctx.writes.at(-1).value.message, 'Sorry, I encountered an error. Please try again.');
    } else {
      assert.deepEqual(ctx.writes.map(write => write.value.message), ['', 'Hello', 'Hello world', 'Hello world']);
      assert.deepEqual(ctx.writes.map(write => write.value.status), ['streaming', 'streaming', 'streaming', 'completed']);
    }
  });
}
