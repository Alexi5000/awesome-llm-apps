"""TripCraft plan API routes must authenticate the caller and scope every plan
lookup to the caller's userId (source contract; the Next.js app has no test runner)."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "advanced_ai_agents/multi_agent_apps/agent_teams/ai_travel_planner_agent_team"
CLIENT = APP / "client/app/api"


class TripCraftOwnershipTests(unittest.TestCase):
    def handlers(self, relative):
        source = (CLIENT / relative).read_text()
        parts = re.split(r"export async function (GET|POST|DELETE)", source)
        return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}

    def test_every_plan_handler_requires_a_session_before_database_access(self):
        for relative in ["plans/route.ts", "plans/[id]/route.ts", "plans/[id]/retry/route.ts", "plan/submit/route.ts"]:
            for method, body in self.handlers(relative).items():
                with self.subTest(route=relative, method=method):
                    session = body.find("getSessionUserId()")
                    self.assertGreater(session, -1)
                    self.assertIn("unauthorizedResponse()", body)
                    first_db = body.find("prisma.")
                    self.assertTrue(first_db == -1 or session < first_db)

    def test_plan_lookups_are_owner_scoped(self):
        for relative in ["plans/route.ts", "plans/[id]/route.ts", "plans/[id]/retry/route.ts"]:
            source = (CLIENT / relative).read_text()
            with self.subTest(route=relative):
                self.assertNotIn("findUnique", source)
                for lookup in re.findall(r"prisma\.tripPlan\.find\w+\(\{\s*where: \{([^}]*)\}", source):
                    self.assertIn("userId", lookup)

    def test_submit_binds_creator_and_backend_calls_carry_internal_token(self):
        submit = (CLIENT / "plan/submit/route.ts").read_text()
        self.assertNotIn("userId: null", submit)
        self.assertRegex(submit, r"\n\s+userId\n")
        for relative in ["plan/submit/route.ts", "plans/[id]/retry/route.ts"]:
            self.assertIn("headers: backendHeaders()", (CLIENT / relative).read_text())

    def test_retry_error_path_only_touches_verified_plan(self):
        retry = (CLIENT / "plans/[id]/retry/route.ts").read_text()
        self.assertNotIn("(await params).id", retry)
        self.assertIn("if (ownedPlanId)", retry)

    def test_backend_trigger_route_requires_internal_caller(self):
        router = (APP / "backend/router/plan.py").read_text()
        self.assertIn("dependencies=[Depends(require_internal_caller)]", router)


if __name__ == "__main__":
    unittest.main()
