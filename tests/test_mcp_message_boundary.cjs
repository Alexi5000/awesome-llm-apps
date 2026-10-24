const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

for (const name of ['flights', 'hotels', 'trading', 'kanban']) {
  test(`${name} accepts only the embedding parent's messages`, () => {
    const html = fs.readFileSync(path.join(__dirname, '../generative_ui_agents/mcp-apps-generative-ui-showcase/mcp-server/apps', `${name}-app.html`), 'utf8');
    const start = html.indexOf('const mcpApp = (() => {');
    const end = html.indexOf('})();', start) + 5;
    assert.ok(start >= 0 && end > start);
    let listener;
    const parent = { postMessage() {} };
    const window = { parent, addEventListener(name, callback) { listener = callback; } };
    const context = { window, document: { referrer: 'https://host.example/app' }, URL };
    vm.runInNewContext(html.slice(start, end) + '\nglobalThis.api = mcpApp;', context);
    let calls = 0;
    context.api.onNotification('test/update', () => calls++);
    const data = { jsonrpc: '2.0', method: 'test/update', params: {} };
    listener({ source: {}, origin: 'https://host.example', data });
    listener({ source: parent, origin: 'https://evil.example', data });
    assert.equal(calls, 0);
    listener({ source: parent, origin: 'https://host.example', data });
    assert.equal(calls, 1);
    listener({ source: parent, origin: 'https://host.example', data: { method: '__proto__' } });
    listener({ source: parent, origin: 'https://host.example', data: { method: 'constructor' } });
  });
}
