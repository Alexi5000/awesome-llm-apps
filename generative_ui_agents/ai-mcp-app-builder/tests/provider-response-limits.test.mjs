import assert from 'node:assert/strict';
import { readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import test from 'node:test';

const store = resolve('node_modules/.pnpm');
const entries = readdirSync(store).filter(name => name.startsWith('@ai-sdk+provider-utils@2.2.8'));
assert.ok(entries.length > 0);
for (const entry of entries) {
const packagePath = resolve(store, entry, 'node_modules/@ai-sdk/provider-utils');
const require = createRequire(resolve(packagePath, 'package.json'));
const { z } = require('zod/v3');
const maxBytes = 2 * 1024 * 1024 * 1024;

for (const format of ['index.js', 'index.mjs']) {
  const sdk = await import(pathToFileURL(resolve(packagePath, 'dist', format)));
  const handlers = {
    json: sdk.createJsonResponseHandler(z.object({ message: z.string() })),
    jsonError: sdk.createJsonErrorResponseHandler({
      errorSchema: z.object({ message: z.string() }),
      errorToMessage: value => value.message,
    }),
    statusError: sdk.createStatusCodeErrorResponseHandler(),
  };
  const invoke = (handler, response) => handler({ response, url: 'https://provider.invalid', requestBodyValues: {} });

  test(`${format}: preserves synchronous parsing and schema constraints`, () => {
    const parsed = sdk.safeParseJSON({ text: '{"message":"ok"}', schema: z.object({ message: z.string() }) });
    assert.equal(parsed.success, true);
    assert.equal(parsed.value.message, 'ok');
    assert.equal(sdk.safeParseJSON({ text: '{"message":7}', schema: z.object({ message: z.string() }) }).success, false);
  });

  test(`${format}: normal response handlers retain values and provider errors`, async () => {
    assert.deepEqual((await invoke(handlers.json, new Response('{"message":"ok"}'))).value, { message: 'ok' });
    const error = await invoke(handlers.jsonError, new Response('{"message":"denied"}', { status: 403 }));
    assert.equal(error.value.message, 'denied');
    assert.equal(error.value.statusCode, 403);
    const status = await invoke(handlers.statusError, new Response('upstream unavailable', { status: 503 }));
    assert.equal(status.value.responseBody, 'upstream unavailable');
    const empty = await invoke(handlers.jsonError, new Response(null, { status: 500, statusText: 'Failed' }));
    assert.equal(empty.value.message, 'Failed');
    await assert.rejects(invoke(handlers.json, new Response('invalid json')));
  });

  for (const [name, handler] of Object.entries(handlers)) {
    for (const mode of ['declared', 'missing', 'understated']) {
      test(`${format}: ${name} cancels oversized ${mode} bodies`, async () => {
        let cancelled = false;
        let pulls = 0;
        const chunk = new Uint8Array(1024 * 1024);
        const body = new ReadableStream({
          pull(controller) {
            pulls += 1;
            controller.enqueue(chunk);
            if (pulls > 2050) controller.close();
          },
          cancel() { cancelled = true; },
        });
        const headers = mode === 'missing' ? {} : { 'content-length': String(mode === 'declared' ? maxBytes + 1 : 1) };
        const response = new Response(body, { headers });
        await assert.rejects(invoke(handler, response), /exceeded maximum size/);
        assert.equal(cancelled, true);
        assert.equal(body.locked, false);
        assert.ok(pulls <= (mode === 'declared' ? 1 : 2050));
      });
    }
  }
}
}
