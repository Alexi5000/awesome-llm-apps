import ast
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.function import FunctionCall
from jsonschema import ValidationError
from openai import OpenAI
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from teaching_tools import DOCUMENT_ACTIONS, google_docs_tools


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        network = patch("socket.socket.connect", side_effect=AssertionError("Unexpected live network access"))
        network.start()
        self.addCleanup(network.stop)
        telemetry = patch.dict(os.environ, {"AGNO_TELEMETRY": "false"})
        telemetry.start()
        self.addCleanup(telemetry.stop)
        self.executions = []
        self.schemas = []
        for slug in DOCUMENT_ACTIONS:
            self.schemas.append({
                "slug": slug, "name": slug, "description": "Create or update a lesson document",
                "input_parameters": json.loads((Path(__file__).parent / (slug.lower() + ".json")).read_text())["input_parameters"],
                "output_parameters": {}, "available_versions": ["20261001_00"],
                "deprecated": {"is_deprecated": False, "displayName": None},
                "is_deprecated": False, "no_auth": False, "scopes": [], "tags": [],
                "toolkit": {"slug": "googledocs", "name": "Google Docs", "logo": ""},
                "version": "20261001_00",
            })
        self.composio_http = httpx.Client(transport=httpx.MockTransport(self.composio_request))
        self.openai_http = httpx.Client(transport=httpx.MockTransport(self.openai_request))
        self.addCleanup(self.composio_http.close)
        self.addCleanup(self.openai_http.close)
        self.provider_error = False

    def composio_request(self, request):
        self.assertEqual(request.headers["x-api-key"], "offline-key")
        if request.method == "GET" and request.url.path.endswith("/tools"):
            self.assertEqual(set(request.url.params["tool_slugs"].split(",")), set(DOCUMENT_ACTIONS))
            return httpx.Response(200, json={"items": self.schemas, "total_pages": 1, "current_page": 1})
        if request.method == "POST" and "/tools/execute/" in request.url.path:
            payload = json.loads(request.content)
            self.executions.append((request.url.path, payload))
            return httpx.Response(200, json={"data": {"documentId": "lesson-123"},
                "successful": not self.provider_error, "error": "connection expired" if self.provider_error else None,
                "log_id": "offline-log"})
        raise AssertionError(f"Unexpected Composio request {request.method} {request.url}")

    def openai_request(self, request):
        self.assertTrue(request.url.path.endswith("/chat/completions"))
        payload = json.loads(request.content)
        self.assertEqual(payload["model"], "gpt-4o-mini")
        self.assertIn(DOCUMENT_ACTIONS[0], [x["function"]["name"] for x in payload["tools"]])
        tool_messages = [m for m in payload["messages"] if m["role"] == "tool"]
        if len(tool_messages) == 1:
            created = ast.literal_eval(tool_messages[0]["content"])
            self.assertEqual(created["data"]["documentId"], "lesson-123")
            message = {"role": "assistant", "content": None, "tool_calls": [{"id": "call_update", "type": "function",
                "function": {"name": DOCUMENT_ACTIONS[1], "arguments": json.dumps(self.update_arguments())}}]}
            finish = "tool_calls"
        elif len(tool_messages) == 2:
            message = {"role": "assistant", "content": "Lesson: https://docs.google.com/document/d/lesson-123/edit"}
            finish = "stop"
        else:
            message = {"role": "assistant", "content": None, "tool_calls": [{"id": "call_create", "type": "function",
                "function": {"name": DOCUMENT_ACTIONS[0], "arguments": json.dumps({"title": "Python lesson", "text": "Lesson introduction"})}}]}
            finish = "tool_calls"
        return httpx.Response(200, json={"id": "chat-offline", "object": "chat.completion", "created": 1,
            "model": "gpt-4o-mini", "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})

    def update_arguments(self):
        return {"document_id": "lesson-123", "edit_docs": [{"insertText": {"endOfSegmentLocation": {}, "text": "Practice exercise"}}]}

    def tools(self, user="alice"):
        return google_docs_tools("offline-key", user, http_client=self.composio_http)

    def test_real_sdk_schema_and_user_scoped_execution(self):
        for user in ("alice", "bob"):
            tools = self.tools(user)
            for tool in tools:
                arguments = {"title": "lesson"} if tool.name == DOCUMENT_ACTIONS[0] else self.update_arguments()
                call = FunctionCall(function=tool, arguments=arguments)
                result = call.execute()
                self.assertTrue(result.status == "success")
                self.assertEqual(self.executions[-1][1]["user_id"], user)
                self.assertEqual(self.executions[-1][1]["arguments"], arguments)
        self.assertEqual(len(self.executions), 4)

    def test_invalid_arguments_do_not_call_api(self):
        tool = self.tools()[0]
        with self.assertRaises(ValidationError):
            tool.entrypoint(title=4)
        self.assertEqual(self.executions, [])

    def test_tool_arguments_cannot_replace_execution_user(self):
        self.tools("alice")[0].entrypoint(title="lesson", user_id="bob", connected_account_id="another-account")
        payload = self.executions[-1][1]
        self.assertEqual(payload["user_id"], "alice")
        self.assertNotIn("connected_account_id", payload)

    def test_provider_failure_is_preserved(self):
        self.provider_error = True
        result = self.tools()[0].entrypoint(title="lesson")
        self.assertFalse(result["successful"])
        self.assertEqual(result["error"], "connection expired")

    def test_missing_user_and_missing_tools_fail_closed(self):
        with self.assertRaises(ValueError):
            self.tools(" ")
        self.schemas.pop()
        with self.assertRaises(ValueError):
            self.tools()
        self.assertEqual(self.executions, [])

    def test_real_agent_tool_roundtrip(self):
        model = OpenAIChat(id="gpt-4o-mini", client=OpenAI(api_key="offline-key", http_client=self.openai_http))
        response = Agent(model=model, tools=self.tools(), telemetry=False).run("Create a lesson")
        self.assertIn("https://docs.google.com/document", response.content)
        self.assertEqual(len(self.executions), 2)
        self.assertEqual(self.executions[1][1]["arguments"], self.update_arguments())

    def test_streamlit_four_agents_and_credentials(self):
        app_path = Path(__file__).resolve().parents[1] / "teaching_agent_team.py"
        client = OpenAI(api_key="offline-key", http_client=self.openai_http)
        with patch("teaching_tools.Composio", wraps=__import__("composio").Composio) as factory, patch.object(OpenAIChat, "get_client", return_value=client):
            factory.side_effect = lambda **kwargs: __import__("composio").Composio(**kwargs, http_client=self.composio_http)
            app = AppTest.from_file(str(app_path), default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            for item in app.text_input:
                item.set_value("alice" if item.label == "Composio user ID" else "offline-key")
            app.run()
            self.assertFalse(app.exception)
            next(x for x in app.text_input if "topic" in x.label).set_value("Python")
            app.button[0].click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(len(self.executions), 8)
            output = "\n".join(x.value for x in app.markdown)
            for label in ("Professor Document", "Academic Advisor Document", "Research Librarian Document", "Teaching Assistant Document"):
                self.assertIn(label, output)
            self.assertTrue(all(p[1]["user_id"] == "alice" for p in self.executions))


if __name__ == "__main__":
    unittest.main()
