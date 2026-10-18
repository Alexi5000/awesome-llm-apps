from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lxml_html_clean import Cleaner
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / 'startup_trends_agent.py'


class RuntimeTests(unittest.TestCase):
    def test_initial_ui_and_missing_key(self):
        page = AppTest.from_file(str(APP)).run(timeout=30)
        self.assertFalse(page.exception)
        page.button[0].click().run()
        self.assertFalse(page.exception)
        self.assertIn('API key', page.warning[0].value)

    def test_real_agents_and_tools_construct_and_pass_results(self):
        page = AppTest.from_file(str(APP)).run(timeout=30)
        page.text_input[0].set_value('robotics')
        page.sidebar.text_input[0].set_value('offline-key')
        with patch('agno.agent.Agent.run', side_effect=[
            SimpleNamespace(content='articles'), SimpleNamespace(content='summaries'),
            SimpleNamespace(content='final analysis'),
        ]) as run:
            page.button[0].click().run(timeout=30)
        self.assertFalse(page.exception)
        self.assertFalse(page.error)
        self.assertEqual(run.call_count, 3)
        self.assertIn('robotics', run.call_args_list[0].args[0])
        self.assertIn('articles', run.call_args_list[1].args[0])
        self.assertIn('summaries', run.call_args_list[2].args[0])
        self.assertIn('final analysis', [item.value for item in page.markdown])

    def test_cleaner_removes_executable_markup(self):
        cleaned = Cleaner().clean_html('<div><script>alert(1)</script><p onclick="evil()">news</p></div>')
        self.assertNotIn('<script', cleaned)
        self.assertNotIn('onclick', cleaned)
        self.assertIn('news', cleaned)


if __name__ == '__main__':
    unittest.main()
