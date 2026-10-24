const test = require('node:test');
const assert = require('node:assert/strict');
const server = require('./server.js');

test('serves the editor without exposing server source or workspace files', async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    assert.equal((await fetch(base + '/')).status, 200);
    assert.equal((await fetch(base + '/index.html')).status, 200);
    assert.equal((await fetch(base + '/%2e%2e%2fsecret')).status, 403);
    for (const path of ['/server.js', '/package.json', '/.env']) {
      assert.equal((await fetch(base + path)).status, 404, path);
    }
  } finally {
    await new Promise(resolve => server.close(resolve));
  }
});
