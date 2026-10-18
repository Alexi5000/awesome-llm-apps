import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aiohttp
from bs4 import BeautifulSoup
from fastapi import FastAPI, File, UploadFile
from fastapi.testclient import TestClient
import httpx
import jwt
from lxml_html_clean import Cleaner
from nltk.tokenize import wordpunct_tokenize
from PIL import Image
from tools.browser_crawler import PlaywrightScraper
from redis import Redis

from utils.crawl_url import get_web_data
from utils.rss_feed_parser import get_feed_data


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/feed":
            body = b'<rss version="2.0"><channel><title>News</title><item><title>Local story</title><link>https://example.com/story</link><guid isPermaLink="false">story-1</guid></item></channel></rss>'
            content_type = "application/rss+xml"
        else:
            body = b'<html><head><title>Local story</title><meta name="description" content="Verified metadata"></head><body><article>News content</article></body></html>'
            content_type = "text/html"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class DependencyRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def test_browser_support_crypto_and_mcp_contract(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.exceptions import InvalidSignature
        from mcp.types import Tool
        key = Ed25519PrivateKey.generate()
        signature = key.sign(b"offline payload")
        key.public_key().verify(signature, b"offline payload")
        with self.assertRaises(InvalidSignature):
            key.public_key().verify(signature, b"changed payload")
        tool = Tool.model_validate({"name": "search", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}}})
        self.assertEqual(tool.model_dump()["inputSchema"]["properties"]["query"]["type"], "string")

    def test_existing_agno_session_schema_remains_readable(self):
        import json
        import sqlite3
        import tempfile
        from agno.agent import Agent
        from agno.models.openai import OpenAIChat
        from db.podcast_storage import get_podcast_db
        requests = []
        def respond(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "offline-run", "object": "chat.completion", "created": 1,
                "model": "gpt-4o", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": "New answer"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}})
        with tempfile.TemporaryDirectory() as directory:
            filename = str(Path(directory) / "sessions.db")
            memory = {"runs": [{"run_id": "old-run", "agent_id": "podcast-agent", "session_id": "offline-session",
                "content": "Old answer", "messages": [{"role": "user", "content": "Old question"},
                {"role": "assistant", "content": "Old answer"}], "created_at": 1}]}
            with sqlite3.connect(filename) as connection:
                connection.execute("CREATE TABLE podcast_sessions (session_id TEXT PRIMARY KEY, agent_id TEXT, memory TEXT, session_data TEXT, created_at INTEGER, updated_at INTEGER)")
                connection.execute("INSERT INTO podcast_sessions VALUES (?, ?, ?, ?, ?, ?)",
                    ("offline-session", "podcast-agent", json.dumps(memory), json.dumps({"session_state": {"stage": "source_selection"}}), 1, 2))
                connection.execute("INSERT INTO podcast_sessions VALUES (?, ?, ?, ?, ?, ?)",
                    ("empty-session", "podcast-agent", '{"runs": []}', '{}', 1, 2))
            db = get_podcast_db(filename)
            with httpx.Client(transport=httpx.MockTransport(respond)) as client:
                agent = Agent(id="podcast-agent", model=OpenAIChat(id="gpt-4o", api_key="offline-key", http_client=client),
                    db=db, session_id="offline-session", add_history_to_context=True, telemetry=False)
                result = agent.run("New question")
            self.assertEqual(result.content, "New answer")
            self.assertTrue(any(message.get("content") == "Old question" for message in requests[0]["messages"]))
            self.assertTrue(any(message.get("content") == "Old answer" for message in requests[0]["messages"]))
            get_podcast_db(filename)
            with sqlite3.connect(filename) as connection:
                row = connection.execute("SELECT memory, session_data FROM podcast_sessions WHERE session_id = ?", ("offline-session",)).fetchone()
                backup = connection.execute("SELECT memory FROM podcast_sessions_v1_backup WHERE session_id = ?", ("offline-session",)).fetchone()
                self.assertEqual(json.loads(backup[0]), memory)
                self.assertEqual(len(json.loads(row[0])["runs"]), 2)
                self.assertEqual(json.loads(row[1])["session_state"]["stage"], "source_selection")
                connection.execute("DELETE FROM podcast_sessions WHERE session_id = ?", ("offline-session",))
                connection.commit()
            get_podcast_db(filename)
            with sqlite3.connect(filename) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM podcast_sessions WHERE session_id = ?", ("offline-session",)).fetchone()[0], 0)

    def test_actual_agno_v1_fixture_preserves_history_and_metrics(self):
        import json
        import sqlite3
        import tempfile
        from agno.db.base import SessionType
        from db.podcast_storage import get_podcast_db
        source = json.loads((Path(__file__).parent / "fixtures" / "agno_v1_session.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            filename = str(Path(directory) / "sessions.db")
            with sqlite3.connect(filename) as connection:
                columns = ", ".join('"' + key + '"' for key in source)
                connection.execute("CREATE TABLE podcast_sessions (" + columns + ")")
                connection.execute("INSERT INTO podcast_sessions VALUES (" + ",".join("?" for _ in source) + ")", tuple(source.values()))
            session = get_podcast_db(filename).get_session("offline-session", SessionType.AGENT)
            self.assertEqual(len(session.runs), 1)
            self.assertEqual(session.runs[0].content, "Old answer")
            self.assertEqual(session.session_data["session_state"]["stage"], "source_selection")
            self.assertEqual([m.content for m in session.runs[0].messages if m.role == "user"], ["Old question"])

    def test_invalid_legacy_session_aborts_without_replacing_original(self):
        import sqlite3
        import tempfile
        from db.podcast_storage import get_podcast_db
        with tempfile.TemporaryDirectory() as directory:
            filename = str(Path(directory) / "sessions.db")
            with sqlite3.connect(filename) as connection:
                connection.execute("CREATE TABLE podcast_sessions (session_id TEXT PRIMARY KEY, memory TEXT)")
                connection.execute("INSERT INTO podcast_sessions VALUES ('bad', 'invalid JSON')")
            with self.assertRaises(ValueError):
                get_podcast_db(filename)
            with sqlite3.connect(filename) as connection:
                self.assertEqual(connection.execute("SELECT type FROM sqlite_master WHERE name='podcast_sessions'").fetchone()[0], "table")
                self.assertEqual(connection.execute("SELECT memory FROM podcast_sessions").fetchone()[0], "invalid JSON")

    def test_agent_constructor_arguments_match_supported_api(self):
        import ast
        import inspect
        from agno.agent import Agent
        parameters = inspect.signature(Agent).parameters
        root = Path(__file__).resolve().parents[1]
        for folder in (root / "agents", root / "tools", root / "services"):
            for source in folder.rglob("*.py"):
                for node in ast.walk(ast.parse(source.read_text())):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Agent":
                        for keyword in node.keywords:
                            if keyword.arg:
                                self.assertIn(keyword.arg, parameters, f"{source}: unsupported {keyword.arg}")

    def test_browser_search_preserves_structured_results(self):
        import os
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch
        with patch.dict(os.environ, {"ANONYMIZED_TELEMETRY": "false", "OPENAI_API_KEY": "offline-key"}):
            from tools.web_search import run_browser_search, BrowserAgent
            from browser_use.agent.views import AgentHistoryList
            history = AgentHistoryList(history=[])
            payload = '{"results":[{"title":"Local news","url":"https://example.com/news","content":"Verified article"}]}'
            previous = os.getcwd()
            with tempfile.TemporaryDirectory() as directory:
                try:
                    os.chdir(directory)
                    with patch.object(BrowserAgent, 'run', new=AsyncMock(return_value=history)), patch.object(AgentHistoryList, 'final_result', return_value=payload):
                        result = run_browser_search(SimpleNamespace(session_id="offline-session"), "Find local news")
                    self.assertIn('Verified article', result)
                    self.assertIn('"is_scrapping_required": false', result)
                    with patch.object(BrowserAgent, 'run', new=AsyncMock(side_effect=ValueError("provider unavailable"))):
                        failed = run_browser_search(SimpleNamespace(session_id="offline-session"), "Find local news")
                    self.assertIn('Error running browser search: provider unavailable', failed)
                finally:
                    os.chdir(previous)

    def test_embedding_and_audio_transformer_compatibility(self):
        import torch
        from sentence_transformers import SentenceTransformer, models
        from transformers import AlbertConfig
        from kokoro.modules import CustomAlbert
        embedding = SentenceTransformer(modules=[models.BoW(["news", "audio", "story"])])
        vectors = embedding.encode(["news story", "audio"])
        self.assertEqual(vectors.shape, (2, 3))
        self.assertGreater(float(vectors[0].sum()), 0)
        model = CustomAlbert(AlbertConfig(vocab_size=32, embedding_size=8,
            hidden_size=16, num_hidden_layers=1, num_attention_heads=2,
            intermediate_size=24))
        with torch.no_grad():
            output = model(torch.tensor([[1, 2, 3]]))
        self.assertEqual(tuple(output.shape), (1, 3, 16))
        self.assertTrue(torch.isfinite(output).all())

    def test_safe_tensor_checkpoint_roundtrip(self):
        import torch
        import pickle
        checkpoint = BytesIO()
        torch.save({"embedding": torch.tensor([1.0, 2.0])}, checkpoint)
        checkpoint.seek(0)
        self.assertEqual(torch.load(checkpoint, weights_only=True)["embedding"].tolist(), [1.0, 2.0])
        unsafe = BytesIO()
        torch.save({"callable": eval}, unsafe)
        unsafe.seek(0)
        with self.assertRaises(pickle.UnpicklingError):
            torch.load(unsafe, weights_only=True)

    def test_actual_web_extractor(self):
        result = get_web_data(self.url)
        self.assertEqual(result["metadata"]["title"], "Local story")
        self.assertEqual(result["metadata"]["description"], "Verified metadata")
        self.assertIn("News content", result["raw_html"])
        soup = BeautifulSoup(result["raw_html"], "html.parser")
        self.assertEqual(soup.select_one("body > article").text, "News content")

    def test_actual_feed_parser(self):
        result = get_feed_data(self.url + "/feed")
        self.assertTrue(result["is_rss_feed"])
        self.assertEqual(result["parsed_entries"][0]["entry_id"], "story-1")

    def test_async_http_stack(self):
        async def request():
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn("News content", await response.text())
            async with httpx.AsyncClient(http2=True) as client:
                response = await client.get(self.url)
                self.assertEqual(response.status_code, 200)
        asyncio.run(request())

    def test_multipart_upload(self):
        app = FastAPI()
        @app.post("/upload")
        async def upload(file: UploadFile = File()):
            return {"name": file.filename, "body": (await file.read()).decode()}
        with TestClient(app) as client:
            response = client.post("/upload", files={"file": ("article.md", b"News content")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"name": "article.md", "body": "News content"})

    def test_text_cleaning_and_tokenization(self):
        cleaned = Cleaner().clean_html('<div><script>alert(1)</script><p>News content.</p></div>')
        self.assertNotIn("script", cleaned)
        self.assertEqual(wordpunct_tokenize("News content."), ["News", "content", "."])

    def test_newspaper_article_extraction(self):
        result = PlaywrightScraper()._parse_with_newspaper(self.url, self.url)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["title"], "Local story")

    def test_image_decode_resize_and_encode(self):
        source = Image.new("RGB", (40, 20), color=(12, 34, 56))
        png = BytesIO()
        source.save(png, format="PNG")
        png.seek(0)
        with Image.open(png) as image:
            image.load()
            self.assertEqual(image.size, (40, 20))
            image.thumbnail((10, 10), Image.Resampling.LANCZOS)
            self.assertEqual(image.size, (10, 5))
            jpg = BytesIO()
            image.save(jpg, format="JPEG")
        jpg.seek(0)
        with Image.open(jpg) as image:
            image.load()
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.size, (10, 5))

    def test_redis_and_jwt_compatibility(self):
        key = "local-test-key-with-at-least-32-bytes"
        token = jwt.encode({"sub": "reader"}, key, algorithm="HS256")
        self.assertEqual(jwt.decode(token, key, algorithms=["HS256"])["sub"], "reader")
        with self.assertRaises(jwt.InvalidSignatureError):
            jwt.decode(token, key + "wrong", algorithms=["HS256"])
        client = Redis.from_url("redis://localhost:6379/2")
        self.assertEqual(client.connection_pool.connection_kwargs["db"], 2)
        client.close()


if __name__ == "__main__":
    unittest.main()
