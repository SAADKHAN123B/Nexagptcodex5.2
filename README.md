# NexaCode v3.0 "Deep-Think" — AI-Powered Terminal Coding Assistant

```
 ███╗   ██╗███████╗██╗  ██╗ █████╗  ██████╗ ██████╗ ██████╗ ███████╗
 ████╗  ██║██╔════╝╚██╗██╔╝██╔══██╗██╔════╝██╔═══██╗██╔══██╗██╔════╝
 ██╔██╗ ██║█████╗   ╚███╔╝ ███████║██║     ██║   ██║██║  ██║█████╗  
 ██║╚██╗██║██╔══╝   ██╔██╗ ██╔══██║██║     ██║   ██║██║  ██║██╔══╝  
 ██║ ╚████║███████╗██╔╝ ╚██╗██║  ██║╚██████╗╚██████╔╝██████╔╝███████╗
 ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
```

**Like Claude Code, but running locally in YOUR terminal, with YOUR choice of AI models.**

## What's New in v3.0 "Deep-Think"

### 🧠 Deep Thinking Mode
- **Gemini 2.5 Thinking Models** — AI uses `thinkingConfig` for deep reasoning
- AI **thinks before coding** — no more rushed, wrong code
- Supports `gemini-2.5-flash-preview-05-20`, `gemini-2.5-pro-preview-05-06` and more

### 📋 Plan-First Workflow (Like Claude Code)
- **AI plans FIRST** → shows you the plan → waits for your approval
- Say `ok`, `start`, `go ahead`, `karo` etc → AI starts coding
- Say `no` → cancel | Suggest changes → AI updates the plan
- No more random code generation without thinking!

### 🎯 Task-Specific System Prompts
Each type of task gets its own specialized system prompt:
- **Planning** — for building new projects
- **Coding** — for writing implementation code
- **Debugging** — for finding and fixing bugs  
- **Editing** — for modifying existing code
- **Explaining** — for teaching and explaining concepts
- **Reviewing** — for code review and quality checks
- Auto-detects task type from your message!

### 💾 Auto-Save to Files (Not Chat!)
- Code is **automatically saved to files** — not pasted in chat
- `/save` still works as manual fallback
- Every project gets its **own dedicated folder**

### ⚡ Auto-Execute Commands
- AI detects terminal commands in response
- **Automatically runs them** after code generation
- Shows success/failure with output
- Tests your code right after writing it!

### 📁 Project Folder Isolation  
- Each project gets its own folder — no code dumped in workspace root
- Example: `my-todo-app/app.py`, not just `app.py`
- Clean, organized workspace

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run NexaCode
python3 nexacode.py

# 3. Set your API key (inside NexaCode)
/apikey gemini AIza-your-key-here       # Recommended for thinking
# or
/apikey openai sk-your-key-here
# or for local models:
/model add    # then choose ollama

# 4. Start coding! AI will PLAN first, then CODE after your approval
> build me a todo app with Flask
```

### One-liner Quick Start
```bash
python3 nexacode.py --provider gemini --apikey AIza-your-key   # Best for thinking!
python3 nexacode.py --provider openai --apikey sk-your-key-here
python3 nexacode.py --setup   # interactive wizard
```

## How It Works (v3.0 Workflow)

```
You: "build a todo app with Flask"
     ↓
🧠 AI THINKS deeply (Gemini thinking mode)
     ↓
📋 AI shows PLAN (files, architecture, steps)
     ↓
You: "ok" / "start" / "karo"
     ↓
💻 AI GENERATES complete code
     ↓
💾 AUTO-SAVES all files to project folder
     ↓
⚡ AUTO-RUNS test commands
     ↓
✅ Done! Working project ready!
```

## Features

### 10+ AI Providers
| Provider | Models | Thinking? |
|----------|--------|-----------|
| Google Gemini | Gemini 2.5 Flash/Pro (thinking!), 2.0 Flash | ✅ Yes |
| OpenAI | GPT-4o, GPT-4, o1, o3-mini | ❌ |
| Anthropic | Claude 3.5 Sonnet, Claude 3 Opus | ❌ |
| Groq | Llama 3.3, Mixtral | ❌ |
| DeepSeek | DeepSeek Chat, Coder, Reasoner | ✅ Reasoner |
| OpenRouter | Any model (unified API) | Varies |
| Together AI | Llama, Mixtral, and 100+ more | ❌ |
| Ollama | Llama 3.2, CodeLlama, any local model | ❌ |
| LM Studio | Any GGUF model | ❌ |
| Custom | Any OpenAI-compatible endpoint | Varies |

### 5 Specialized AI Agents
- **Architect** — Analyzes requirements, designs system architecture
- **Coder** — Writes production-quality code, full stack
- **Reviewer** — Reviews code for bugs, security, performance
- **Tester** — Writes and runs comprehensive tests
- **DevOps** — Handles deployment, CI/CD, Docker, infrastructure

### 6 Task-Specific Modes (Auto-Detected)
| Mode | Triggers | What AI Does |
|------|----------|-------------|
| Planning | "build", "create", "make" | Plans first, waits for approval |
| Coding | After plan approval | Writes complete code, auto-saves |
| Debugging | "fix", "bug", "error" | Diagnoses root cause, provides fix |
| Editing | "edit", "modify", "change" | Makes targeted changes |
| Explaining | "explain", "how", "why" | Teaches clearly with examples |
| Reviewing | "review", "check", "audit" | Code quality review with scores |

## All Commands

| Category | Command | Description |
|----------|---------|-------------|
| **Chat** | `<natural language>` | Just type! AI auto-detects task type |
| | `/ask <message>` | Send to active agent |
| | `/pipeline <task>` | Run full agent pipeline |
| | `/agent <name>` | Switch agent |
| | `/retry` | Retry last failed request |
| **Models** | `/apikey <provider> <key>` | Set API key |
| | `/model add` | Add model interactively |
| | `/model list` | List configured models |
| | `/model use <name>` | Switch model |
| **Files** | `/read <path>` | Read file |
| | `/write <path>` | Write file |
| | `/edit <path>` | Edit file |
| | `/save [all\|1 2 3]` | Manual save (auto-save is default now) |
| | `/tree` | Project structure |
| | `/glob <pattern>` | Find files |
| | `/grep <pattern>` | Search content |
| **Execute** | `/run <cmd>` | Run command |
| | `/exec <lang>` | Execute code |
| | `/test` | Run tests |
| **Session** | `/session new` | New session |
| | `/session load <id>` | Load session |
| | `/usage` | Token usage stats |

## Architecture

```
nexacode/
├── config/settings.py     — Config, providers, TASK PROMPTS, task detection
├── core/
│   ├── engine.py          — Multi-provider AI engine with THINKING MODE
│   └── commands.py        — PLAN→APPROVE→CODE→SAVE→TEST workflow
├── agents/orchestrator.py — Multi-agent pipeline system
├── tools/
│   ├── file_manager.py    — File operations (auto-save target)
│   └── executor.py        — Code execution sandbox (auto-execute)
├── db/database.py         — SQLite persistence layer
├── ui/
│   ├── terminal.py        — Rich terminal UI
│   └── prompt.py          — Auto-complete prompt
└── utils/helpers.py       — Utility functions
```

## v3.0 Changes (Deep-Think)

1. **🧠 Thinking Mode** — Gemini 2.5 thinking models with `thinkingConfig`
2. **📋 Plan-First** — AI plans → user approves → AI codes (like Claude Code)
3. **🎯 Task Detection** — Auto-detects: planning, coding, debugging, editing, explaining, reviewing
4. **📝 Task-Specific Prompts** — Each task type has its own specialized system prompt
5. **💾 Auto-Save** — Code blocks saved to files automatically (not pasted in chat)
6. **⚡ Auto-Execute** — Terminal commands run automatically after coding
7. **📁 Project Folders** — Each project gets its own folder, never clutters workspace root
8. **🌍 Hindi/Urdu Support** — "karo", "shuru", "theek hai" etc. work as approvals
9. **🔄 Plan Feedback** — Suggest changes to plans before approving
10. **Gemini 2.5 Preview Models** — Latest thinking models added

## Requirements

- Python 3.9+
- Dependencies: `pip install -r requirements.txt`
  - rich, prompt_toolkit, httpx, aiosqlite, pyyaml, python-dotenv, pygments

## License

MIT — Use it however you want.
