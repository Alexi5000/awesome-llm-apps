# Legacy provider response-body limit

`provider-utils-2.2.8.patch` backports the response-handler protection from
https://github.com/vercel/ai/commit/6a436e31d247d678ddaedfc6f61e73ac0595e4b4
for GHSA-866g-f22w-33x8. Both published CommonJS and ESM entrypoints are patched.

The three JSON/status handlers reject declared or streamed bodies over the
upstream 2 GiB ceiling and cancel their readers. Empty bodies, JSON validation,
provider errors, and synchronous `safeParseJSON` keep their existing behavior.
This ceiling is the upstream mitigation, not a guarantee that a process with
less available memory can safely accept every response below it.

The legacy Mastra adapter still depends on `@ai-sdk/ui-utils`, whose latest
1.2.11 release requires provider-utils 2.2.8. Forcing version 3 changes
`safeParseJSON` to an async API. This patch preserves the published package
identity and license and applies through pnpm's integrity-checked patch support.

GitHub and npm may continue reporting the original version advisory. Do not
dismiss it or call the dependency graph clean. Remove the patch only after a
supported adapter migration eliminates this dependency and its runtime tests
pass. Run `pnpm test:provider-response-limits` after every dependency change.

## Legacy Zod collection limits

`zod@3.25.76.patch` and `zod@4.6.7.patch` adapt the early collection-size
rejection in https://github.com/colinhacks/zod/commit/a0ebf970f2d752e5f58527cd2942ff48be4f46bd
to the Zod 3 parser used by the legacy UI/provider adapters. The second patch
covers the `zod/v3` compatibility export inside Zod 4, not its current v4 parser.
Each patch updates both CommonJS and ESM runtime files and their TypeScript source.
Published package identities, declarations, and MIT licenses remain unchanged.

Arrays exceeding `.max()` or `.length()`, and sets exceeding `.max()` or `.size()`,
now fail before parsing their elements or running subsequent refinements. Their
existing size issue, custom message, and nested path are retained. Smaller inputs,
element transforms, asynchronous checks, preprocessors, union fallbacks, defaults,
and catch recovery retain their existing behavior. Zod 3 maps do not support a
built-in size constraint and are outside this patch.

This is a bounded-collection mitigation for GHSA-mrhx-c7xc-m3w5 in this example's
dependency tree, not a claim that all memory-exhaustion risks or all catalog
examples are fixed. Unbounded schemas still need application-specific input
limits; this patch does not invent a global collection limit. The older v4 API
bundled inside Zod 3 is outside this patch. The advisory remains open for the
original Zod 3 version and must not be dismissed on the basis of this mitigation.

Run `pnpm test:collection-limits` after dependency changes. The tests resolve the
actual legacy consumer dependencies, cover root and `/v3` entrypoints in both
module formats, and exercise real provider parsing and response validation.
Remove these patches only after the legacy consumers migrate to maintained,
compatible APIs with equivalent size-limit regression coverage.
