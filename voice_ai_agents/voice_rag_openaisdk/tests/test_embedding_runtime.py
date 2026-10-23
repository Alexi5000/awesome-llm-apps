import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer, models as embedding_models
from tokenizers import Tokenizer, models as tokenizer_models, pre_tokenizers
from transformers import BertConfig, BertModel, PreTrainedTokenizerFast

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("voice_embedding_app", ROOT / "rag_voice.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class EmbeddingRuntimeTests(unittest.TestCase):
    def test_real_encoder_and_separate_collection_preserve_old_vectors(self):
        with TemporaryDirectory() as directory:
            tokenizer = Tokenizer(tokenizer_models.WordLevel({"[UNK]": 0, "[PAD]": 1, "bearer": 2, "token": 3, "houses": 4}, unk_token="[UNK]"))
            tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
            PreTrainedTokenizerFast(tokenizer_object=tokenizer, unk_token="[UNK]", pad_token="[PAD]").save_pretrained(directory)
            BertModel(BertConfig(vocab_size=5, hidden_size=12, num_hidden_layers=1, num_attention_heads=3, intermediate_size=16)).save_pretrained(directory)
            encoder = SentenceTransformer(modules=[embedding_models.Transformer(directory, max_seq_length=16), embedding_models.Pooling(12)], device="cpu")
            vectors = encoder.encode(["bearer token", "houses"], normalize_embeddings=True)
            self.assertEqual(vectors.shape, (2, 12))
            np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), [1, 1], atol=1e-6)
            client = QdrantClient(":memory:")
            client.create_collection("voice-rag-agent", vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE))
            client.upsert("voice-rag-agent", [models.PointStruct(id=1, vector=[1, 0, 0], payload={"legacy": True})])
            state = SimpleNamespace(qdrant_url="https://qdrant.invalid", qdrant_api_key="test")
            try:
                with patch.object(app.st, "session_state", state), patch.object(app, "QdrantClient", return_value=client), patch.object(app, "SentenceTransformer", return_value=encoder) as factory:
                    actual_client, actual_encoder = app.setup_qdrant()
                factory.assert_called_once_with(app.EMBEDDING_MODEL, revision=app.EMBEDDING_REVISION, device="cpu", trust_remote_code=False)
                self.assertIs(actual_client, client)
                self.assertIs(actual_encoder, encoder)
                documents = [SimpleNamespace(page_content="bearer token", metadata={"source": "guide.pdf"})]
                app.store_embeddings(client, encoder, documents, app.COLLECTION_NAME)
                query = encoder.encode(["bearer token"], normalize_embeddings=True)[0]
                hits = client.query_points(app.COLLECTION_NAME, query=query.tolist(), limit=1).points
                self.assertEqual(hits[0].payload["content"], "bearer token")
                self.assertGreater(hits[0].score, 0.99)
                old = client.retrieve("voice-rag-agent", [1], with_vectors=True)[0]
                self.assertEqual(old.vector, [1.0, 0.0, 0.0])
                self.assertEqual(old.payload, {"legacy": True})
            finally:
                client.close()


if __name__ == "__main__":
    unittest.main()
