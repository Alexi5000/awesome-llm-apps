"""Speech trainer analysis tools may only decode files inside the upload directory."""

import ast
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "advanced_ai_agents/multi_agent_apps/ai_speech_trainer_agent"
spec = importlib.util.spec_from_file_location("speech_media_paths", APP / "backend/agents/tools/media_paths.py")
media = importlib.util.module_from_spec(spec)
spec.loader.exec_module(media)


class SpeechTrainerMediaPathTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.base = Path(scratch.name).resolve()
        self.uploads = self.base / "uploads"
        self.uploads.mkdir()
        self.outside = self.base / "outside"
        self.outside.mkdir()
        env = patch.dict(os.environ, {media.UPLOAD_DIR_ENV: str(self.uploads)})
        env.start()
        self.addCleanup(env.stop)
        self.video = self.uploads / "clip.mp4"
        self.video.write_bytes(b"video")
        (self.outside / "secret.mp4").write_bytes(b"secret")
        (self.outside / "notes.txt").write_bytes(b"secret")

    def test_accepts_uploaded_media_by_absolute_or_relative_path(self):
        self.assertEqual(media.resolve_upload_media(str(self.video)), str(self.video))
        self.assertEqual(media.resolve_upload_media("clip.mp4"), str(self.video))

    def test_rejects_host_paths_traversal_and_missing_files(self):
        for path in [str(self.outside / "secret.mp4"), "../outside/secret.mp4", "/etc/passwd",
                     str(self.uploads / ".." / "outside" / "secret.mp4"), str(self.uploads / "missing.mp4"),
                     str(self.uploads), "", "   ", "clip.mp4\x00.txt", None]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                media.resolve_upload_media(path)

    def test_rejects_symlink_escapes(self):
        leaf = self.uploads / "link.mp4"
        leaf.symlink_to(self.outside / "secret.mp4")
        folder = self.uploads / "nested"
        folder.symlink_to(self.outside, target_is_directory=True)
        inside_link = self.uploads / "alias.mp4"
        inside_link.symlink_to(self.video)
        for path in [leaf, folder / "secret.mp4", inside_link]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                media.resolve_upload_media(str(path))

    def test_rejects_non_media_and_directories(self):
        (self.uploads / "notes.txt").write_bytes(b"text")
        (self.uploads / "dir.mp4").mkdir()
        for name in ["notes.txt", "dir.mp4"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                media.resolve_upload_media(str(self.uploads / name))

    def load_tool(self, relative, name, **scope):
        source = APP / relative
        node = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == name)
        node.decorator_list = []
        namespace = {"json": json, "os": os, "tempfile": tempfile, "resolve_upload_media": media.resolve_upload_media, **scope}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
        return namespace[name]

    def test_tools_reject_model_selected_host_paths_before_decoding(self):
        transcribe, librosa, cv2 = Mock(), Mock(), Mock()
        voice = self.load_tool("backend/agents/tools/voice_analysis_tool.py", "analyze_voice_attributes",
                               transcribe_audio=transcribe, librosa=librosa, extract_audio_from_video=Mock())
        face = self.load_tool("backend/agents/tools/facial_expression_tool.py", "analyze_facial_expressions",
                              cv2=cv2, mp=Mock())
        secret = str(self.outside / "secret.mp4")
        self.assertIn("error", json.loads(voice(secret)))
        self.assertIn("error", json.loads(face(secret)))
        transcribe.assert_not_called()
        librosa.load.assert_not_called()
        cv2.VideoCapture.assert_not_called()

    def test_route_and_both_tools_apply_containment(self):
        for relative, marker in [("backend/main.py", "resolve_upload_media(request.video_url)"),
                                 ("backend/agents/tools/voice_analysis_tool.py", "resolve_upload_media(file_path)"),
                                 ("backend/agents/tools/facial_expression_tool.py", "resolve_upload_media(video_path)")]:
            with self.subTest(relative=relative):
                self.assertIn(marker, (APP / relative).read_text())


if __name__ == "__main__":
    unittest.main()
