import asyncio
import importlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BODY = {"trip_plan_id": "victim-plan", "travel_plan": {}}


class PlanTriggerAuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for guard in (
            patch.dict(os.environ, {
                "OPENAI_API_KEY": "offline-test",
                "OPENROUTER_API_KEY": "offline-test",
                "EXA_API_KEY": "offline-test",
                "FIRECRAWL_API_KEY": "offline-test",
            }, clear=True),
            patch("socket.socket.connect", side_effect=AssertionError("Network is disabled")),
            patch("dotenv.load_dotenv", return_value=False),
        ):
            guard.start()
            cls.addClassCleanup(guard.stop)
        cls.api = importlib.import_module("api.app").app
        cls.plan = importlib.import_module("router.plan")

    def post(self, headers=None, client=("127.0.0.1", 50000)):
        import httpx

        create = AsyncMock(return_value=SimpleNamespace(id=1))
        generate = AsyncMock(return_value="plan")

        async def request():
            transport = httpx.ASGITransport(app=self.api, client=client)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
                response = await http.post("/api/plan/trigger", json=BODY, headers=headers or {})
                await asyncio.sleep(0)
                return response

        with patch.object(self.plan, "create_plan_task", create), \
                patch.object(self.plan, "update_task_status", AsyncMock()), \
                patch.object(self.plan, "generate_travel_plan", generate):
            response = asyncio.run(request())
        return response, create

    def test_remote_caller_is_rejected_without_configured_token(self):
        response, create = self.post(client=("203.0.113.9", 50000))
        self.assertEqual(response.status_code, 403)
        create.assert_not_called()

    def test_loopback_caller_is_admitted_for_local_development(self):
        response, create = self.post()
        self.assertEqual(response.status_code, 200)
        create.assert_awaited_once()

    def test_configured_token_is_required_even_from_loopback(self):
        with patch.dict(os.environ, {"TRIPCRAFT_INTERNAL_API_TOKEN": "s3cret"}):
            for headers in [None, {"X-TripCraft-Internal-Token": "wrong"}]:
                with self.subTest(headers=headers):
                    response, create = self.post(headers=headers)
                    self.assertEqual(response.status_code, 401)
                    create.assert_not_called()
            response, create = self.post(headers={"X-TripCraft-Internal-Token": "s3cret"},
                                         client=("203.0.113.9", 50000))
            self.assertEqual(response.status_code, 200)
            create.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
