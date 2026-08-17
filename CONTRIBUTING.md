# Contributing

Alexi5000/awesome-llm-apps is an applied agent-engineering fork of the upstream [Shubhamsaboo/awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps) catalog. Contributions should improve reproducibility, documentation quality, safe integration boundaries, or fork-specific learning value while preserving clear upstream attribution.

## Contribution scope

Use a focused issue or pull request for one example, one documentation correction, or one repository-quality improvement at a time. Explain the target example, the agent or automation pattern involved, the intended learner or operator outcome, and the verification performed. Include screenshots or terminal output when a user-facing behavior changes.

For upstream catalog features that do not depend on Alexi5000-specific guidance, consider contributing directly upstream. Fork-specific policy and synchronization expectations are defined in [FORK_POLICY.md](./FORK_POLICY.md).

## Local verification

Use Python 3.11 or newer. Run the repository-level checks from the root before opening a pull request:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
python3 -m compileall -q \
  starter_ai_agents advanced_ai_agents advanced_llm_apps \
  mcp_ai_agents rag_tutorials voice_ai_agents
```

Then follow the selected example’s README and install only that example’s dependencies in an isolated virtual environment. Do not commit `.env` files, API keys, OAuth tokens, customer data, generated caches, model weights, or local databases.

## Pull-request standard

A pull request should state its purpose, identify affected paths, note provider or framework assumptions, and record the commands used for verification. Keep dependency changes minimal and pinned only where the example’s ecosystem requires it. Review the implementation for credential handling, privacy exposure, tool side effects, and upstream attribution before requesting review.

Security-sensitive reports must follow [SECURITY.md](./SECURITY.md), and participant expectations are defined by [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).
