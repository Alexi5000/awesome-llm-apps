# Braces security backport

This is braces 3.0.3 with the depth and cyclic-parent guards from upstream proposal https://github.com/micromatch/braces/pull/72 at commit 28d440b5dd449dbf1fe6f3506cf94ecca4d02660. The proposal was closed without an official release. This is a maintained local backport, not an upstream patched version. The original package name, version, and MIT license are retained.

The complete proposal test suite passed locally: 904 tests on Node 22.22.2. Normal expansion, fractional depth limits, malformed input, direct AST depth, and parent cycles are covered by that suite. Remove this override only when a supported upstream release or compatible replacement contains these protections. Owner: repository maintainer. Review by 2026-11-18.

## Negotiation frontend integration

The application's Tailwind3 toolchain reaches braces through fast-glob/micromatch and Chokidar. The npm override resolves every braces copy to the included archive; `scripts/verify-braces.cjs` checks lockfile sources, installed-source hashes, normal expansion and recursion boundaries before each production build. The frontend regression suite additionally exercises Tailwind file discovery/CSS generation and actual micromatch/fast-glob consumers. The unmodified package overflows the stack for the4000-level micromatch fixture; this backport rejects it with a bounded depth error.

GHSA-vfj7-8cjw-p6xm has no patched registry release. The name/version are deliberately unchanged. Raw npm audit still reports five high entries across braces and its parent chain; this change is a source mitigation, not an upstream advisory closure or a claim that npm audit is clean. No advisory is ignored or dismissed.
