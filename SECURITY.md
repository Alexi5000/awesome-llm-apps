# Security policy

## Reporting a vulnerability

Do **not** report security vulnerabilities in public issues, pull requests, or discussions. Send a concise private report through [TechTide AI](https://techtideai.io), including the affected example or path, prerequisites, reproduction steps, potential impact, and any suggested mitigation.

Reports involving leaked credentials, tool authorization, prompt injection, unsafe browser or system actions, dependency compromise, cross-tenant data exposure, retrieval-data leakage, or vulnerable deployment configuration are in scope. Please avoid including real secrets or customer data in the report; redact sensitive values and provide a safe reproduction where possible.

Maintainers will acknowledge credible reports, assess severity and scope, coordinate a fix, and share disclosure timing when appropriate. Please allow a reasonable remediation period before public disclosure.

## Secure use of examples

Examples in this repository may call hosted models, external tools, browsers, databases, or third-party APIs. Treat every example as code requiring review before execution. Use least-privilege credentials, isolate test data, confirm any externally consequential action, and review current provider documentation before deploying an adapted workflow.

For non-security questions, use [SUPPORT.md](./SUPPORT.md). For contribution workflow, use [CONTRIBUTING.md](./CONTRIBUTING.md).
