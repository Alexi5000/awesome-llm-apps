import asyncio
import importlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class RuntimeTests(unittest.TestCase):
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
        cls.team = importlib.import_module("agents.team").trip_planning_team
        cls.api = importlib.import_module("api.app").app

    def test_team_retains_six_members(self):
        self.assertEqual(len(self.team.members), 6)
        self.assertFalse(self.team.telemetry)

    def test_health_endpoint(self):
        import httpx

        async def request():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.api), base_url="http://test"
            ) as client:
                return await client.get("/api/health")

        response = asyncio.run(request())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_scrape_markdown_contract(self):
        module = importlib.import_module("tools.scrape")
        with patch.object(module.app, "scrape_url", return_value=SimpleNamespace(markdown="# Result")) as scrape:
            self.assertEqual(module.scrape_website.entrypoint("https://example.com"), "# Result")
        scrape.assert_called_once_with(
            "https://example.com", formats=["markdown"], wait_for=30000, timeout=60000
        )

    def test_flight_request_contract(self):
        module = importlib.import_module("tools.google_flight")
        with patch.object(module, "get_flights", return_value=SimpleNamespace(flights=["flight"])) as flights:
            self.assertEqual(module.get_google_flights.entrypoint("BOM", "DEL", "2027-01-01"), ["flight"])
        self.assertEqual(flights.call_args.kwargs["flight_data"][0].from_airport, "BOM")

    def test_structured_output_cleaning(self):
        module = importlib.import_module("agents.structured_output")
        self.assertEqual(module.clean_json_string('```json\n{"ok": true}\n```'), '{"ok": true}')


if __name__ == "__main__":
    unittest.main()
