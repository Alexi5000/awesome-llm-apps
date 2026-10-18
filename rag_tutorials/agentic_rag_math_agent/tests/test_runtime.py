from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import dspy
from dspy.utils.dummies import DummyLM
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage, Settings
from llama_index.core.embeddings import MockEmbedding
from llama_index.core.schema import Document
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag import query_router, guardrails


class MathRuntimeTests(unittest.TestCase):
    def test_initial_ui(self):
        ui = AppTest.from_file(str(ROOT / "app/streamlit.py")).run(timeout=30)
        self.assertEqual(len(ui.exception), 0)
        self.assertTrue(any("Math Tutor" in item.value for item in ui.title))

    def test_actual_guardrail_signatures_and_predictions(self):
        with dspy.context(lm=DummyLM([{"verdict": "Yes"}, {"verdict": "No"}, {"verdict": "Yes"}])):
            self.assertTrue(guardrails.InputValidator().forward("What is 2+2?"))
            self.assertFalse(guardrails.InputValidator().forward("Recommend a movie"))
            self.assertTrue(guardrails.OutputValidator().forward("2+2?", "4"))

    def test_qdrant_index_persistence_and_router_retrieval(self):
        client = QdrantClient(":memory:")
        embeddings = MockEmbedding(embed_dim=8)
        Settings.embed_model = embeddings
        store = QdrantVectorStore(client=client, collection_name="math_agent")
        context = StorageContext.from_defaults(vector_store=store)
        index = VectorStoreIndex.from_documents([Document(text="Q: What is 2+2? A: 4")], storage_context=context, embed_model=embeddings)
        try:
            with tempfile.TemporaryDirectory() as directory:
                index.storage_context.persist(persist_dir=directory)
                loaded = load_index_from_storage(StorageContext.from_defaults(persist_dir=directory, vector_store=store), embed_model=embeddings)
                with patch.object(query_router, "load_kb_index", return_value=loaded):
                    text, score = query_router.query_kb("2+2?")
                self.assertIn("A: 4", text)
                self.assertGreater(score, 0)
        finally:
            client.close()

    def test_kb_and_web_fallback_with_actual_guardrails(self):
        completion = SimpleNamespace(text="2 + 2 = 4")
        with patch.object(query_router.OpenAI, "complete", return_value=completion) as complete, patch.object(query_router, "query_kb", return_value=("Answer: 4", 1)), dspy.context(lm=DummyLM([{"verdict": "Yes"}, {"verdict": "Yes"}])):
            with patch.object(query_router, "OPENAI_API_KEY", "test-key"):
                self.assertEqual(query_router.answer_math_question("2+2?"), completion.text)
            self.assertIn("Answer: 4", complete.call_args.args[0])
        response = SimpleNamespace(json=lambda: {"answer": "The sum is 4"})
        with patch.object(query_router, "query_kb", return_value=("", 0)), patch.object(query_router.requests, "post", return_value=response) as request, patch.object(query_router.OpenAI, "complete", return_value=completion), patch.object(query_router, "OPENAI_API_KEY", "test-key"), dspy.context(lm=DummyLM([{"verdict": "Yes"}, {"verdict": "Yes"}])):
            self.assertEqual(query_router.answer_math_question("2+2?"), completion.text)
            self.assertEqual(request.call_args.kwargs["json"]["query"], "2+2?")


if __name__ == "__main__":
    unittest.main()
