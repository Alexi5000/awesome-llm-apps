## Purpose

Describe the fork-specific improvement and the learner, developer, or operator outcome it supports.

## Scope and attribution

- [ ] This change is scoped to the paths described below.
- [ ] Upstream authorship, licensing, and contributor credit are preserved.
- [ ] I identified whether the change should also be proposed upstream.

## Verification

- [ ] `python3 -m unittest discover -s tests -p "test_*.py"`
- [ ] `python3 -m compileall -q starter_ai_agents advanced_ai_agents advanced_llm_apps mcp_ai_agents rag_tutorials voice_ai_agents`
- [ ] I followed the affected example’s README or recorded why runtime verification was not appropriate.

## Agent and automation safety

- [ ] No secrets, tokens, customer data, or private prompts are included.
- [ ] Provider, framework, tool-access, and external-side-effect assumptions are documented.
- [ ] Security-sensitive concerns follow `SECURITY.md`, not a public discussion.
