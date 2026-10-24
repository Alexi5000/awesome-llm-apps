"""Self-improving skill optimizer: per-optimizer credentials and real stop semantics.

Google ADK is replaced with small stubs so the test runs with only the standard
library, pydantic and fastapi installed.
"""

import ast
import asyncio
import importlib.util
import logging
import os
import re
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "agent_skills/self-improving-agent-skills/backend"
DISPATCHED = []


class Gemini:
    def __init__(self, model, client_kwargs=None):
        self.model = model
        self.client_kwargs = client_kwargs or {}


class Agent:
    def __init__(self, name, model, instruction="", output_schema=None):
        self.name = name
        self.model = model


class Runner:
    def __init__(self, agent, app_name, session_service):
        self.agent = agent

    async def run_async(self, user_id, session_id, new_message):
        DISPATCHED.append((self.agent.name, self.agent.model.client_kwargs.get("api_key"),
                           os.environ.get("GOOGLE_API_KEY")))
        yield SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(text='{"results": []}')]))


class InMemorySessionService:
    async def create_session(self, app_name, user_id):
        return SimpleNamespace(id=user_id)


def stub_modules():
    def module(name, **attrs):
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        return mod

    genai_types = module("google.genai.types", Content=lambda **kw: kw, Part=lambda **kw: kw)
    return {
        "google": module("google"),
        "google.adk": module("google.adk"),
        "google.adk.agents": module("google.adk.agents", Agent=Agent),
        "google.adk.models": module("google.adk.models", Gemini=Gemini),
        "google.adk.runners": module("google.adk.runners", Runner=Runner),
        "google.adk.sessions": module("google.adk.sessions", InMemorySessionService=InMemorySessionService),
        "google.genai": module("google.genai", types=genai_types),
        "google.genai.types": genai_types,
    }


def load_optimizer():
    with patch.dict(sys.modules, stub_modules()):
        spec = importlib.util.spec_from_file_location("cf_adk_optimizer", BACKEND / "adk_optimizer.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


optimizer_module = load_optimizer()


def load_app_handlers(optimizer_cls):
    tree = ast.parse((BACKEND / "app.py").read_text())
    names = {"start_optimization", "stop_optimization", "resolve_model", "default_model"}
    nodes = [n for n in tree.body if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef)) and n.name in names]
    for node in nodes:
        node.decorator_list = []
    scope = {
        "asyncio": asyncio, "HTTPException": HTTPException, "StartRequest": object,
        "SkillOptimizer": optimizer_cls, "OptimizationStopped": optimizer_module.OptimizationStopped,
        "logger": logging.getLogger("skill-stop-test"), "traceback": SimpleNamespace(format_exc=lambda: "tb"),
        "sessions": {}, "Optional": __import__("typing").Optional, "os": os,
        "DEFAULT_MODEL": optimizer_module.DEFAULT_MODEL,
        "MODEL_NAME_RE": re.compile(r"[A-Za-z0-9][A-Za-z0-9._\-/]{0,127}"),
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(BACKEND / "app.py"), "exec"), scope)
    return scope


SCENARIOS = [{"id": 1, "input": "do it"}]
EVALS = [{"id": 1, "question": "ok?"}]


class CredentialBoundaryTests(unittest.TestCase):
    def setUp(self):
        DISPATCHED.clear()

    def test_each_optimizer_dispatches_with_its_own_key_without_touching_environment(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "operator-key"}):
            first = optimizer_module.SkillOptimizer(api_key="key-a")
            second = optimizer_module.SkillOptimizer(api_key="key-b")
            self.assertEqual(os.environ["GOOGLE_API_KEY"], "operator-key")

            async def interleave():
                await second._ask(second.executor, "b")
                await first._ask(first.executor, "a")
                await second._ask(second.mutator, "b")
                await first._ask(first.analyst, "a")

            asyncio.run(interleave())
        self.assertEqual([key for _, key, _ in DISPATCHED], ["key-b", "key-a", "key-b", "key-a"])
        self.assertTrue(all(env == "operator-key" for _, _, env in DISPATCHED))
        for optimizer, key in [(first, "key-a"), (second, "key-b")]:
            for agent in (optimizer.executor, optimizer.analyst, optimizer.mutator):
                self.assertEqual(agent.model.client_kwargs, {"api_key": key, "vertexai": False})

    def test_source_no_longer_writes_process_environment(self):
        source = (BACKEND / "adk_optimizer.py").read_text()
        self.assertNotIn("os.environ", source)


class StopSemanticsTests(unittest.TestCase):
    def setUp(self):
        DISPATCHED.clear()

    def test_should_stop_prevents_further_model_calls(self):
        optimizer = optimizer_module.SkillOptimizer(api_key="key")
        stop_after = 3

        def should_stop():
            return len(DISPATCHED) >= stop_after

        with self.assertRaises(optimizer_module.OptimizationStopped):
            asyncio.run(optimizer.optimize({"SKILL.md": "# s"}, SCENARIOS, EVALS, max_rounds=5,
                                           should_stop=should_stop))
        self.assertEqual(len(DISPATCHED), stop_after)

    def test_stop_cancels_in_flight_run_and_never_reports_complete(self):
        events = {}

        class BlockingOptimizer:
            def __init__(self, api_key, model):
                self.calls_after_release = 0

            async def optimize(self, skill_files, scenarios, evals, max_rounds, callback, should_stop):
                events["started"].set()
                await events["release"].wait()
                if not should_stop():
                    self.calls_after_release += 1
                await callback({"type": "complete", "data": {"improved_skill_md": "stale"}})
                return {"baseline_score": 0, "final_score": 100, "improved_skill_md": "stale"}

        scope = load_app_handlers(BlockingOptimizer)
        session = {"scenarios": SCENARIOS, "evals": EVALS, "skill_files": {"SKILL.md": "# s"},
                   "experiments": [], "status": "configured"}
        scope["sessions"]["s1"] = session

        async def scenario():
            events["started"] = asyncio.Event()
            events["release"] = asyncio.Event()
            await scope["start_optimization"]("s1", SimpleNamespace(gemini_api_key="k", max_rounds=1, model=None))
            await events["started"].wait()
            task = session["task"]
            result = await scope["stop_optimization"]("s1")
            self.assertEqual(result, {"status": "stopped"})
            self.assertTrue(session["stop_event"].is_set())
            events["release"].set()
            await asyncio.gather(task, return_exceptions=True)
            return task

        task = asyncio.run(scenario())
        self.assertTrue(task.done())
        self.assertEqual(session["status"], "stopped")
        self.assertNotIn("final_result", session)
        self.assertNotIn("current_skill_md", session)

    def test_restart_after_stop_is_not_overwritten_by_old_run(self):
        class ReturningOptimizer:
            def __init__(self, api_key, model):
                pass

            async def optimize(self, skill_files, scenarios, evals, max_rounds, callback, should_stop):
                await asyncio.sleep(0)
                await callback({"type": "complete", "data": {"improved_skill_md": "new"}})
                return {"baseline_score": 0, "final_score": 1, "improved_skill_md": "new"}

        scope = load_app_handlers(ReturningOptimizer)
        session = {"scenarios": SCENARIOS, "evals": EVALS, "skill_files": {"SKILL.md": "# s"},
                   "experiments": [], "status": "configured", "final_result": {"improved_skill_md": "old"}}
        scope["sessions"]["s1"] = session

        async def scenario():
            await scope["start_optimization"]("s1", SimpleNamespace(gemini_api_key="k", max_rounds=1, model=None))
            await session["task"]

        asyncio.run(scenario())
        self.assertEqual(session["status"], "complete")
        self.assertEqual(session["final_result"]["improved_skill_md"], "new")


if __name__ == "__main__":
    unittest.main()
