import importlib.util
import json
import httpx
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake import FakeListLLM
from langchain_qdrant import QdrantVectorStore as Qdrant
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from streamlit.testing.v1 import AppTest

SOURCE = Path(__file__).resolve().parents[1] / 'rag_database_routing.py'
spec = importlib.util.spec_from_file_location('routing_app', SOURCE)
app = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = app
spec.loader.exec_module(app)


class RuntimeTests(unittest.TestCase):
    def test_initial_ui_without_provider_keys(self):
        page = AppTest.from_file(str(SOURCE)).run(timeout=30)
        self.assertFalse(page.exception)

    def test_real_vector_store_retrieval_and_chain(self):
        client = QdrantClient(':memory:')
        client.create_collection('products', vectors_config=VectorParams(size=8, distance=Distance.COSINE))
        store = Qdrant(client, 'products', embedding=DeterministicFakeEmbedding(size=8))
        store.add_documents([Document(page_content='Widget price is $20', metadata={'source': 'offline'})])
        state = SimpleNamespace(llm=FakeListLLM(responses=['The widget costs $20.']))
        with patch.object(app.st, 'session_state', state):
            answer, docs = app.query_database(store, 'widget price')
        self.assertEqual(answer, 'The widget costs $20.')
        self.assertEqual(docs[0].metadata['source'], 'offline')
        client.close()

    def test_routing_agent_constructs_and_routes_low_confidence(self):
        state = SimpleNamespace(openai_api_key='offline-key', databases={})
        with patch.object(app.st, 'session_state', state), patch.object(
            app.Agent, 'run', return_value=SimpleNamespace(content='finance')
        ):
            self.assertEqual(app.route_query('quarterly revenue'), 'finance')

    def test_fallback_graph_constructs_with_current_chat_adapter(self):
        def respond(request):
            payload = json.loads(request.content)
            self.assertEqual(payload['tools'][0]['function']['name'], 'web_research')
            return httpx.Response(200, json={
                'id': 'offline', 'object': 'chat.completion', 'created': 0,
                'model': 'gpt-4o', 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': 'Offline research answer'}}],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}})
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            model = app.ChatOpenAI(api_key='offline-key', model='gpt-4o', http_client=client)
            graph = app.create_fallback_agent(model)
            result = graph.invoke({'messages': [('user', 'research a widget')]})
        self.assertEqual(result['messages'][-1].content, 'Offline research answer')


if __name__ == '__main__':
    unittest.main()
