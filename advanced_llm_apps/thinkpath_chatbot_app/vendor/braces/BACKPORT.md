# Braces security backport

Braces 3.0.3 with depth and cyclic-parent guards from upstream proposal https://github.com/micromatch/braces/pull/72 at commit 28d440b5dd449dbf1fe6f3506cf94ecca4d02660, reused byte-for-byte from this repository's negotiation frontend. Original name, version and MIT license remain. This is a local mitigation, not an officially patched upstream release.

The npm override applies to every braces copy. `npm run test:security` checks installed source hashes, lockfile archive sources, normal expansion, parser depth boundaries and direct AST depth, including the micromatch consumer. Production build runs the same guard. GHSA-vfj7-8cjw-p6xm remains reported by npm audit; no advisory is ignored or dismissed. Owner: repository maintainer. Review by 2026-11-18 and replace with a supported fixed release when available.
