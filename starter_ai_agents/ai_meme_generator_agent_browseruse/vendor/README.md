# Maintained browser dependency compatibility builds

These MIT source packages preserve the published browser-use 0.13.11 and
browser-harness 0.1.13 runtime files and licenses byte-for-byte. Local build
versions are `0.13.11+techtide.1` and `0.1.13+techtide.1`. Only dependency
metadata changes: aiohttp 3.14.4, AnyIO 4.14.2, MCP 2.2.0, Pillow 13.0.0 and
pypdf 6.21.2 replace the vulnerable exact pins, including optional MCP/eval
pins. Browser-use's exact harness requirement accepts its matching local build.

Each package records its source-distribution URL/SHA256, upstream metadata,
exact metadata replacements, and hashes of every preserved source/resource
file in `PROVENANCE.json`. Tests verify those files and metadata. No resolver
override is used. Keep this vendor directory with the app when exporting it;
both pip requirements and uv source references use its relative paths.

The fork maintainers own these compatibility builds. The ordinary app tests
remain, supplemented by real headless Chromium navigation/input/download,
screenshot storage and Pillow rendering, browser-use PDF extraction, MP4
encoding/decoding, and local MCP protocol discovery/tool success/error tests.
They run with telemetry/cloud disabled, without provider credentials or calls.
CI exercises Python 3.11 with the uv lock and Python 3.12 with pip requirements.
This does not claim live-provider, third-party-site, native macOS/Windows,
cloud-browser, or every optional integration acceptance.

Remove these local sources once released packages accept the fixed dependency
versions, after rerunning both installation paths and the same real runtime
contracts. Update source hashes only after checking changes against the
published source archive. Generated setuptools build/egg-info files are ignored.
