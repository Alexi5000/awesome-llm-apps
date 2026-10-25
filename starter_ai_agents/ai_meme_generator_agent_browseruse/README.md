# 🥸 AI Meme Generator Agent - Browser Use

The AI Meme Generator Agent is a powerful browser automation tool that creates memes using AI agents. This app combines multi-LLM capabilities with automated browser interactions to generate memes based on text prompts through direct website manipulation.

## Features

- **Multi-LLM Support**
  - Claude 3.5 Sonnet (Anthropic)
  - GPT-4o (OpenAI)
  - Deepseek v3 (Deepseek)
  - Automatic model switching with API key validation

- **Browser Automation**:
  - Direct interaction with imgflip.com meme templates
  - Automated search for relevant meme formats
  - Dynamic text insertion for top/bottom captions
  - Image link extraction from generated memes

- **Smart Generation Workflow**:
  - Action verb extraction from prompts
  - Metaphorical template matching
  - Multi-step quality validation
  - Automatic retry mechanism for failed generations

- **User-Friendly Interface**:
  - Model configuration sidebar
  - API key management
  - Direct meme preview with clickable links
  - Responsive error handling


API keys required:
- **Anthropic** (for Claude)
- **Deepseek** 
- **OpenAI** (for GPT-4o)

## How to Run

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/Shubhamsaboo/awesome-llm-apps.git
   cd starter_ai_agents/ai_meme_generator_agent_browseruse
   ```
2. **Install the dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    Install Chromium using the installed Browser Use CLI:
    ```bash
    browser-use install
    ```
3. **Run the Streamlit app**:
    ```bash
    streamlit run ai_meme_generator_agent.py

    ```

### Running with uv

You can also run this project using [uv](https://docs.astral.sh/uv/), a fast Python package manager, instead of `pip`.

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/Shubhamsaboo/awesome-llm-apps.git
   cd starter_ai_agents/ai_meme_generator_agent_browseruse
   ```
2. **Install the dependencies** (this creates a `.venv` and installs everything from `pyproject.toml`/`uv.lock`):
    ```bash
    uv sync
    ```
    Install Chromium if needed:
    ```bash
    uv run browser-use install
    ```
3. **Run the Streamlit app**:
    ```bash
    uv run streamlit run ai_meme_generator_agent.py
    ```

### Dependency compatibility checks

This app includes maintained browser-use and browser-harness source packages
with patched dependency pins; keep `vendor/` when copying the app. The uv lock
targets Python 3.11; the pip installation is also tested on Python 3.12.
See [vendor/README.md](vendor/README.md) for provenance and removal criteria.

With Chromium or Chrome installed, run either:

```bash
uv sync --frozen --group test
uv run --frozen --group test python -m unittest discover -s tests -v
```

or, in a Python 3.12 virtual environment:

```bash
python -m pip install -r requirements-test.txt
python -m pip check
python -m unittest discover -s tests -v
```

Set `BROWSER_EXECUTABLE_PATH` if the browser is not on PATH. The compatibility
tests use only local pages and local MCP servers; they need no provider keys.
