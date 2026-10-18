import asyncio
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["BROWSER_USE_DISABLE_CLOUD"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai_meme_generator_agent as app
from browser_use import Agent
from browser_use.agent.views import AgentHistoryList, AgentHistory, ActionResult
from streamlit.testing.v1 import AppTest


class RuntimeTests(unittest.TestCase):
    def test_all_providers_build_real_agents(self):
        async def exercise():
            agents = []
            real_agent = app.Agent
            def construct(**kwargs):
                agent = real_agent(**kwargs)
                agents.append(agent)
                return agent
            history = AgentHistoryList(history=[])
            with patch.object(app, "Agent", side_effect=construct), patch.object(Agent, "run", new=AsyncMock(return_value=history)):
                for provider in ("Claude", "Deepseek", "OpenAI"):
                    self.assertIsNone(await app.generate_meme("deadline panic", provider, "offline-test-key"))
            self.assertEqual([a.llm.model for a in agents], ["claude-3-5-sonnet-20241022", "deepseek-chat", "gpt-4o"])
            self.assertFalse(agents[1].settings.use_vision)
            self.assertEqual(agents[1].llm.base_url, "https://api.deepseek.com/v1")
            self.assertTrue(all("deadline panic" in a.task for a in agents))
        asyncio.run(exercise())

    def test_result_and_failure_handling(self):
        async def exercise():
            history = AgentHistoryList(history=[])
            with patch.object(AgentHistoryList, "final_result", return_value="Generated https://imgflip.com/i/abc123"), patch.object(Agent, "run", new=AsyncMock(return_value=history)):
                self.assertEqual(await app.generate_meme("test", "OpenAI", "offline-test-key"), "https://i.imgflip.com/abc123.jpg")
            with patch.object(Agent, "run", new=AsyncMock(side_effect=RuntimeError("provider offline"))):
                with self.assertRaisesRegex(RuntimeError, "provider offline"):
                    await app.generate_meme("test", "OpenAI", "offline-test-key")
        asyncio.run(exercise())

    def test_ui_requires_credentials(self):
        page = AppTest.from_file(str(Path(app.__file__))).run()
        self.assertFalse(page.exception)
        page.button[0].click().run()
        self.assertFalse(page.exception)
        self.assertIn("API key", page.warning[0].value)
