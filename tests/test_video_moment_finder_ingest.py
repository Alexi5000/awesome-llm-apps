"""Video moment finder: upload filename containment and frame/embedding budget."""

import ast
import asyncio
import importlib.util
import math
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "advanced_llm_apps/multimodal_video_moment_finder/backend"


def load(name, relative, extra_modules=None):
    modules = dict(extra_modules or {})
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location(name, BACKEND / relative)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module


limits = load("ingest_limits", "ingest_limits.py")


def stub(name, **attrs):
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    return module


genai_types = stub("google.genai.types", Part=SimpleNamespace(from_bytes=lambda data, mime_type: data))
store_module = load("cf_video_store", "video_store.py", {
    "ingest_limits": limits,
    "PIL": stub("PIL", Image=SimpleNamespace()),
    "chromadb": stub("chromadb"),
    "google": stub("google"),
    "google.genai": stub("google.genai", types=genai_types),
    "google.genai.types": genai_types,
})


class Upload:
    def __init__(self, filename, data=b"video-bytes"):
        self.filename = filename
        self.data = data
        self.sizes = []

    async def read(self, size=-1):
        self.sizes.append(size)
        return self.data if size < 0 else self.data[:size]


def upload_handler(uploads_dir, store):
    tree = ast.parse((BACKEND / "server.py").read_text())
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "upload_video")
    node.decorator_list = []
    node.args.defaults = []
    scope = {"HTTPException": HTTPException, "UploadFile": object, "File": None, "Form": None,
             "uploads_dir": uploads_dir, "store": store, "MAX_UPLOAD_BYTES": limits.MAX_UPLOAD_BYTES,
             "clamp_fps": limits.clamp_fps, "display_filename": limits.display_filename,
             "stored_upload_path": limits.stored_upload_path}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(BACKEND / "server.py"), "exec"), scope)
    return scope["upload_video"]


class UploadContainmentTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.base = Path(scratch.name).resolve()
        self.uploads = self.base / "uploads"
        self.uploads.mkdir()
        self.store = Mock()
        self.store.ingest_video.return_value = {"video_id": "v1"}
        self.handler = upload_handler(self.uploads, self.store)

    def call(self, filename, fps=1.0, data=b"video-bytes"):
        return asyncio.run(self.handler(file=Upload(filename, data), fps=fps))

    def test_traversal_and_absolute_names_stay_inside_uploads(self):
        sentinel = self.base / "sentinel.mp4"
        sentinel.write_bytes(b"original")
        for name in ["../sentinel.mp4", str(sentinel), "..\\..\\sentinel.mp4", "a/b/../../../sentinel.mp4"]:
            with self.subTest(name=name):
                self.call(name)
                path, display = self.store.ingest_video.call_args.args
                stored = Path(path)
                self.assertEqual(stored.parent, self.uploads)
                self.assertEqual(display, "sentinel.mp4")
                self.assertEqual(self.store.ingest_video.call_args.kwargs["stored_filename"], stored.name)
        self.assertEqual(sentinel.read_bytes(), b"original")
        self.assertEqual(sorted(p.parent for p in self.base.rglob("*.mp4") if p != sentinel), [self.uploads] * 4)

    def test_non_video_extensions_are_rejected_before_writing(self):
        for name in ["page.html", "script.js", "noext", "", None, "clip.mp4.html"]:
            with self.subTest(name=name), self.assertRaises(HTTPException) as caught:
                self.call(name)
            self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(list(self.uploads.iterdir()), [])

    def test_oversized_upload_is_rejected_with_bounded_read(self):
        upload = Upload("big.mp4", b"x" * (limits.MAX_UPLOAD_BYTES + 5))
        with self.assertRaises(HTTPException):
            asyncio.run(self.handler(file=upload, fps=1.0))
        self.assertEqual(upload.sizes, [limits.MAX_UPLOAD_BYTES + 1])
        self.assertEqual(list(self.uploads.iterdir()), [])

    def test_failed_ingest_removes_the_stored_video(self):
        self.store.ingest_video.return_value = {"error": "No frames extracted"}
        with self.assertRaises(HTTPException):
            self.call("clip.mp4")
        self.assertEqual(list(self.uploads.iterdir()), [])


class FrameBudgetTests(unittest.TestCase):
    def test_fps_is_clamped_and_invalid_values_rejected(self):
        self.assertEqual(limits.clamp_fps(1), 1.0)
        self.assertEqual(limits.clamp_fps(1000), limits.MAX_FPS)
        self.assertEqual(limits.clamp_fps(1e-9), limits.MIN_FPS)
        for value in [0, -1, math.inf, -math.inf, math.nan, "abc", None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                limits.clamp_fps(value)

    def test_upload_route_rejects_invalid_fps_before_writing(self):
        with tempfile.TemporaryDirectory() as scratch:
            store = Mock()
            store.ingest_video.return_value = {"video_id": "v1"}
            handler = upload_handler(Path(scratch), store)
            for fps in [0, -2, math.nan, math.inf]:
                with self.subTest(fps=fps), self.assertRaises(HTTPException):
                    asyncio.run(handler(file=Upload("clip.mp4"), fps=fps))
            store.ingest_video.assert_not_called()
            self.assertEqual(list(Path(scratch).iterdir()), [])
            asyncio.run(handler(file=Upload("clip.mp4"), fps=500))
            self.assertEqual(store.ingest_video.call_args.kwargs["fps"], limits.MAX_FPS)

    def test_ffmpeg_is_bounded_by_frame_count_rate_and_time(self):
        store = store_module.VideoStore.__new__(store_module.VideoStore)
        with tempfile.TemporaryDirectory() as scratch:
            store.frames_dir = Path(scratch)
            calls = []

            def run(command, **kwargs):
                calls.append((command, kwargs))
                return SimpleNamespace(stdout="12.0\n")

            with patch.object(store_module.subprocess, "run", side_effect=run):
                store.extract_frames("/uploads/clip.mp4", fps=999)
        ffprobe, ffmpeg = calls
        self.assertIn("timeout", ffprobe[1])
        self.assertEqual(ffmpeg[1]["timeout"], limits.FFMPEG_TIMEOUT_SECONDS)
        command = ffmpeg[0]
        self.assertEqual(command[command.index("-vf") + 1], f"fps={limits.MAX_FPS}")
        self.assertEqual(command[command.index("-frames:v") + 1], str(limits.MAX_FRAMES))

    def test_ffmpeg_timeout_keeps_partial_frames(self):
        store = store_module.VideoStore.__new__(store_module.VideoStore)
        with tempfile.TemporaryDirectory() as scratch:
            store.frames_dir = Path(scratch)

            def run(command, **kwargs):
                if command[0] == "ffmpeg":
                    out = Path(command[-2]).parent
                    (out / "frame_0001.jpg").write_bytes(b"jpg")
                    raise subprocess.TimeoutExpired(command, kwargs["timeout"])
                return SimpleNamespace(stdout="")

            with patch.object(store_module.subprocess, "run", side_effect=run):
                frames, duration, _ = store.extract_frames("/uploads/clip.mp4", fps=1)
        self.assertEqual(len(frames), 1)
        self.assertEqual(duration, 0)

    def test_embedding_calls_are_capped_by_frame_budget(self):
        store = store_module.VideoStore.__new__(store_module.VideoStore)
        with tempfile.TemporaryDirectory() as scratch:
            frame = Path(scratch) / "f.jpg"
            frame.write_bytes(b"jpg")
            many = [{"path": str(frame), "timestamp": i, "frame_num": i + 1, "video_id": "v"}
                    for i in range(limits.MAX_FRAMES + 50)]
            store.extract_frames = Mock(return_value=(many, 10.0, "v"))
            store._resize_image = lambda data: data
            embed = Mock(side_effect=lambda model, contents: SimpleNamespace(
                embeddings=[SimpleNamespace(values=[0.0]) for _ in contents]))
            store.client = SimpleNamespace(models=SimpleNamespace(embed_content=embed))
            store.collection = Mock()
            result = store.ingest_video("/uploads/clip.mp4", "clip.mp4", fps=1, stored_filename="abc.mp4")
        embedded = sum(len(call.kwargs["contents"]) for call in embed.call_args_list)
        self.assertEqual(embedded, limits.MAX_FRAMES)
        self.assertEqual(embed.call_count, math.ceil(limits.MAX_FRAMES / 6))
        self.assertEqual(result["frames_extracted"], limits.MAX_FRAMES)
        metadata = store.collection.add.call_args.kwargs["metadatas"][0]
        self.assertEqual(metadata["stored_filename"], "abc.mp4")


if __name__ == "__main__":
    unittest.main()
