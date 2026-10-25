# Dependency refresh, October 25, 2026

This refresh updates the dependency graphs introduced by the latest catalog synchronization. It retains the examples and their provider integrations. Production builds and offline agent construction are checked by `generative-runtime.yml`; these checks do not call paid providers or certify live deployments.

The MCP builder now includes the actual upstream CopilotKit logo instead of an unresolved Git LFS pointer. The downloaded bytes match the pointer's SHA-256 (`4f3988438ee1892802f510cb61a264c8493267f4aa62ee31265aa13d22e2e8b7`), retrieved from the original CopilotKit `examples/showcases/open-mcp-client/apps/web/app/image.png` asset. Its archive extraction still rejects parent-relative paths and escaping links. Local archive regression tests cover normal merging and both rejection cases.

The Shadcn agent updates LangChain, LangGraph and AG-UI together. The obsolete message-tracking monkey patch was removed because the current upstream implementation handles cleared messages and concurrent lanes. The remaining checkpoint adapter forwards the new optional configuration argument. Checkpoint eviction calls the upstream thread-deletion API so channel blobs and pending writes are deleted along with checkpoint metadata. Regression tests cover lane isolation, cleared messages, checkpoint configuration and full payload cleanup through both synchronous and asynchronous checkpoint writes.

## Remaining upstream compatibility constraints

These are not waived, suppressed or counted as fixed:

- Current CopilotKit and AG-UI graphs retain Zod 3 dependencies. The constrained-collection advisory is fixed in Zod 4.6.6; direct examples use Zod 4.6.7, but forcing every transitive Zod 3 consumer across the major boundary requires additional schema/runtime migration.
- The MCP builder retains older `@ai-sdk/provider-utils` through upstream integrations. Its remaining audit findings require a compatible provider-adapter migration.
- Latest browser-use 0.13.11 pins vulnerable aiohttp, AnyIO, MCP, Pillow and pypdf versions. Its requirements and uv manifest now agree on browser-use 0.13.11; other resolvable packages were refreshed. Those exact upstream pins remain visible.
- Google ADK constrains OpenTelemetry below the patched API release. The financial-coach graph retains that upstream constraint. Release Radar stays on the compatible Google ADK 1.x line, with a compatible FastAPI release.
- The older Motia streaming-chatbot example is not migrated by this change; its Zod 3 dependency remains a separate compatibility task.

Local audits are package/advisory snapshots. GitHub alert closure must be checked after the merged dependency graph is processed. Passing compilation, mocked tests or offline graph construction is not evidence of real provider, browser-session, E2B sandbox or deployment acceptance.
