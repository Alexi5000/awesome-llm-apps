import base64
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from PIL import Image
from streamlit.testing.v1 import AppTest
from together import Together

APP = Path(__file__).resolve().parents[1] / 'ai_data_visualisation_agent.py'
spec = importlib.util.spec_from_file_location('visualisation', APP)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class RuntimeTests(unittest.TestCase):
    def test_initial_ui_without_credentials(self):
        page = AppTest.from_file(str(APP)).run(timeout=20)
        self.assertFalse(page.exception)
        self.assertEqual(page.title[0].value, '📊 AI Data Visualization Agent')
        self.assertEqual(len(page.text_input), 2)

    def test_real_together_response_drives_sandbox(self):
        captured = []
        def respond(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200, json={
                'id': 'offline-completion', 'object': 'chat.completion',
                'created': 1, 'model': 'offline-model',
                'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {
                    'role': 'assistant', 'content': '```python\nprint(42)\n```'}}],
            })
        result = SimpleNamespace(text='42')
        sandbox = unittest.mock.Mock()
        sandbox.run_code.return_value = SimpleNamespace(error=None, results=[result])
        with Together(api_key='offline-test-key', http_client=httpx.Client(
            transport=httpx.MockTransport(respond)
        )) as client:
            with patch.object(app, 'Together', return_value=client), patch.object(
                app.st, 'session_state', SimpleNamespace(
                    together_api_key='offline-test-key', model_name='offline-model'
                )
            ):
                results, message = app.chat_with_llm(sandbox, 'summarize', './data.csv')
        self.assertEqual(results, [result])
        self.assertIn('print(42)', message)
        sandbox.run_code.assert_called_once_with('print(42)')
        self.assertEqual(captured[0]['model'], 'offline-model')
        self.assertIn('./data.csv', captured[0]['messages'][0]['content'])

    def test_png_base64_result_decodes_with_patched_pillow(self):
        png = io.BytesIO()
        Image.new('RGB', (3, 2), (20, 30, 40)).save(png, format='PNG')
        payload = base64.b64encode(png.getvalue())
        with Image.open(io.BytesIO(base64.b64decode(payload))) as image:
            image.load()
            self.assertEqual(image.size, (3, 2))
            self.assertEqual(image.getpixel((0, 0)), (20, 30, 40))

    def test_sandbox_failure_is_not_success(self):
        sandbox = unittest.mock.Mock()
        sandbox.run_code.return_value = SimpleNamespace(error='offline failure', results=[])
        self.assertIsNone(app.code_interpret(sandbox, 'bad code'))

    def test_dataset_upload_retains_file_and_path(self):
        sandbox = unittest.mock.Mock()
        upload = io.BytesIO(b'a\n1\n')
        upload.name = 'sample.csv'
        self.assertEqual(app.upload_dataset(sandbox, upload), './sample.csv')
        sandbox.files.write.assert_called_once_with('./sample.csv', upload)


if __name__ == '__main__':
    unittest.main()
