# Zod 3 collection-limit backport

`zod-collection-limits.json` records the official npm tarball integrity and exact
before/after SHA-256 hashes for each changed source, CommonJS and ESM file.
It adapts the early-size rejection in upstream commit
https://github.com/colinhacks/zod/commit/a0ebf970f2d752e5f58527cd2942ff48be4f46bd
for GHSA-mrhx-c7xc-m3w5 to Zod3.25.76 and the bundled `zod/v3` export in4.6.7.
The current Zod4 parser, declarations, identities and MIT licenses are unchanged.

Arrays above `.max()` or `.length()` and sets above `.max()` or `.size()` fail
before element parsing and subsequent refinements. Size messages and paths,
valid transforms, async parsing, preprocess, unions, defaults and catch recovery
are tested. Unbounded schemas still need application-specific limits. This is
not a complete memory-exhaustion defense or an advisory-closure claim.

Use this app's committed npm lockfile. `npm ci` applies the patch via postinstall;
when deliberately skipping lifecycle scripts, run `npm ci --ignore-scripts`
followed by `npm run patch:zod`. Build, development and start scripts verify the
patch too. Include `scripts/patch-zod.cjs`, `patches/` and `package-lock.json`
when copying the source application. Next standalone images are patched before
compilation and run their generated server directly. Docker build paths install
from the same lock and apply the patch explicitly.

The zero-dependency applicator checks every installed Zod path from the lock,
rejects unfamiliar artifacts, changed content and linked files, validates all
planned writes before mutation, then replaces each file atomically. Repeated
runs are idempotent. `npm run test:collection-limits` covers every installed root
and `/v3` CJS/ESM entrypoint, real CopilotKit schema conversion, Zod4 behavior,
and applicator failure cases. CI explicitly applies patches after ignored scripts.

Maintain this backport until legacy consumers support a fixed compatible release.
Review package updates and regenerate provenance deliberately; an unfamiliar
package fails closed. Keep the original advisory open until the affected version
is actually removed or a recognized fixed version is installed.
