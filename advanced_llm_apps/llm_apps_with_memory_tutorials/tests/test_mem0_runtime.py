import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ["MEM0_TELEMETRY"] = "false"

from mem0 import Memory
from mem0.exceptions import ValidationError


class MemoryRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        embedder = Mock()
        embedder.embed.return_value = [1.0, 0.0, 0.0]
        embedder.embed_batch.side_effect = lambda texts, *args: [[1.0, 0.0, 0.0] for _ in texts]
        self.llm = Mock()
        self.llm.generate_response.return_value = '{"memory": [{"text": "Enjoys hiking", "event": "ADD"}]}'
        with patch("mem0.memory.main.EmbedderFactory.create", return_value=embedder), patch(
            "mem0.memory.main.LlmFactory.create", return_value=self.llm
        ):
            self.memory = Memory.from_config({
                "vector_store": {"provider": "qdrant", "config": {
                    "path": self.directory.name + "/vectors",
                    "collection_name": "runtime",
                    "embedding_model_dims": 3,
                }},
                "history_db_path": self.directory.name + "/history.db",
            })
        self.addCleanup(self.memory.close)

    def test_add_search_and_history_preserve_user_isolation(self):
        added = self.memory.add("Enjoys hiking", user_id="alice", infer=False)
        self.assertEqual(added["results"][0]["memory"], "Enjoys hiking")
        self.memory.add("Enjoys swimming", user_id="bob", infer=False)
        for result in [self.memory.search("hobbies", filters={"user_id": "alice"}), self.memory.get_all(filters={"user_id": "alice"})]:
            self.assertEqual([item["memory"] for item in result["results"]], ["Enjoys hiking"])

    def test_inferred_memory_is_persisted(self):
        result = self.memory.add("I enjoy hiking", user_id="alice")
        self.assertEqual(result["results"][0]["memory"], "Enjoys hiking")
        self.assertEqual(self.memory.get_all(filters={"user_id": "alice"})["results"][0]["memory"], "Enjoys hiking")
        self.llm.generate_response.assert_called()

    def test_missing_user_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.memory.add("private preference")

    def test_personalized_app_uses_retrieved_context_and_stores_answer(self):
        from streamlit.testing.v1 import AppTest

        self.memory.add("Enjoys hiking", user_id="alice", infer=False)
        client = Mock()
        client.chat.completions.create.return_value.choices = [Mock(message=Mock(content="Try a mountain trail"))]
        path = Path(__file__).resolve().parents[1] / "llm_app_personalized_memory/llm_app_memory.py"
        with patch("mem0.Memory.from_config", return_value=self.memory), patch("openai.OpenAI", return_value=client):
            app = AppTest.from_file(str(path)).run()
            app.text_input[0].set_value("test-key").run()
            app.text_input[1].set_value("alice")
            app.text_input[2].set_value("What should I do this weekend?")
            app.button[0].click().run()
            self.assertEqual(list(app.exception), [])
            prompt = client.chat.completions.create.call_args.kwargs["messages"][-1]["content"]
            self.assertIn("Enjoys hiking", prompt)
            self.assertTrue(any("Try a mountain trail" in item.value for item in app.markdown))
            app.button[1].click().run()
            self.assertEqual(list(app.exception), [])


if __name__ == "__main__":
    unittest.main()
