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
