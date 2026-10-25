# Legacy Zod collection limits

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
actual AG-UI client dependencies, cover root and `/v3` entrypoints in both
module formats, and preserve valid collection parsing and recovery.
Remove these patches only after the legacy consumers migrate to maintained,
compatible APIs with equivalent size-limit regression coverage.
