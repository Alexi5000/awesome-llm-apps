import ast
import asyncio
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

ROOT = Path(__file__).resolve().parents[1]
BEIFONG = ROOT / "advanced_ai_agents/multi_agent_apps/ai_news_and_podcast_agents/beifong"
SENTINEL = "/private/credential-do-not-disclose"


class Response:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content


def load_service():
    tree = ast.parse((BEIFONG / "services/async_podcast_agent_service.py").read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "PodcastAgentService")
    db = Mock(side_effect=RuntimeError(SENTINEL))
    agent = Mock()
    scope = {
        "JSONResponse": Response,
        "status": SimpleNamespace(HTTP_500_INTERNAL_SERVER_ERROR=500, HTTP_400_BAD_REQUEST=400),
        "get_agent_session_db_path": db,
        "agent_chat": agent,
        "json": json,
    }
    exec(compile(ast.Module(body=[cls], type_ignores=[]), "podcast_service", "exec"), scope)
    service = scope["PodcastAgentService"].__new__(scope["PodcastAgentService"])
    service._browser_recording = Mock(return_value=None)
    service.get_active_task = AsyncMock(return_value=None)
    return service, agent


class SourceBoundaryTests(unittest.TestCase):
    def assert_private(self, result):
        payload = result.content if isinstance(result, Response) else result
        self.assertNotIn(SENTINEL, json.dumps(payload))
        return payload

    def test_podcast_error_paths_do_not_expose_exception_details(self):
        for method, args in [
            ("get_session_state", ("session",)),
            ("list_sessions", ()),
            ("delete_session", ("session",)),
            ("get_session_history", ("session",)),
        ]:
            with self.subTest(method=method):
                service, _ = load_service()
                result = asyncio.run(getattr(service, method)(*args))
                self.assert_private(result)
                if isinstance(result, Response):
                    self.assertEqual(result.status_code, 500)

    def test_chat_queue_failure_and_success_preserve_contract(self):
        service, agent = load_service()
        request = SimpleNamespace(session_id="session", message="hello")
        agent.delay.side_effect = RuntimeError(SENTINEL)
        result = asyncio.run(service.chat(request))
        payload = self.assert_private(result)
        self.assertEqual(result.status_code, 500)
        self.assertEqual(payload["stage"], "error")
        self.assertFalse(payload["is_processing"])
        agent.delay.side_effect = None
        agent.delay.return_value = SimpleNamespace(id="task")
        result = asyncio.run(service.chat(request))
        self.assertEqual(result["task_id"], "task")
        self.assertTrue(result["is_processing"])

    def test_status_exception_and_failed_task_are_private(self):
        service, agent = load_service()
        request = SimpleNamespace(session_id="session", task_id="task")
        agent.AsyncResult.side_effect = RuntimeError(SENTINEL)
        result = asyncio.run(service.check_result_status(request))
        self.assert_private(result)
        self.assertEqual(result.status_code, 500)
        agent.AsyncResult.side_effect = None
        agent.AsyncResult.return_value = SimpleNamespace(state="FAILURE", result=RuntimeError(SENTINEL))
        payload = self.assert_private(asyncio.run(service.check_result_status(request)))
        self.assertEqual(payload["stage"], "error")
        self.assertFalse(payload["is_processing"])

    def test_recording_failure_returns_controlled_error(self):
        service, _ = load_service()
        service._browser_recording.side_effect = RuntimeError(SENTINEL)
        result = asyncio.run(service.check_result_status(SimpleNamespace(session_id="session")))
        self.assertEqual(result.status_code, 500)
        self.assertIsNone(self.assert_private(result)["browser_recording_path"])

    def test_status_success_and_pending_preserve_contract(self):
        service, agent = load_service()
        request = SimpleNamespace(session_id="session", task_id="task")
        agent.AsyncResult.return_value = SimpleNamespace(state="PENDING")
        self.assertTrue(asyncio.run(service.check_result_status(request))["is_processing"])
        expected = {"session_id": "session", "response": "ready"}
        agent.AsyncResult.return_value = SimpleNamespace(state="SUCCESS", result=expected)
        self.assertEqual(asyncio.run(service.check_result_status(request)), expected)

    def test_optimizer_logs_escape_control_characters(self):
        import logging
        tree = ast.parse((ROOT / "awesome_agent_skills/self-improving-agent-skills/backend/app.py").read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == "info"
                 and node.args and isinstance(node.args[0], ast.Constant)
                 and str(node.args[0].value).startswith(("Starting optimization for session", "Callback event:"))]
        logger = Mock()
        scope = {"logger": logger, "session_id": "abc\r\nFORGED\x1b[31m",
                 "event": {"type": "done\r\nFORGED\x1b[31m"}, "json": json}
        for call in calls:
            exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.Expr(value=call)], type_ignores=[])), "log_sink", "exec"), scope)
            args = logger.info.call_args.args
            message = logging.LogRecord("test", 20, "", 0, args[0], args[1:], None).getMessage()
            for control in ("\r", "\n", "\x1b"):
                self.assertNotIn(control, message)
            self.assertIn("FORGED", message)

    def test_url_extractors_keep_queries_but_stop_at_markup(self):
        paths = [
            "ai_agent_framework_crash_course/google_adk_crash_course/4_tool_using_agent/4_2_function_tools/utility_agent/tools.py",
            "advanced_ai_agents/multi_agent_apps/agent_teams/ai_real_estate_agent_team/ai_real_estate_agent_team.py",
            "advanced_ai_agents/multi_agent_apps/agent_teams/ai_real_estate_agent_team/local_ai_real_estate_agent_team.py",
        ]
        url = "https://example.com/property-list?id=2&ref=a%20b#photos"
        for path in paths:
            tree = ast.parse((ROOT / path).read_text())
            pattern = next(node.value for node in ast.walk(tree)
                           if isinstance(node, ast.Constant) and isinstance(node.value, str)
                           and node.value.startswith("http[s]?://"))
            with self.subTest(path=path):
                self.assertEqual(re.findall(pattern, url + '<tag>'), [url])
                self.assertEqual(re.findall(pattern, "http://example.com/path"), ["http://example.com/path"])


if __name__ == "__main__":
    unittest.main()
