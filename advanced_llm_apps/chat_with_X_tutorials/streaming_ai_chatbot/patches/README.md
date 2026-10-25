# Legacy Zod collection limits

The pinned Motia 0.2.2 framework and OpenAI 4 client consume Zod 3. Replacing it
with Zod 4 breaks the legacy schema contracts. This example retains those APIs
and adapts upstream Zod commit
https://github.com/colinhacks/zod/commit/a0ebf970f2d752e5f58527cd2942ff48be4f46bd
to the legacy parser in response to GHSA-mrhx-c7xc-m3w5.

Arrays exceeding `.max()`/`.length()` and sets exceeding `.max()`/`.size()` fail
before element parsing and later refinements. Valid inputs, transforms, async
checks, smaller-input errors, preprocessors, unions and recovery stay covered.
Unbounded collections, maps without size constraints, and Zod 3's bundled old
v4 export are not protected by this narrow mitigation. Do not dismiss the
original-version advisory or call the dependency graph clean.

Use `npm ci` with the committed lockfile. Its postinstall runs the zero-dependency
`scripts/patch-zod.cjs`. When intentionally skipping scripts, run
`npm ci --ignore-scripts` followed by `npm run patch:zod`. Development, type
generation and build commands also verify the patch. Copy the scripts, patches,
and lockfile along with the example.

The JSON patch manifest identifies official npm artifacts by integrity and every
changed source/CJS/ESM file by exact before/after SHA-256. The applicator preflights
every locked installation, rejects unknown or linked files, and performs atomic
per-file replacements. Repeated execution is idempotent. Package identities,
declarations, and licenses remain unchanged.

`npm test` covers collection rejection and patch-integrity failure cases, Motia's
actual JSON Schema converter and source handlers, and OpenAI's real streaming
client against a local fake provider. Tests make no live provider request and
require no credential. Motia type generation, typecheck and production build run
in CI. Remove the patch only after a supported consumer migration preserves this
coverage and no longer requires the vulnerable package.

The locked raw npm audit still reports the original Zod advisory and an older
UUID dependency from node-cron. Those are not suppressed by this patch.
