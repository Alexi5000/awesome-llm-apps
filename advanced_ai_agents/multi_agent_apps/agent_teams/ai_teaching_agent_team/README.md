# 👨‍🏫 AI Teaching Agent Team

### 🎓 FREE Step-by-Step Tutorial 
**👉 [Click here to follow our complete step-by-step tutorial](https://www.theunwindai.com/p/build-an-ai-teaching-agent-team) and learn how to build this from scratch with detailed code walkthroughs, explanations, and best practices.**

A Streamlit application that brings together a team of specialized AI teaching agents who collaborate like a professional teaching faculty. Each agent acts as a specialized educator: a curriculum designer, learning path expert, resource librarian, and practice instructor - working together to create a complete educational experience through Google Docs.

## 🪄 Meet your AI Teaching Agent Team 

#### 🧠 Professor Agent
- Creates fundamental knowledge base in Google Docs
- Organizes content with proper headings and sections
- Includes detailed explanations and examples
- Output: Comprehensive knowledge base document with table of contents

#### 🗺️ Academic Advisor Agent
- Designs learning path in a structured Google Doc
- Creates progressive milestone markers
- Includes time estimates and prerequisites
- Output: Visual roadmap document with clear progression paths

#### 📚 Research Librarian Agent
- Compiles resources in an organized Google Doc
- Includes links to academic papers and tutorials
- Adds descriptions and difficulty levels
- Output: Categorized resource list with quality ratings

#### ✍️ Teaching Assistant Agent
- Develops exercises in an interactive Google Doc
- Creates structured practice sections
- Includes solution guides
- Output: Complete practice workbook with answers


## How to Run

1. Clone the repository
  ```bash
   # Clone the repository
   git clone https://github.com/Shubhamsaboo/awesome-llm-apps.git
   cd advanced_ai_agents/multi_agent_apps/agent_teams/ai_teaching_agent_team

   # Install dependencies
   pip install -r requirements.txt
   ```

## Configuration - IMPORTANT STEP

1. Get your OpenAI API Key
- Create an account on [OpenAI Platform](https://platform.openai.com/)
- Navigate to API Keys section
- Create a new API key

2. Get your Composio API Key
- Create an account on [Composio Platform](https://composio.ai/)
- Connect Google Docs in the [Composio dashboard](https://platform.composio.dev/) using its Google OAuth flow. The API key alone does not grant Google account access.
- Note the Composio **user ID** assigned to that connection. Enter the same user ID in the app sidebar; `default` retains the previous example's account scope. This is a local single-operator example, not a multi-user authentication system.
- Use a fresh Python 3.12 virtual environment. The current `composio` SDK replaces `composio-core`, `composio-phidata`, and the old shim package; do not install both generations together.

3. Sign up and get the [SerpAPI Key](https://serpapi.com/)

## How to Use? 

1. Start the Streamlit app
```bash
streamlit run teaching_agent_team.py
```

2. Use the application
- Enter your OpenAI API key in the sidebar (if not set in environment)
- Enter your Composio API key in the sidebar 
- Type a topic you want to learn about (e.g., "Python Programming", "Machine Learning")
- Click "Start"
- Wait for the agents to generate your personalized learning plan
- View the results and terminal output in the interface

## Runtime compatibility and security validation

The example uses Composio 0.28, Agno 3.1 and OpenAI 2.54. `teaching_tools.py` implements the SDK's [custom agentic-provider contract](https://docs.composio.dev/docs/providers/custom-providers/python) with native Agno functions. It preserves the fetched JSON schemas, validates arguments, and retains Composio's user-scoped execution and error results. Both Google Docs creation and document updates are available to every teaching agent. The current published `composio-agno` package still depends on the legacy SDK and is intentionally not mixed into this environment.

Run offline checks with `python -m unittest discover -s tests -v` from this directory. Tests use the real SDKs and Agno agent loop with intercepted HTTP transports, including create/update document content, user isolation, failure propagation and all four Streamlit agents. Network connections are blocked. The two input-schema fixtures were retrieved from the official public Composio documentation API on 2026-10-18; source URLs are embedded in each fixture. These tests do not validate live OAuth grants, paid model calls or actual Google document delivery.
