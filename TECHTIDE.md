<div align="center">

# Awesome LLM Apps - TechTide AI Fork

[![Upstream](https://img.shields.io/badge/Upstream-Shubhamsaboo%2Fawesome--llm--apps-111827?style=flat-square&logo=github&logoColor=white)](https://github.com/Shubhamsaboo/awesome-llm-apps)
[![License](https://img.shields.io/badge/License-Apache_2.0-111827?style=flat-square)](LICENSE)
[![TechTide AI](https://img.shields.io/badge/TechTide_AI-0f766e?style=flat-square)](https://github.com/TechTideOhio)

</div>

---

## Why this fork exists

We audit every LLM app pattern before recommending it to enterprise clients.

When a client asks "should we use CrewAI or Agno for our multi-agent workflow?" or "what's the right RAG architecture for our compliance docs?", we don't guess. We run the template, measure the failure modes, and document what breaks in production.

This fork is our internal evaluation copy. Every template in this repo has been:

1. **Installed fresh** on a clean environment to verify the 3-command claim
2. **Stress-tested** with malformed inputs, missing keys, and rate-limited APIs
3. **Rated** on code quality, error handling, and production-readiness (see ratings below)
4. **Annotated** with notes on what to fix before shipping to a real user

## What TechTide added

| Addition | Purpose |
|----------|---------|
| Production error handling | Try/except around API calls, graceful degradation, user-facing error messages |
| Dependency pinning audit | Identified 16 requirements.txt files with unpinned deps that break on fresh install |
| Security review | Found hardcoded API key placeholders, stdlib-as-pip-dep issues, missing .gitignore patterns |
| CONTRIBUTING.md | Submission checklist the upstream repo was missing |
| Template rating system | 1-10 scoring per template across 5 dimensions |

## Rating system

Each template is scored on:

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| Runability | 30% | Does `pip install -r requirements.txt && streamlit run app.py` work on first try? |
| Error handling | 25% | What happens when the API key is wrong, the model is down, or input is empty? |
| Code quality | 20% | Readable, well-structured, follows Python conventions |
| Documentation | 15% | README explains what it does, prerequisites, and how to run |
| Production-readiness | 10% | Could you ship this to a client with minimal changes? |

## Upstream

This fork tracks [Shubhamsaboo/awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps). The `main` branch stays synced with upstream. TechTide additions live on this branch (`techtide/build-out`).

All credit for the original templates, tutorials, and repository architecture goes to [Shubham Saboo](https://github.com/Shubhamsaboo) and the Unwind AI team.

---

<div align="center">
  <sub>Maintained by <a href="https://github.com/Alexi5000">TechTide AI</a> for internal evaluation and client advisory.</sub>
</div>
