"""The insurance live-voice WebSocket must reject cross-site browser origins before
accepting the socket or touching the operator's Gemini credentials."""

import asyncio
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "voice_ai_agents/insurance_claim_live_agent_team"


def load_server():
    agent = types.ModuleType("agent")
    agent.MODEL = "stub"
    agent.blank_claim = dict
    agent.build_initial_workflow_state = lambda *a, **k: {}
    agent.run_claim_workflow = lambda *a, **k: {}
    schemas = types.ModuleType("schemas")
    schemas.ClaimClassification = schemas.ClaimNarrative = object
    with patch.dict(sys.modules, {"agent": agent, "schemas": schemas}), patch.object(sys, "path", list(sys.path)):
        spec = importlib.util.spec_from_file_location("cf_insurance_server", APP / "live_demo/server.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    sys.modules[spec.name] = module
    return module


server = load_server()


class FakeWebSocket:
    def __init__(self, origin):
        self.headers = {} if origin is None else {"origin": origin}
        self.accepted = False
        self.closed_with = None
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def close(self, code=1000):
        self.closed_with = code

    async def send_json(self, payload):
        self.sent.append(payload)


class LiveOriginTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"FNOL_WS_ORIGINS": "", "FNOL_CORS_ORIGINS": "",
                                      "GOOGLE_API_KEY": "", "GEMINI_API_KEY": ""})
        env.start()
        self.addCleanup(env.stop)
        server.sessions.clear()

    def connect(self, origin):
        socket = FakeWebSocket(origin)
        with patch.object(server, "_client", side_effect=AssertionError("provider must not be reached")):
            asyncio.run(server.live_voice(socket))
        return socket

    def test_rejects_foreign_missing_and_lookalike_origins_before_accept(self):
        for origin in [None, "", "http://unrelated.test", "null", "http://127.0.0.1:4177.evil.test",
                       "https://127.0.0.1:4177", "http://localhost:9999"]:
            with self.subTest(origin=origin):
                socket = self.connect(origin)
                self.assertFalse(socket.accepted)
                self.assertEqual(socket.closed_with, 1008)
        self.assertEqual(server.sessions, {})

    def test_default_local_ui_origins_are_admitted(self):
        for origin in ["http://127.0.0.1:4177", "http://localhost:4177", "http://localhost:4177/"]:
            with self.subTest(origin=origin):
                socket = self.connect(origin)
                self.assertTrue(socket.accepted)
                self.assertNotEqual(socket.closed_with, 1008)

    def test_allowlist_is_configurable(self):
        with patch.dict(os.environ, {"FNOL_WS_ORIGINS": "https://claims.example.com"}):
            self.assertTrue(server._websocket_origin_allowed("https://claims.example.com"))
            self.assertFalse(server._websocket_origin_allowed("http://127.0.0.1:4177"))
        with patch.dict(os.environ, {"FNOL_CORS_ORIGINS": "http://127.0.0.1:9000"}):
            self.assertTrue(server._websocket_origin_allowed("http://127.0.0.1:9000"))


if __name__ == "__main__":
    unittest.main()
