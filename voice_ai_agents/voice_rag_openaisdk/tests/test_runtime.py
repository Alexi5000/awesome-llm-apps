import asyncio
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import httpx
import numpy as np
from openai import AsyncOpenAI
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from qdrant_client import QdrantClient, models
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("voice_app", ROOT / "rag_voice.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class Embeddings:
    def embed(self, texts):
        return [np.array([1.0, 0.0, 0.0]) for _ in texts]


class VoiceRuntimeTests(unittest.TestCase):
    def test_initial_ui(self):
        ui = AppTest.from_file(str(ROOT / "rag_voice.py")).run(timeout=30)
        self.assertEqual(len(ui.exception), 0)
        self.assertTrue(any("Voice RAG" in item.value for item in ui.title))

    def test_pdf_retrieval_agents_and_audio_transport(self):
        writer = PdfWriter()
        page = writer.add_blank_page(width=300, height=300)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 20 200 Td (Authentication uses bearer tokens.) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
        buffer = io.BytesIO()
        writer.write(buffer)
        upload = SimpleNamespace(name="guide.pdf", getvalue=buffer.getvalue)
        documents = app.process_pdf(upload)
        self.assertIn("bearer tokens", documents[0].page_content)
        client = QdrantClient(":memory:")
        client.create_collection(app.COLLECTION_NAME, vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE))
        app.store_embeddings(client, Embeddings(), documents, app.COLLECTION_NAME)
        processor, speech = app.setup_agents("test-key")
        state = SimpleNamespace(processor_agent=processor, tts_agent=speech)
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(200, content=b"audio-data", headers={"content-type": "audio/mpeg"})

        async def run():
            sdk = AsyncOpenAI(api_key="test-key", http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
            runner = AsyncMock(side_effect=[SimpleNamespace(final_output="Use a bearer token."), SimpleNamespace(final_output="Speak clearly.")])
            player = SimpleNamespace(play=AsyncMock())
            with patch.object(app.st, "session_state", state), patch.object(app.Runner, "run", runner), patch.object(app, "AsyncOpenAI", return_value=sdk), patch.object(app, "LocalAudioPlayer", return_value=player):
                result = await app.process_query("How do I authenticate?", client, Embeddings(), app.COLLECTION_NAME, "test-key", "coral")
            await sdk.close()
            self.assertEqual(result["status"], "success", result)
            self.assertEqual(result["sources"], ["guide.pdf"])
            self.assertIn("bearer tokens", runner.call_args_list[0].args[1])
            self.assertEqual(Path(result["audio_path"]).read_bytes(), b"audio-data")
            Path(result["audio_path"]).unlink()
            self.assertEqual(len(requests), 2)
            self.assertIn(b'"response_format":"mp3"', requests[1].content)
            player.play.assert_awaited_once()

        try:
            asyncio.run(run())
        finally:
            client.close()

    def test_missing_documents_fail_without_provider_calls(self):
        client = QdrantClient(":memory:")
        client.create_collection(app.COLLECTION_NAME, vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE))
        runner = AsyncMock()
        with patch.object(app.Runner, "run", runner):
            result = asyncio.run(app.process_query("question", client, Embeddings(), app.COLLECTION_NAME, "test-key", "coral"))
        client.close()
        self.assertEqual(result["status"], "error")
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
