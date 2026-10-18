const assert = require('node:assert/strict');
const { app } = require('electron');
const axios = require('axios');
app.setAppPath(require('node:path').resolve(__dirname, '..'));

axios.post = async (url) => {
  assert.equal(url, 'http://localhost:11434/api/generate');
  return { data: { response: 'offline smoke response' } };
};

const timeout = setTimeout(() => {
  console.error('Electron runtime smoke test timed out');
  app.exit(1);
}, 30000);

app.on('browser-window-created', (_event, window) => {
  window.webContents.once('did-finish-load', async () => {
    try {
      const result = await window.webContents.executeJavaScript(`
        (async () => ({
          title: document.title,
          input: Boolean(document.getElementById('chatInput')),
          response: await ipcRenderer.invoke('send-to-llm', 'offline test'),
          maximized: await ipcRenderer.invoke('window-is-maximized'),
          paths: await ipcRenderer.invoke('generate-thinking-paths', 'write code')
        }))()
      `);
      assert.equal(result.title, 'Guided LLM Chat');
      assert.equal(result.input, true);
      assert.deepEqual(result.response, { success: true, response: 'offline smoke response' });
      assert.equal(typeof result.maximized, 'boolean');
      assert.equal(result.paths.success, true);
      assert.equal(result.paths.paths.length, 4);
      clearTimeout(timeout);
      console.log('PASS: Electron window, renderer, IPC, offline response and fallback paths');
      app.exit(0);
    } catch (error) {
      clearTimeout(timeout);
      console.error(error);
      app.exit(1);
    }
  });
});

require('../main.js');
