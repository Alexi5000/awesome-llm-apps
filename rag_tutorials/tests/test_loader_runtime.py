import ast
from contextlib import closing, nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import Mock, patch

from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = {
    "gemini_agentic_rag": "agentic_rag_gemini.py",
    "deepseek_local_rag_agent": "deepseek_rag_agent.py",
}


def load_functions(folder, filename):
    path = ROOT / folder / filename
    tree = ast.parse(path.read_text())
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.ClassDef, ast.FunctionDef))
                 or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "COLLECTION_NAME" for t in node.targets)]
    namespace = {"__name__": "offline_rag"}
    exec(compile(tree, str(path), "exec"), namespace)
    namespace["st"] = SimpleNamespace(
        session_state=SimpleNamespace(google_api_key="offline-key", exa_api_key="offline-key", model_version="deepseek-r1:1.5b"),
        success=Mock(), error=Mock(), spinner=lambda *args: nullcontext(),
    )
    namespace["search_domains"] = ["example.com"]
    return namespace


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = b'<html><head><title>Verified report</title></head><body><main class="content">Solar energy report: panels generate electricity.</main></body></html>'
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class LoaderRuntimeTests(unittest.TestCase):
    def test_both_ui_entrypoints_render_without_credentials(self):
        for folder, filename in EXAMPLES.items():
            with self.subTest(folder=folder):
                app = AppTest.from_file(str(ROOT / folder / filename)).run(timeout=30)
                self.assertFalse(app.exception, [error.message for error in app.exception])

    def test_google_embedding_uses_native_sdk_response_and_rejects_empty(self):
        ns = load_functions("gemini_agentic_rag", EXAMPLES["gemini_agentic_rag"])
        embedder = ns["GeminiEmbedder"]()
        types = ns["types"]
        response = types.EmbedContentResponse(embeddings=[types.ContentEmbedding(values=[1.0, 0.0])])
        with patch.object(embedder.client.models, "embed_content", autospec=True, return_value=response) as request:
            self.assertEqual(embedder.embed_documents(["solar"]), [[1.0, 0.0]])
            self.assertEqual(request.call_args.kwargs["contents"], "solar")
            self.assertEqual(request.call_args.kwargs["config"].task_type, "RETRIEVAL_DOCUMENT")
        with patch.object(embedder.client.models, "embed_content", return_value=types.EmbedContentResponse()):
            with self.assertRaises(ValueError):
                embedder.embed_query("solar")
        embedder.client.close()

    def test_actual_web_processing_vector_ingestion_and_retrieval(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for folder, filename in EXAMPLES.items():
                with self.subTest(folder=folder):
                    ns = load_functions(folder, filename)
                    size = 768 if folder.startswith("gemini") else 1024
                    class LocalEmbeddings(Embeddings):
                        def embed_documents(self, texts):
                            return [self.embed_query(text) for text in texts]
                        def embed_query(self, text):
                            return [1.0] + [0.0] * (size - 1)
                    ns["GeminiEmbedder" if size == 768 else "OllamaEmbedderr"] = LocalEmbeddings
                    docs = ns["process_web"](f"http://127.0.0.1:{server.server_port}")
                    self.assertTrue(docs)
                    self.assertIn("Solar energy", docs[0].page_content)
                    self.assertEqual(docs[0].metadata["source_type"], "url")
                    with closing(QdrantClient(location=":memory:")) as client:
                        store = ns["create_vector_store"](client, docs)
                        self.assertIsNotNone(store, ns["st"].error.call_args_list)
                        found = store.similarity_search("solar", k=1)
                        self.assertIn("Solar energy", found[0].page_content)
                        self.assertEqual(found[0].metadata["source_type"], "url")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_pdf_loader_keeps_text_and_source_metadata(self):
        from io import BytesIO
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
        writer = PdfWriter()
        page = writer.add_blank_page(width=300, height=200)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        content = DecodedStreamObject()
        content.set_data(b"BT /F1 12 Tf 20 100 Td (Solar energy report) Tj ET")
        page[NameObject("/Contents")] = content
        file = BytesIO()
        writer.write(file)
        file.name = "report.pdf"
        for folder, filename in EXAMPLES.items():
            ns = load_functions(folder, filename)
            docs = ns["process_pdf"](file)
            self.assertTrue(docs, ns["st"].error.call_args_list)
            self.assertIn("Solar energy report", docs[0].page_content)
            self.assertEqual(docs[0].metadata["file_name"], "report.pdf")

    def test_ollama_embedding_uses_native_sdk(self):
        from ollama import Client, EmbedResponse
        ns = load_functions("deepseek_local_rag_agent", EXAMPLES["deepseek_local_rag_agent"])
        embedder = ns["OllamaEmbedderr"]()
        vector = [1.0] + [0.0] * 1023
        with patch.object(Client, "embed", autospec=True, return_value=EmbedResponse(embeddings=[vector])) as request:
            self.assertEqual(embedder.embed_documents(["solar"]), [vector])
            self.assertEqual(request.call_args.kwargs["input"], "solar")

    def test_all_agent_factories_construct_with_native_models_and_search(self):
        for folder, filename in EXAMPLES.items():
            ns = load_functions(folder, filename)
            for name in ("get_rag_agent", "get_web_search_agent", "get_query_rewriter_agent"):
                if name in ns:
                    with self.subTest(folder=folder, factory=name):
                        agent = ns[name]()
                        self.assertTrue(agent.model.id)
                        if name == "get_web_search_agent":
                            self.assertEqual(agent.tools[0].include_domains, ["example.com"])


if __name__ == "__main__":
    unittest.main()
