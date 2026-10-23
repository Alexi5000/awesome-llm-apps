import asyncio
import importlib
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class InputBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory()
        cls.previous = os.getcwd()
        os.chdir(cls.workspace.name)
        from services import social_media_service
        cls.social = social_media_service
        tasks = ModuleType("services.celery_tasks")
        tasks.agent_chat = Mock()
        with patch.dict(sys.modules, {"services.celery_tasks": tasks}):
            cls.podcast = importlib.import_module("services.async_podcast_agent_service")
            cls.router = importlib.import_module("routers.async_podcast_agent_router")
        cls.web = importlib.import_module("tools.web_search")

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.previous)
        cls.workspace.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=self.workspace.name)
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.chdir, self.cwd)
        self.db = str(Path("social.db").resolve())
        Path("podcasts/recordings").mkdir(parents=True)
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE posts (post_id TEXT, post_timestamp TEXT, sentiment TEXT, platform TEXT)")
            conn.executemany("INSERT INTO posts VALUES (?, ?, ?, ?)", [
                ("one", "2000-01-01", "positive", "x"),
                ("two", "2000-01-01", "negative", "reddit"),
            ])

    def trends(self, start=None, end=None, platform=None):
        with patch.object(self.social.social_media_db, "db_path", self.db):
            return asyncio.run(self.social.SocialMediaService().get_sentiment_over_time(start, end, platform))

    def test_dates_and_platform_preserve_counts_and_empty_days(self):
        rows = self.trends("2000-01-01", "2000-01-02", "x")
        self.assertEqual([row["post_date"] for row in rows], ["2000-01-01", "2000-01-02"])
        self.assertEqual(rows[0]["total_count"], 1)
        self.assertEqual(rows[0]["positive_percent"], 100)
        self.assertEqual(rows[1]["total_count"], 0)
        self.assertEqual(self.trends("2000-01-01", "2000-01-01")[0]["total_count"], 2)

    def test_default_range_and_single_selector_remain_supported(self):
        rows = self.trends()
        self.assertEqual(len(rows), 31)
        self.assertEqual(self.trends("2000-01-01"), rows)

    def test_injected_start_is_not_evaluated(self):
        rows = self.trends("2000-' || (SELECT '01') || '-01", "2000-01-01")
        self.assertIsNone(rows[0]["post_date"])
        self.assertEqual(rows[0]["total_count"], 0)

    def test_injected_end_is_not_evaluated(self):
        rows = self.trends("2000-01-01", "2000-' || (SELECT '01') || '-02")
        self.assertEqual([row["post_date"] for row in rows], ["2000-01-01"])

    def test_platform_remains_a_bound_value(self):
        rows = self.trends("2000-01-01", "2000-01-01", "x' OR 1=1 --")
        self.assertEqual(rows[0]["total_count"], 0)

    def recording(self, session_id):
        service = self.podcast.PodcastAgentService.__new__(self.podcast.PodcastAgentService)
        return service._browser_recording(session_id)

    def make_recording(self, relative):
        path = Path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * 8193)
        return path

    def test_recording_lookup_preserves_relative_path(self):
        path = self.make_recording("podcasts/recordings/offline-session/video.webm")
        self.assertEqual(self.recording("offline-session"), str(path))

    def test_recording_lookup_rejects_traversal_and_absolute_paths(self):
        path = self.make_recording("podcasts/sentinel/video.webm")
        for session in ("../sentinel", str(path.parent.resolve())):
            with self.subTest(session=session):
                self.assertIsNone(self.recording(session))

    def test_recording_lookup_does_not_expand_glob_characters(self):
        self.make_recording("podcasts/recordings/other/video.webm")
        self.assertIsNone(self.recording("*"))

    def test_recording_lookup_rejects_directory_and_file_symlinks(self):
        outside = self.make_recording("outside/video.webm").resolve()
        root = Path("podcasts/recordings")
        root.mkdir(parents=True, exist_ok=True)
        (root / "linked-session").symlink_to(outside.parent, target_is_directory=True)
        self.assertIsNone(self.recording("linked-session"))
        (root / "safe").mkdir()
        (root / "safe/video.webm").symlink_to(outside)
        self.assertIsNone(self.recording("safe"))

    def test_http_status_does_not_disclose_outside_recording(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        self.make_recording("podcasts/sentinel/video.webm")
        app = FastAPI()
        app.include_router(self.router.router, prefix="/api/podcast-agent")
        with patch.object(self.podcast.agent_chat, "AsyncResult", return_value=SimpleNamespace(state="PENDING")):
            with TestClient(app) as client:
                response = client.post("/api/podcast-agent/status", json={"session_id": "../sentinel", "task_id": "offline-task"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["browser_recording_path"])

    def test_browser_rejects_escape_before_browser_or_provider_construction(self):
        for session in ("../new-sentinel", str(Path("absolute-sentinel").resolve())):
            with self.subTest(session=session), patch.object(self.web, "BrowserProfile") as profile:
                result = self.web.run_browser_search(SimpleNamespace(session_id=session), "offline fixture")
                self.assertIn("Error running browser search", result)
                profile.assert_not_called()
        self.assertFalse(Path("podcasts/new-sentinel").exists())
        self.assertFalse(Path("absolute-sentinel").exists())

    def test_cleanup_cannot_remove_sibling_recording_directory(self):
        marker = self.make_recording("podcasts/sentinel/video.webm")
        session = "../sentinel"
        db = str(Path("sessions.db").resolve())
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE podcast_sessions (session_id TEXT, session_data TEXT)")
            conn.execute("INSERT INTO podcast_sessions VALUES (?, '{}')", (session,))
        service = self.podcast.PodcastAgentService.__new__(self.podcast.PodcastAgentService)
        with patch.object(self.podcast, "get_agent_session_db_path", return_value=db), patch.object(
            self.podcast.SessionService, "get_session", return_value={"state": {"web_search_recording": True}}
        ):
            asyncio.run(service.delete_session(session))
        self.assertTrue(marker.exists())
        with sqlite3.connect(db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM podcast_sessions").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
