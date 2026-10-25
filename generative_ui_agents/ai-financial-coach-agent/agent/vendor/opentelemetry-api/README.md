# OpenTelemetry API security backport

This maintained local package is OpenTelemetry API 1.44.0 with the exact
upstream fix for [GHSA-xcq7-p3pf-p88h](https://github.com/advisories/GHSA-xcq7-p3pf-p88h).
`upstream.patch` comes from commit
[`d5224bf4ffdf2aee1b592ad238dcc32ca957f26b`](https://github.com/open-telemetry/opentelemetry-python/commit/d5224bf4ffdf2aee1b592ad238dcc32ca957f26b).
It makes direct tracestate parsing linear and rejects combined propagation
headers above 8,192 characters while preserving the parent trace.

Google ADK 2.13.0 caps OpenTelemetry at 1.44.0. This source package preserves
that API and its dependencies, identifies the backport as
`1.44.0+techtide.1`, and satisfies the SDK's exact 1.44.0 requirement without
an override. The two patched modules are the only changed runtime files.
The upstream Apache-2.0 license, original wheel hashes and per-file hashes
are recorded in `provenance.json`. The upstream 1.44.0 tests are retained,
with the security commit's test additions in `upstream-tests.patch`.

Use `uv sync --frozen` from the agent directory in a complete checkout.
CI runs the upstream tracestate tests, real propagation and SDK tests,
provenance validation, and the existing offline ADK construction check.
This is a code mitigation; the original-version advisory may remain open.
The fork maintainers own the backport. Remove it when ADK supports the
released fixed API (1.45.1 or later), after the same compatibility checks.
