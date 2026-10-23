import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from earnings_call_analyst_agent import youtube_ingest
from earnings_call_analyst_agent.live_demo import server


@pytest.fixture(autouse=True)
def clean_sessions(monkeypatch):
    monkeypatch.setattr(server, "sessions", {})
    yield


def _runtime(session_id: str, status: str = "queued") -> server.RuntimeSession:
    return server.RuntimeSession(session_id=session_id, youtube_url="abcDEF12345", status=status)


def test_admission_rejects_when_active_budget_is_full(monkeypatch):
    monkeypatch.setattr(server, "MAX_ACTIVE_SESSIONS", 2)
    server._admit_session(_runtime("a", "transcript"))
    server._admit_session(_runtime("b", "analysis"))
    with pytest.raises(HTTPException) as caught:
        server._admit_session(_runtime("c"))
    assert caught.value.status_code == 429
    assert "c" not in server.sessions


def test_admission_evicts_oldest_finished_session(monkeypatch):
    monkeypatch.setattr(server, "MAX_ACTIVE_SESSIONS", 5)
    monkeypatch.setattr(server, "MAX_RETAINED_SESSIONS", 2)
    server._admit_session(_runtime("old", "ready"))
    server._admit_session(_runtime("running", "research"))
    server._admit_session(_runtime("new"))
    assert list(server.sessions) == ["running", "new"]


def test_admission_refuses_when_retained_sessions_are_all_active(monkeypatch):
    monkeypatch.setattr(server, "MAX_ACTIVE_SESSIONS", 5)
    monkeypatch.setattr(server, "MAX_RETAINED_SESSIONS", 1)
    server._admit_session(_runtime("running", "metadata"))
    with pytest.raises(HTTPException) as caught:
        server._admit_session(_runtime("next"))
    assert caught.value.status_code == 429


def test_create_session_route_returns_429_without_scheduling(monkeypatch):
    from fastapi.testclient import TestClient

    scheduled = []

    async def fake_run(session_id):
        scheduled.append(session_id)

    monkeypatch.setattr(server, "_run_session", fake_run)
    monkeypatch.setattr(server, "MAX_ACTIVE_SESSIONS", 1)
    client = TestClient(server.app)
    first = client.post("/api/sessions", json={"youtube_url": "abcDEF12345"})
    assert first.status_code == 200
    second = client.post("/api/sessions", json={"youtube_url": "abcDEF12345"})
    assert second.status_code == 429
    assert scheduled == [first.json()["session_id"]]


@pytest.mark.parametrize(
    "info",
    [
        {"duration": 0},
        {},
        {"duration": "not-a-number"},
        {"duration": 60, "is_live": True},
        {"_type": "playlist", "duration": 60},
    ],
)
def test_audio_duration_budget_rejects_unknown_live_and_playlist(info):
    with pytest.raises(RuntimeError):
        youtube_ingest.enforce_audio_duration_budget(info)


def test_audio_duration_budget_enforces_maximum(monkeypatch):
    monkeypatch.setattr(youtube_ingest, "MAX_AUDIO_SECONDS", 600)
    youtube_ingest.enforce_audio_duration_budget({"duration": 600})
    with pytest.raises(RuntimeError):
        youtube_ingest.enforce_audio_duration_budget({"duration": 601})


def test_audio_chunk_budget_caps_calls_and_bytes(monkeypatch, tmp_path: Path):
    chunks = []
    for index in range(3):
        chunk = tmp_path / f"chunk_{index:03d}.mp3"
        chunk.write_bytes(b"x" * 10)
        chunks.append(chunk)
    monkeypatch.setattr(youtube_ingest, "MAX_AUDIO_CHUNKS", 3)
    monkeypatch.setattr(youtube_ingest, "MAX_AUDIO_BYTES", 30)
    youtube_ingest.enforce_audio_chunk_budget(chunks)
    monkeypatch.setattr(youtube_ingest, "MAX_AUDIO_CHUNKS", 2)
    with pytest.raises(RuntimeError):
        youtube_ingest.enforce_audio_chunk_budget(chunks)
    monkeypatch.setattr(youtube_ingest, "MAX_AUDIO_CHUNKS", 3)
    monkeypatch.setattr(youtube_ingest, "MAX_AUDIO_BYTES", 29)
    with pytest.raises(RuntimeError):
        youtube_ingest.enforce_audio_chunk_budget(chunks)


def test_audio_fallback_stops_before_any_adk_call_when_over_budget(monkeypatch, tmp_path: Path):
    calls = []

    class FakeYoutubeDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download):
            calls.append(("extract", download))
            return {"duration": youtube_ingest.MAX_AUDIO_SECONDS + 1}

    import yt_dlp

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYoutubeDL)
    monkeypatch.setattr(youtube_ingest, "has_adk_credentials", lambda: True)
    monkeypatch.setattr(youtube_ingest, "run_adk_agent_content", lambda *a: calls.append("adk"))
    with pytest.raises(RuntimeError):
        youtube_ingest.transcribe_audio_with_adk("abcDEF12345")
    assert calls == [("extract", False)]
