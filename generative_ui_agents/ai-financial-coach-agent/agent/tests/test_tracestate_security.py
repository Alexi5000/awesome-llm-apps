import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import TraceState
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "opentelemetry-api"
PARENT = "00-12345678901234567890123456789012-1234567890123456-01"


class TelemetrySecurityTests(unittest.TestCase):
    def extract(self, headers):
        context = TraceContextTextMapPropagator().extract(
            {"traceparent": [PARENT], "tracestate": headers}
        )
        span = trace.get_current_span(context).get_span_context()
        self.assertEqual(span.trace_id, int("12345678901234567890123456789012", 16))
        self.assertEqual(span.span_id, int("1234567890123456", 16))
        self.assertTrue(span.trace_flags.sampled)
        return context, span

    def test_provenance(self):
        provenance = json.loads((VENDOR / "provenance.json").read_text())
        for name, expected in provenance["installed_files"].items():
            self.assertEqual(hashlib.sha256((VENDOR / name).read_bytes()).hexdigest(), expected, name)
        actual = {str(p.relative_to(VENDOR)) for p in (VENDOR / "opentelemetry").rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        self.assertEqual(actual | {"LICENSE"}, set(provenance["installed_files"]))
        changed = {name for name in provenance["original_files"] if provenance["original_files"][name] != provenance["installed_files"][name]}
        self.assertEqual(changed, {"opentelemetry/trace/span.py", "opentelemetry/trace/propagation/tracecontext.py"})
        self.assertEqual(hashlib.sha256((VENDOR / "tests/test_upstream_tracestate.py").read_bytes()).hexdigest(), provenance["patched_test_sha256"])

    def test_installed_backport_and_sdk(self):
        self.assertEqual(importlib.metadata.version("opentelemetry-api"), "1.44.0+techtide.1")
        self.assertEqual(importlib.metadata.version("opentelemetry-sdk"), "1.44.0")

    def test_upstream_entry_points(self):
        provenance = json.loads((VENDOR / "provenance.json").read_text())
        installed = {}
        for entry in importlib.metadata.distribution("opentelemetry-api").entry_points:
            installed.setdefault(entry.group, {})[entry.name] = entry.value
            self.assertIsNotNone(entry.load())
        self.assertEqual(installed, provenance["entry_points"])

    def test_explicit_provider_configuration(self):
        env = os.environ.copy()
        env.update(OTEL_PROPAGATORS="tracecontext,baggage", OTEL_PYTHON_CONTEXT="contextvars_context", OTEL_PYTHON_TRACER_PROVIDER="default_tracer_provider", OTEL_PYTHON_METER_PROVIDER="default_meter_provider")
        code = """from opentelemetry import baggage, propagate, trace, metrics
from opentelemetry.context import attach, detach
context = propagate.extract({'traceparent': '00-12345678901234567890123456789012-1234567890123456-01', 'tracestate': 'vendor=value', 'baggage': 'example=value'})
assert baggage.get_baggage('example', context) == 'value'
token = attach(context)
try:
    carrier = {}
    propagate.inject(carrier)
    assert carrier['tracestate'] == 'vendor=value'
    assert carrier['baggage'] == 'example=value'
    assert isinstance(trace.get_tracer_provider(), trace.NoOpTracerProvider)
    assert isinstance(metrics.get_meter_provider(), metrics.NoOpMeterProvider)
finally:
    detach(token)
"""
        result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_combined_header_limit_preserves_parent(self):
        cases = [["foo=1" + " " * 8188], ["foo=1" + " " * 4091, "bar=2" + " " * 4091]]
        for headers in cases:
            with self.subTest(lengths=list(map(len, headers))):
                with patch.object(TraceState, "from_header", side_effect=AssertionError("oversized header reached parser")):
                    _, span = self.extract(headers)
                self.assertEqual(len(span.trace_state), 0)

    def test_exact_header_limit_and_whitespace(self):
        cases = [["foo=1" + " " * 8187], ["foo=1" + " " * 4090, "bar=2" + " " * 4091], ["\tfoo=1,\tbar=2\t"]]
        for headers in cases:
            with self.subTest(lengths=list(map(len, headers))):
                _, span = self.extract(headers)
                self.assertEqual(span.trace_state["foo"], "1")

    def test_malformed_duplicate_and_empty_states(self):
        for headers in [["foo=1,foo=2"], ["bad==value"], [""], []]:
            with self.subTest(headers=headers):
                _, span = self.extract(headers)
                self.assertEqual(len(span.trace_state), 0)

    def test_direct_parser_has_no_quadratic_split(self):
        with patch("opentelemetry.trace.span.re.split", side_effect=AssertionError("regex split used")):
            self.assertEqual(dict(TraceState.from_header(["foo=1 , bar=2"])), {"foo": "1", "bar": "2"})

    def test_large_direct_headers_finish_in_bounded_time(self):
        code = """import logging
from opentelemetry.trace import TraceState
logging.disable(logging.CRITICAL)
for whitespace in (' ', '\\t'):
    assert not TraceState.from_header(['a=b' + whitespace * 100_000 + 'x'])
"""
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_sdk_export_retains_propagated_state(self):
        context, parent = self.extract(["vendor=value"])
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        try:
            with provider.get_tracer("compatibility").start_as_current_span("local", context=context):
                pass
            spans = exporter.get_finished_spans()
            self.assertEqual(len(spans), 1)
            self.assertEqual(spans[0].context.trace_id, parent.trace_id)
            self.assertEqual(spans[0].parent.span_id, parent.span_id)
            self.assertEqual(dict(spans[0].context.trace_state), {"vendor": "value"})
        finally:
            provider.shutdown()


if __name__ == "__main__":
    unittest.main()
