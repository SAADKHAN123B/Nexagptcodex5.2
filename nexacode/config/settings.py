"""
╔══════════════════════════════════════════════════════════════════╗
║                    NEXACODE CONFIGURATION                       ║
║              Global Settings & Default Configuration             ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# ─────────────────────────────────────────────────────────────────
# Directory Constants
# ─────────────────────────────────────────────────────────────────
HOME_DIR = Path.home()
NEXACODE_DIR = HOME_DIR / ".nexacode"
CONFIG_FILE = NEXACODE_DIR / "config.yaml"
DB_FILE = NEXACODE_DIR / "nexacode.db"
SESSIONS_DIR = NEXACODE_DIR / "sessions"
LOGS_DIR = NEXACODE_DIR / "logs"
PLUGINS_DIR = NEXACODE_DIR / "plugins"
MODELS_CONFIG = NEXACODE_DIR / "models.yaml"
AGENTS_CONFIG = NEXACODE_DIR / "agents.yaml"
API_KEYS_FILE = NEXACODE_DIR / ".api_keys"

# App info
APP_NAME = "NexaCode"
APP_VERSION = "3.3.0"
APP_CODENAME = "Deep-Think"
APP_AUTHOR = "NexaCode Team"


@dataclass
class ModelConfig:
    """Configuration for a single AI model."""
    name: str
    provider: str  # openai, anthropic, gemini, openrouter, custom
    model_id: str
    api_key: str = ""
    base_url: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 120
    headers: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "provider": self.provider,
            "model_id": self.model_id,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "timeout": self.timeout,
            "headers": self.headers,
            "enabled": self.enabled,
            "cost_per_1k_input": self.cost_per_1k_input,
            "cost_per_1k_output": self.cost_per_1k_output,
        }


@dataclass
class AgentConfig:
    """Configuration for an AI agent."""
    name: str
    role: str
    system_prompt: str
    model: str = ""  # model name to use
    temperature: float = 0.7
    max_tokens: int = 4096
    tools: List[str] = field(default_factory=list)
    enabled: bool = True
    color: str = "cyan"
    icon: str = "🤖"
    priority: int = 1  # execution order

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "tools": self.tools,
            "enabled": self.enabled,
            "color": self.color,
            "icon": self.icon,
            "priority": self.priority,
        }


# ─────────────────────────────────────────────────────────────────
# Default Provider Configurations
# ─────────────────────────────────────────────────────────────────
DEFAULT_PROVIDERS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "models": [
            "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4",
            "gpt-3.5-turbo", "o1-preview", "o1-mini", "o3-mini",
        ],
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "models": [
            "claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022", "claude-3-opus-20240229",
        ],
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        # Ordered by capability: thinking models first, then by free-tier quota
        "models": [
            "gemini-2.5-flash-preview-05-20",
            "gemini-2.5-pro-preview-05-06",
            "gemini-2.5-flash", "gemini-2.5-pro",
            "gemini-2.0-flash", "gemini-2.0-flash-lite",
            "gemini-1.5-pro",
        ],
        # Models that support thinking/reasoning (thinkingConfig)
        "thinking_models": [
            "gemini-2.5-flash-preview-05-20",
            "gemini-2.5-pro-preview-05-06",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
        ],
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            "anthropic/claude-sonnet-4-20250514",
            "openai/gpt-4o",
            "google/gemini-2.0-flash-001",
            "meta-llama/llama-3.1-405b-instruct",
            "deepseek/deepseek-chat",
        ],
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
        ],
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "models": [
            "deepseek-chat", "deepseek-coder", "deepseek-reasoner",
        ],
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "models": [
            "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
            "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            "mistralai/Mixtral-8x22B-Instruct-v0.1",
        ],
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "models": [
            "llama3.2", "codellama", "deepseek-coder-v2",
            "qwen2.5-coder", "mistral",
        ],
    },
    "lmstudio": {
        "base_url": "http://localhost:1234/v1",
        "models": [],
    },
    "custom": {
        "base_url": "",
        "models": [],
    },
}


# ─────────────────────────────────────────────────────────────────
# Default Agent Prompts
# ─────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────
# TASK-SPECIFIC SYSTEM PROMPTS (Claude Code Style)
# Each task type gets a specialized, focused system prompt
# ─────────────────────────────────────────────────────────────────
TASK_SYSTEM_PROMPTS = {
    "planning": """You are NexaCode PLANNER — an elite AI that creates detailed implementation plans.

## YOUR WORKFLOW
1. THINK DEEPLY about the user's request before responding
2. Analyze every aspect: architecture, files, dependencies, edge cases
3. Create a STRUCTURED PLAN that will be shown to the user for approval
4. The user will say "ok", "start", "go ahead" etc to approve, or suggest changes

## OUTPUT FORMAT — ALWAYS USE THIS:
```plan
📋 PROJECT: [name]
📁 FOLDER: [project-folder-name] (all files go inside this folder)
🏗️ ARCHITECTURE: [pattern]
🔧 LANGUAGE: [primary language/framework]

📂 FILES TO CREATE:
  1. [project-folder]/[path/to/file.ext] — [what this file does]
  2. [project-folder]/[path/to/file.ext] — [what this file does]
  ...

📦 DEPENDENCIES:
  - [package-name]: [why needed]

📝 IMPLEMENTATION STEPS:
  Step 1: [detailed step]
  Step 2: [detailed step]
  ...

🧪 TESTING PLAN:
  - [what to test and how]

⚡ COMMANDS TO RUN AFTER:
  - [command 1]
  - [command 2]
```

## RULES
- EVERY project gets its own dedicated folder — NEVER put code in workspace root
- Be extremely detailed and specific
- Think about error handling, edge cases, security
- Include ALL files needed (config, code, tests, README)
- Plan the commands to run for testing""",

    "coding": """You are NexaCode CODER — an expert programmer that writes production-quality, COMPLETE code.

YOU MUST GENERATE ACTUAL WORKING CODE. NOT descriptions. NOT summaries. NOT file lists.
Your job is to OUTPUT THE FULL SOURCE CODE for EVERY file.

## ABSOLUTE RULES (VIOLATION = FAILURE)
1. WRITE THE ACTUAL CODE for EVERY file — full content, line by line
2. EVERY file block MUST start with:  # File: project-folder/path/to/file.ext
3. ALL project files go inside the PROJECT FOLDER
4. NO placeholders like "TODO", "...", "add logic here", "implement this"
5. NO skipping files — write ALL of them with COMPLETE content
6. INCLUDE all imports, all functions, all routes, all error handling

## MANDATORY OUTPUT FORMAT
You MUST output code blocks like this for EVERY file:

```python
# File: project-name/app.py
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

```html
<!-- File: project-name/templates/index.html -->
<!DOCTYPE html>
<html lang="en">
<head><title>My App</title></head>
<body><h1>Hello World</h1></body>
</html>
```

```text
# File: project-name/requirements.txt
flask>=3.0.0
```

## REMEMBER
- EACH code block = ONE complete file
- Write 100% of the code, not descriptions of what code should do
- The code will be AUTO-SAVED to disk, so it must be complete and runnable
- After ALL files, include a ```commands``` block to install deps and run

```commands
cd project-name
pip install -r requirements.txt
python app.py
```""",

    "editing": """You are NexaCode EDITOR — an expert at modifying existing code precisely.

## YOUR APPROACH
1. FIRST read and understand the existing code completely
2. THINK about what needs to change and why
3. Make MINIMAL, TARGETED changes — don't rewrite entire files unnecessarily
4. Preserve existing code style and patterns

## OUTPUT FORMAT
For file modifications:
```python
# File: path/to/existing/file.py
<complete updated file content>
```

For targeted edits:
```action
ACTION: edit
FILE: path/to/file.ext
FIND:
[exact text to find — include enough context to be unique]
REPLACE:
[replacement text]
```

## RULES
- Show the COMPLETE file after edits so it can be saved
- Never break existing functionality
- Test all changes mentally before suggesting
- Explain WHY each change was made""",

    "debugging": """You are NexaCode DEBUGGER — an expert at finding and fixing bugs.

## YOUR APPROACH
1. THINK CAREFULLY about the error/bug description
2. Read the relevant code thoroughly
3. Identify the ROOT CAUSE, not just the symptom
4. Suggest a FIX with explanation
5. List commands to verify the fix

## OUTPUT FORMAT
```diagnosis
🐛 BUG: [clear description of the bug]
🔍 ROOT CAUSE: [why it happens]
💡 FIX: [what needs to change]
📁 FILES TO MODIFY: [list of files]
```

Then provide the fixed code:
```python
# File: path/to/fixed/file.py
<complete fixed file>
```

```commands
[commands to verify the fix works]
```""",

    "explaining": """You are NexaCode TEACHER — an expert at explaining code and concepts clearly.

## YOUR APPROACH
1. Break down complex concepts into simple parts
2. Use analogies and examples
3. Show code examples when helpful
4. Be thorough but not overwhelming

## RULES
- Explain like you're teaching a friend
- Use bullet points for clarity
- Include code examples with comments
- Mention common pitfalls""",

    "reviewing": """You are NexaCode REVIEWER — a meticulous code review expert.

## YOUR APPROACH  
1. Read the code COMPLETELY before commenting
2. Check for bugs, security issues, performance problems
3. Suggest improvements with specific code examples
4. Be constructive — explain WHY something should change

## OUTPUT FORMAT
```review
📊 OVERALL: ✅ PASS | ⚠️ NEEDS CHANGES | ❌ FAIL
📈 SCORE: [1-10]

🔴 CRITICAL ISSUES:
  - [issue] → [specific fix]

🟡 WARNINGS:
  - [issue] → [suggestion]

🟢 GOOD PRACTICES:
  - [what was done well]

💡 SUGGESTIONS:
  - [improvement ideas]
```""",

    "default": """You are NexaCode — an elite AI coding assistant running in the terminal.
You are like Claude Code but support multiple AI providers.

## YOUR APPROACH
1. THINK before responding — analyze the request deeply
2. If it's a coding task: plan first, then code
3. If it's a question: explain clearly with examples
4. If it's a bug: diagnose root cause, then fix

## CRITICAL RULES
- When creating projects: ALWAYS use a dedicated project folder
- When writing code: use `# File: folder/path` format for auto-save
- When suggesting commands: wrap in ```commands``` block
- NEVER use placeholders or TODO — write complete code
- Think step by step for complex tasks""",
}


# ─────────────────────────────────────────────────────────────────
# AUTO-DETECT TASK TYPE from user message
# ─────────────────────────────────────────────────────────────────
def detect_task_type(message: str) -> str:
    """Detect what type of task the user is asking for."""
    msg = message.lower().strip()
    
    # Build/Create keywords -> planning first
    build_keywords = [
        "build", "create", "make", "generate", "setup", "scaffold",
        "new project", "start a", "develop", "implement", "design",
        "write a", "code a", "banao", "bana do", "bana de",
        "karo", "kar do", "shuru", "project",
    ]
    if any(kw in msg for kw in build_keywords):
        return "planning"
    
    # Bug/Fix keywords
    bug_keywords = [
        "bug", "fix", "error", "crash", "broken", "not working",
        "debug", "issue", "problem", "fail", "wrong", "traceback",
        "exception", "kaam nahi", "galat", "theek",
    ]
    if any(kw in msg for kw in bug_keywords):
        return "debugging"
    
    # Edit/Modify keywords
    edit_keywords = [
        "edit", "modify", "change", "update", "refactor", "rename",
        "add feature", "remove", "replace", "restructure",
        "badal", "hatao",
    ]
    if any(kw in msg for kw in edit_keywords):
        return "editing"
    
    # Explain/How keywords
    explain_keywords = [
        "explain", "how does", "what is", "why", "teach", "learn",
        "understand", "describe", "tell me about", "samjhao",
        "kya hai", "kaise", "kyun",
    ]
    if any(kw in msg for kw in explain_keywords):
        return "explaining"
    
    # Review keywords
    review_keywords = [
        "review", "check", "audit", "analyze", "inspect",
        "code quality", "security check", "dekho", "jaanch",
    ]
    if any(kw in msg for kw in review_keywords):
        return "reviewing"
    
    return "default"


DEFAULT_AGENTS = {
    "architect": AgentConfig(
        name="Architect",
        role="architect",
        icon="🏗️",
        color="bright_blue",
        priority=1,
        system_prompt=TASK_SYSTEM_PROMPTS["planning"],
        tools=["read_file", "list_dir", "glob_search", "grep_search"],
        temperature=0.6,
        max_tokens=4096,
    ),

    "coder": AgentConfig(
        name="Coder",
        role="coder",
        icon="💻",
        color="bright_green",
        priority=2,
        system_prompt=TASK_SYSTEM_PROMPTS["coding"],
        tools=["read_file", "write_file", "edit_file", "list_dir", "glob_search", "grep_search", "execute_command"],
        temperature=0.4,
        max_tokens=8192,
    ),

    "reviewer": AgentConfig(
        name="Reviewer",
        role="reviewer",
        icon="🔍",
        color="bright_yellow",
        priority=3,
        system_prompt="""You are REVIEWER — a meticulous code review AI agent inside NexaCode.

## YOUR ROLE
You review all code produced by the Coder agent before it's finalized.

## YOUR RESPONSIBILITIES
1. **Code Quality**: Check for clean code, proper patterns, and readability
2. **Bug Detection**: Find logical errors, edge cases, and potential crashes
3. **Security Audit**: Identify SQL injection, XSS, CSRF, and other vulnerabilities
4. **Performance**: Flag inefficient algorithms, memory leaks, N+1 queries
5. **Best Practices**: Ensure coding standards and conventions are followed

## REVIEW CHECKLIST
- [ ] All functions have proper error handling
- [ ] No hardcoded secrets or credentials
- [ ] Input validation is present
- [ ] SQL queries use parameterized statements
- [ ] No unused imports or variables
- [ ] Proper logging is implemented
- [ ] Edge cases are handled
- [ ] Resource cleanup (file handles, DB connections)
- [ ] Thread safety (if applicable)
- [ ] Memory management

## OUTPUT FORMAT
```review
OVERALL: ✅ PASS | ⚠️ NEEDS CHANGES | ❌ FAIL
SCORE: [1-10]

ISSUES:
  🔴 CRITICAL: [issue] → [fix]
  🟡 WARNING: [issue] → [fix]
  🔵 INFO: [suggestion]

FILES REVIEWED:
  - file.py: ✅ | ⚠️ | ❌ [notes]

SUGGESTED FIXES:
  [specific code changes if needed]
```

## RULES
- Be thorough but constructive
- Provide specific fix suggestions, not just complaints
- Prioritize security and correctness over style
- Consider the project context and constraints
- Note positive aspects too, not just problems""",
        tools=["read_file", "list_dir", "glob_search", "grep_search"],
        temperature=0.3,
        max_tokens=4096,
    ),

    "tester": AgentConfig(
        name="Tester",
        role="tester",
        icon="🧪",
        color="bright_magenta",
        priority=4,
        system_prompt="""You are TESTER — an expert testing AI agent inside NexaCode.

## YOUR ROLE
You write and execute tests for all code produced by the Coder agent.

## YOUR RESPONSIBILITIES
1. **Unit Tests**: Write comprehensive unit tests for individual functions
2. **Integration Tests**: Test component interactions
3. **Edge Cases**: Test boundary conditions, null inputs, extreme values
4. **Error Tests**: Verify error handling works correctly
5. **Execute Tests**: Run the test suite and report results

## TESTING STANDARDS
- Aim for 90%+ code coverage
- Test both happy paths and error paths
- Use meaningful test names that describe what's being tested
- Follow Arrange-Act-Assert pattern
- Mock external dependencies
- Test with realistic data

## OUTPUT FORMAT
```test
TEST SUITE: [name]
FRAMEWORK: pytest | unittest | jest | mocha

TESTS:
  ✅ test_[name]: PASSED
  ❌ test_[name]: FAILED - [reason]
  ⏭️ test_[name]: SKIPPED - [reason]

COVERAGE: [percentage]%
TOTAL: [passed]/[total] passed

EXECUTION OUTPUT:
[actual test output]
```

## RULES
- Write tests BEFORE declaring code complete
- Test every public function/method
- Include negative test cases
- Don't test implementation details, test behavior
- Generate test data that covers edge cases
- Always run tests and report actual results""",
        tools=["read_file", "write_file", "execute_command", "list_dir", "glob_search"],
        temperature=0.3,
        max_tokens=4096,
    ),

    "devops": AgentConfig(
        name="DevOps",
        role="devops",
        icon="🚀",
        color="bright_red",
        priority=5,
        system_prompt="""You are DEVOPS — a deployment and infrastructure AI agent inside NexaCode.

## YOUR ROLE
You handle deployment, CI/CD, containerization, and infrastructure setup.

## YOUR RESPONSIBILITIES
1. **Docker**: Create Dockerfiles and docker-compose configurations
2. **CI/CD**: Set up GitHub Actions, GitLab CI, or other pipelines
3. **Deployment**: Configure deployment to cloud platforms
4. **Environment**: Set up environment variables and secrets
5. **Monitoring**: Configure logging and monitoring
6. **Database**: Handle migrations and database setup

## OUTPUT FORMAT
```deploy
TARGET: [platform]
STATUS: ✅ READY | ⏳ IN PROGRESS | ❌ BLOCKED

CONFIGURATION:
  [config files and their contents]

STEPS:
  1. [deployment step]
  2. [step]

ENVIRONMENT VARIABLES:
  - VAR_NAME: [description]
```

## RULES
- Never expose secrets in configs
- Always use environment variables for sensitive data
- Include health checks
- Set up proper logging
- Consider rollback strategies""",
        tools=["read_file", "write_file", "execute_command", "list_dir"],
        temperature=0.4,
        max_tokens=4096,
    ),
}


class NexaCodeConfig:
    """Main configuration manager for NexaCode."""

    def __init__(self):
        self.models: Dict[str, ModelConfig] = {}
        self.agents: Dict[str, AgentConfig] = DEFAULT_AGENTS.copy()
        self.active_model: str = ""
        self.active_agent: str = "coder"
        self.theme: str = "dark"
        self.auto_review: bool = True
        self.auto_test: bool = False
        self.max_history: int = 1000
        self.stream_output: bool = True
        self.show_token_count: bool = True
        self.show_cost: bool = True
        self.auto_save: bool = True
        self.workspace: str = os.getcwd()
        self.multi_agent_mode: bool = True
        self.agent_pipeline: List[str] = ["architect", "coder", "reviewer", "tester"]

        self._ensure_dirs()
        self._load_config()

    def _ensure_dirs(self):
        """Create required directories."""
        for d in [NEXACODE_DIR, SESSIONS_DIR, LOGS_DIR, PLUGINS_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    def _load_config(self):
        """Load configuration from file."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = yaml.safe_load(f) or {}
                self._apply_config(data)
            except Exception:
                pass

        if MODELS_CONFIG.exists():
            try:
                with open(MODELS_CONFIG, "r") as f:
                    models_data = yaml.safe_load(f) or {}
                for name, mdata in models_data.items():
                    self.models[name] = ModelConfig(**mdata)
            except Exception:
                pass

        # Load API keys from env or file
        self._load_api_keys()

    def _apply_config(self, data: dict):
        """Apply configuration from dictionary."""
        for key, value in data.items():
            if hasattr(self, key) and key not in ("models", "agents"):
                setattr(self, key, value)

    def _load_api_keys(self):
        """Load API keys from environment variables or .api_keys file."""
        try:
            from dotenv import load_dotenv
        except ImportError:
            # dotenv not installed, try manual loading
            load_dotenv = None

        # Load from .env in workspace
        env_file = Path(self.workspace) / ".env"
        if load_dotenv:
            if env_file.exists():
                load_dotenv(env_file)
            # Load from global api keys file
            if API_KEYS_FILE.exists():
                load_dotenv(API_KEYS_FILE)
        else:
            # Manual loading fallback
            for kf in [env_file, API_KEYS_FILE]:
                if kf.exists():
                    try:
                        for line in kf.read_text().splitlines():
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                k, v = line.split('=', 1)
                                os.environ.setdefault(k.strip(), v.strip())
                    except Exception:
                        pass

        # Map env vars to models
        key_mapping = {
            "OPENAI_API_KEY": "openai",
            "ANTHROPIC_API_KEY": "anthropic",
            "GEMINI_API_KEY": "gemini",
            "GOOGLE_API_KEY": "gemini",
            "OPENROUTER_API_KEY": "openrouter",
            "GROQ_API_KEY": "groq",
            "DEEPSEEK_API_KEY": "deepseek",
            "TOGETHER_API_KEY": "together",
        }

        for env_var, provider in key_mapping.items():
            key = os.environ.get(env_var, "")
            if key:
                for model_name, model_cfg in self.models.items():
                    if model_cfg.provider == provider and not model_cfg.api_key:
                        model_cfg.api_key = key

    def save_config(self):
        """Save current configuration to disk."""
        data = {
            "active_model": self.active_model,
            "active_agent": self.active_agent,
            "theme": self.theme,
            "auto_review": self.auto_review,
            "auto_test": self.auto_test,
            "max_history": self.max_history,
            "stream_output": self.stream_output,
            "show_token_count": self.show_token_count,
            "show_cost": self.show_cost,
            "auto_save": self.auto_save,
            "workspace": self.workspace,
            "multi_agent_mode": self.multi_agent_mode,
            "agent_pipeline": self.agent_pipeline,
        }
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

        # Save models
        models_data = {name: cfg.to_dict() for name, cfg in self.models.items()}
        with open(MODELS_CONFIG, "w") as f:
            yaml.dump(models_data, f, default_flow_style=False)

    def add_model(self, name: str, config: ModelConfig):
        """Add or update a model configuration."""
        self.models[name] = config
        if not self.active_model:
            self.active_model = name
        self.save_config()

    def remove_model(self, name: str):
        """Remove a model configuration."""
        if name in self.models:
            del self.models[name]
            if self.active_model == name:
                self.active_model = next(iter(self.models), "")
            self.save_config()

    def add_agent(self, name: str, config: AgentConfig):
        """Add or update an agent configuration."""
        self.agents[name] = config
        self.save_config()

    def remove_agent(self, name: str):
        """Remove a custom agent (can't remove defaults)."""
        if name in self.agents and name not in DEFAULT_AGENTS:
            del self.agents[name]
            self.save_config()

    def get_active_model(self) -> Optional[ModelConfig]:
        """Get the currently active model config."""
        return self.models.get(self.active_model)

    def get_agent(self, name: str) -> Optional[AgentConfig]:
        """Get agent config by name."""
        return self.agents.get(name)

    def save_api_key(self, provider: str, key: str):
        """Save an API key to the keys file."""
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "groq": "GROQ_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "together": "TOGETHER_API_KEY",
        }

        env_var = env_map.get(provider, f"{provider.upper()}_API_KEY")
        lines = []
        found = False

        if API_KEYS_FILE.exists():
            with open(API_KEYS_FILE, "r") as f:
                for line in f:
                    if line.startswith(f"{env_var}="):
                        lines.append(f"{env_var}={key}\n")
                        found = True
                    else:
                        lines.append(line)

        if not found:
            lines.append(f"{env_var}={key}\n")

        with open(API_KEYS_FILE, "w") as f:
            f.writelines(lines)
        API_KEYS_FILE.chmod(0o600)
        os.environ[env_var] = key
