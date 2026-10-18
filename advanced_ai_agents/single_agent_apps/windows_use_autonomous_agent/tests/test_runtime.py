import unittest
from unittest.mock import patch


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        guard = patch("socket.socket.connect", side_effect=AssertionError("Network is disabled"))
        guard.start()
        self.addCleanup(guard.stop)
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        from windows_use.agent import Agent
        self.agent = Agent(llm=FakeListChatModel(responses=["offline"]), max_steps=2)

    def test_registry_retains_tools(self):
        self.assertEqual(len(self.agent.registry.tools), 13)
        self.assertIn("Done Tool", self.agent.registry.get_tools_prompt())

    def test_done_tool_without_desktop_actions(self):
        result = self.agent.registry.execute("Done Tool", self.agent.desktop, answer="finished")
        self.assertTrue(result.is_success)
        self.assertEqual(result.content, "finished")

    def test_unknown_tool_is_rejected(self):
        result = self.agent.registry.execute("unknown", self.agent.desktop)
        self.assertFalse(result.is_success)

    def test_prompt_template(self):
        from windows_use.agent.prompt.service import Prompt
        with patch("pyautogui.size", return_value=(1280, 720)):
            prompt = Prompt.system_prompt(self.agent.registry.get_tools_prompt(), 2)
        self.assertIn("1280x720", prompt)

    def test_google_provider_import(self):
        from langchain_google_genai import ChatGoogleGenerativeAI
        self.assertTrue(callable(ChatGoogleGenerativeAI))


if __name__ == "__main__":
    unittest.main()
