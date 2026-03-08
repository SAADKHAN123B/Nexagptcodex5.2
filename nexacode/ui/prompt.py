"""
╔══════════════════════════════════════════════════════════════════╗
║                   NEXACODE PROMPT INPUT                         ║
║            Advanced Input with Auto-Complete & History            ║
╚══════════════════════════════════════════════════════════════════╝
"""

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter, merge_completers, PathCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from pathlib import Path

from nexacode.config.settings import NEXACODE_DIR


# ─────────────────────────────────────────────────────────────────
# Prompt Style
# ─────────────────────────────────────────────────────────────────
PROMPT_STYLE = Style.from_dict({
    "prompt": "ansibrightcyan bold",
    "path": "ansibrightgreen",
    "arrow": "ansibrightmagenta bold",
    "": "ansiwhite",
    "completion-menu.completion": "bg:ansibrightblack ansiwhite",
    "completion-menu.completion.current": "bg:ansibrightcyan ansiblack",
    "auto-suggest": "ansibrightblack",
})


# ─────────────────────────────────────────────────────────────────
# Commands for auto-complete
# ─────────────────────────────────────────────────────────────────
COMMANDS = [
    # Quick help
    "/", "/help", "/help full",
    # Chat & AI
    "/ask", "/pipeline", "/agent", "/agents", "/clear", "/retry",
    # Model management
    "/model", "/model add", "/model list", "/model use", "/model remove",
    "/model info", "/providers", "/apikey",
    # File operations
    "/read", "/write", "/edit", "/tree", "/glob", "/grep", "/diff",
    "/mkdir", "/delete", "/move", "/copy", "/save", "/save all",
    # Project memory
    "/project", "/project list", "/project open", "/project new",
    "/project save", "/project info", "/project close", "/project delete",
    # Execution
    "/run", "/exec", "/test", "/lint", "/install",
    # Session & history
    "/session", "/session new", "/session list", "/session load",
    "/history", "/search", "/usage",
    # Settings
    "/config", "/config set", "/workspace", "/theme", "/export",
    # General
    "/version", "/stats", "/quit", "/exit", "/q",
    # Agents
    "architect", "coder", "reviewer", "tester", "devops",
]

AGENT_NAMES = ["architect", "coder", "reviewer", "tester", "devops"]


def create_prompt_session(workspace: str = ".") -> PromptSession:
    """Create a prompt session with rich features."""
    history_file = NEXACODE_DIR / "command_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    command_completer = WordCompleter(
        COMMANDS,
        ignore_case=True,
        sentence=True,
    )

    path_completer = PathCompleter(
        expanduser=True,
        get_paths=lambda: [workspace],
    )

    completer = merge_completers([command_completer, path_completer])

    return PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=completer,
        style=PROMPT_STYLE,
        complete_while_typing=True,
        enable_history_search=True,
        mouse_support=False,
    )


def get_prompt_message(workspace: str, agent: str = "coder") -> list:
    """Generate the prompt message with current context."""
    short_path = Path(workspace).name or workspace
    return [
        ("class:prompt", "NexaCode"),
        ("class:arrow", " ⚡ "),
        ("class:path", short_path),
        ("class:arrow", f" [{agent}]"),
        ("class:arrow", " ❯ "),
    ]


def get_multiline_prompt() -> list:
    """Prompt for multiline input."""
    return [
        ("class:prompt", "NexaCode"),
        ("class:arrow", " 📝 "),
        ("class:path", "multiline (Ctrl+D to finish)"),
        ("class:arrow", " ❯ "),
    ]
