import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ['GRADIO_ANALYTICS_ENABLED'] = 'False'
from fastapi.testclient import TestClient
from gradio.routes import App

SOURCE = Path(__file__).resolve().parents[1] / 'ai_aqi_analysis_agent_gradio.py'
spec = importlib.util.spec_from_file_location('aqi_app', SOURCE)
app = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = app
spec.loader.exec_module(app)


class RuntimeTests(unittest.TestCase):
    def test_gradio_http_configuration_and_inputs(self):
        demo = app.create_demo()
        with TestClient(App.create_app(demo)) as client:
            response = client.get('/config')
            self.assertEqual(response.status_code, 200)
            config = response.json()
            passwords = [c for c in config['components'] if c.get('props', {}).get('type') == 'password']
            self.assertEqual(len(passwords), 2)
            actions = [d for d in config['dependencies'] if d.get('api_name') == 'analyze_conditions']
            self.assertEqual(len(actions), 1)
            self.assertEqual(len(actions[0]['inputs']), 7)
            self.assertEqual(len(actions[0]['outputs']), 4)
        demo.close()

    def test_analysis_preserves_data_and_provider_prompt(self):
        data = dict(aqi=42, temperature=20, humidity=50, wind_speed=4, pm25=5, pm10=8, co=2)
        with patch.object(app.FirecrawlApp, 'extract', return_value={
            'success': True, 'status': 'completed', 'expiresAt': '2099-01-01', 'data': data,
        }) as extract, patch.object(app.Agent, 'run', return_value=SimpleNamespace(content='offline result')) as run:
            output = app.analyze_conditions('New York', '', 'United States', '', 'walk', 'offline-key', 'offline-key')
        self.assertEqual(json.loads(output[0])['Air Quality Index (AQI)'], 42)
        self.assertEqual(output[1], 'offline result')
        self.assertIn('42.0', run.call_args.args[0])
        self.assertEqual(extract.call_args.kwargs['urls'], ['https://www.aqi.in/dashboard/united-states/new-york/*'])

    def test_failed_fetch_never_fabricates_clean_air_or_requests_advice(self):
        failures = [RuntimeError('offline timeout'), {
            'success': False, 'status': 'failed', 'expiresAt': '2099-01-01', 'data': {},
        }, {'success': True, 'data': {}}]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                behavior = {'side_effect': failure} if isinstance(failure, Exception) else {'return_value': failure}
                with patch.object(app.FirecrawlApp, 'extract', **behavior), patch.object(app.Agent, 'run') as run:
                    output = app.analyze_conditions('city', '', 'country', '', 'walk', 'offline-key', 'offline-key')
                run.assert_not_called()
                self.assertEqual(output[0], '')
                self.assertEqual(output[1], 'Analysis failed')
                self.assertIn('Error fetching AQI data', output[2])

    def test_provider_error_surfaces_as_failed_analysis(self):
        with patch.object(app.Agent, 'run', side_effect=RuntimeError('offline failure')), patch.object(
            app.AQIAnalyzer, 'fetch_aqi_data', return_value=(dict(aqi=42, temperature=20, humidity=50, wind_speed=4, pm25=5, pm10=8, co=2), 'status')
        ):
            output = app.analyze_conditions('city', '', 'country', '', 'walk', 'offline-key', 'offline-key')
        self.assertEqual(output[1], 'Analysis failed')
        self.assertIn('offline failure', output[2])


if __name__ == '__main__':
    unittest.main()
