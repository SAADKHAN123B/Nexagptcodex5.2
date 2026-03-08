"""
+======================================================================+
|                  NEXACODE TERMINAL UI                                 |
|            Rich-Powered Mind-Blowing Terminal Interface               |
|   v3.1.1: Fixed UnicodeEncodeError for Termux/Android                |
|   All emoji output goes through safe_text() to strip surrogates      |
+======================================================================+
"""

import os
import sys
import time
import asyncio
from typing import Optional, List, Dict, Callable
from datetime import datetime

# ---- FORCE UTF-8 on Termux/Android/Windows where stdout defaults to ascii ----
import io as _io
if hasattr(sys.stdout, 'buffer'):
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
            sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.columns import Columns
from rich.text import Text
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.live import Live
from rich.layout import Layout
from rich.align import Align
from rich.rule import Rule
from rich.box import DOUBLE, HEAVY, ROUNDED, MINIMAL, SIMPLE_HEAVY
from rich import box

from nexacode.config.settings import APP_NAME, APP_VERSION, APP_CODENAME


# =====================================================================
# SAFE TEXT HELPER  --  strips surrogates that crash Termux stdout
# =====================================================================
def safe_text(text: str) -> str:
    """Remove surrogate characters that cause UnicodeEncodeError on Termux.
    
    Termux's default stdout encoding is often 'ascii' or 'utf-8' with
    strict error handling.  Rich markup containing emoji (which are fine)
    is not the problem -- the issue is that Python sometimes keeps
    surrogate pairs (\ud800-\udfff) in internal strings, and writing
    those to a strict-utf-8 or ascii pipe raises UnicodeEncodeError.
    
    This function:
    1. Encodes to utf-8 with 'surrogateescape' to handle surrogates
    2. Decodes back, replacing any invalid bytes with '?'
    """
    try:
        return text.encode('utf-8', errors='surrogateescape').decode('utf-8', errors='replace')
    except Exception:
        # Nuclear option: strip everything non-ASCII
        return text.encode('ascii', errors='replace').decode('ascii')


# ─────────────────────────────────────────────────────────────────
# Color Theme
# ─────────────────────────────────────────────────────────────────
class Theme:
    PRIMARY = "bright_cyan"
    SECONDARY = "bright_magenta"
    SUCCESS = "bright_green"
    WARNING = "bright_yellow"
    ERROR = "bright_red"
    INFO = "bright_blue"
    DIM = "dim white"
    ACCENT = "bright_white"
    CODE = "green"
    BORDER = "bright_cyan"
    HEADER = "bold bright_white on rgb(30,30,60)"
    AGENT_ARCHITECT = "bright_blue"
    AGENT_CODER = "bright_green"
    AGENT_REVIEWER = "bright_yellow"
    AGENT_TESTER = "bright_magenta"
    AGENT_DEVOPS = "bright_red"


# =====================================================================
# SAFE CONSOLE  --  wraps Rich Console to survive encoding issues
# =====================================================================
class SafeConsole(Console):
    """Console subclass that catches UnicodeEncodeError on .print()."""

    def print(self, *objects, **kwargs):
        try:
            super().print(*objects, **kwargs)
        except UnicodeEncodeError:
            # Fallback: stringify and sanitise, then try again
            try:
                safe_objects = []
                for obj in objects:
                    if isinstance(obj, str):
                        safe_objects.append(safe_text(obj))
                    else:
                        safe_objects.append(obj)
                super().print(*safe_objects, **kwargs)
            except UnicodeEncodeError:
                # Last resort: plain ascii
                for obj in objects:
                    sys.stdout.write(str(obj).encode('ascii', errors='replace').decode('ascii') + '\n')
                sys.stdout.flush()


# Create console with UTF-8 forced and graceful fallback
try:
    console = SafeConsole(force_terminal=True)
except Exception:
    console = SafeConsole()


# ─────────────────────────────────────────────────────────────────
# BANNER & SPLASH
# ─────────────────────────────────────────────────────────────────
BANNER_ART = """
[bright_cyan]
 ███╗   ██╗███████╗██╗  ██╗ █████╗  ██████╗ ██████╗ ██████╗ ███████╗
 ████╗  ██║██╔════╝╚██╗██╔╝██╔══██╗██╔════╝██╔═══██╗██╔══██╗██╔════╝
 ██╔██╗ ██║█████╗   ╚███╔╝ ███████║██║     ██║   ██║██║  ██║█████╗  
 ██║╚██╗██║██╔══╝   ██╔██╗ ██╔══██║██║     ██║   ██║██║  ██║██╔══╝  
 ██║ ╚████║███████╗██╔╝ ╚██╗██║  ██║╚██████╗╚██████╔╝██████╔╝███████╗
 ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
[/bright_cyan]
"""

TAGLINE = "[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]"


def show_banner():
    """Display the full NexaCode banner."""
    console.print(BANNER_ART)
    console.print(
        Align.center(
            Text.from_markup(
                f"[bold bright_white]⚡ AI-Powered Terminal Coding Assistant ⚡[/]\n"
                f"[dim]v{APP_VERSION} '{APP_CODENAME}' — Deep-Think • Plan-First • Auto-Execute[/dim]"
            )
        )
    )
    console.print(TAGLINE)
    console.print()


def show_welcome(workspace: str, model: str = "", session: str = ""):
    """Show welcome info panel."""
    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("Key", style="bright_cyan", width=16)
    info_table.add_column("Value", style="bright_white")

    info_table.add_row("📂 Workspace", workspace)
    info_table.add_row("🤖 Model", model or "[dim]Not configured[/dim]")
    info_table.add_row("💾 Session", session or "[dim]New session[/dim]")
    info_table.add_row("🕐 Started", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    panel = Panel(
        info_table,
        title="[bold bright_white]⚙️  Session Info[/]",
        border_style="bright_cyan",
        box=ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)
    console.print()


# ─────────────────────────────────────────────────────────────────
# STATUS & INFO DISPLAYS
# ─────────────────────────────────────────────────────────────────
def show_status_bar(model: str, agent: str, tokens: int, cost: float, session: str):
    """Show a compact status bar."""
    parts = [
        f"[bright_cyan]🤖 {model or 'N/A'}[/]",
        f"[bright_green]👤 {agent}[/]",
        f"[bright_yellow]🔤 {tokens:,} tokens[/]",
        f"[bright_magenta]💰 ${cost:.4f}[/]",
        f"[dim]📎 {session}[/]",
    ]
    bar = " │ ".join(parts)
    console.print(f"[dim]╔{'═' * (console.width - 2)}╗[/dim]")
    console.print(f" {bar}")
    console.print(f"[dim]╚{'═' * (console.width - 2)}╝[/dim]")


def show_agent_status(agents: Dict[str, dict]):
    """Show status of all agents."""
    table = Table(
        title="[bold bright_white]🤖 Agent Pipeline Status[/]",
        box=ROUNDED,
        border_style="bright_cyan",
        show_lines=True,
        padding=(0, 1),
    )
    table.add_column("#", style="dim", width=3, justify="center")
    table.add_column("Agent", style="bold", width=14)
    table.add_column("Role", width=12)
    table.add_column("Status", width=14, justify="center")
    table.add_column("Model", width=20)
    table.add_column("Tokens", justify="right", width=10)

    status_icons = {
        "idle": "[dim]⏸️  Idle[/]",
        "thinking": "[bright_yellow]🧠 Thinking[/]",
        "working": "[bright_green]⚡ Working[/]",
        "reviewing": "[bright_yellow]🔍 Reviewing[/]",
        "testing": "[bright_magenta]🧪 Testing[/]",
        "done": "[bright_green]✅ Done[/]",
        "error": "[bright_red]❌ Error[/]",
    }

    for i, (name, info) in enumerate(agents.items(), 1):
        icon = info.get("icon", "🤖")
        status = status_icons.get(info.get("status", "idle"), "[dim]Unknown[/]")
        table.add_row(
            str(i),
            f"{icon} {name}",
            info.get("role", ""),
            status,
            info.get("model", "[dim]default[/dim]"),
            str(info.get("tokens", 0)),
        )

    console.print(table)
    console.print()


# ─────────────────────────────────────────────────────────────────
# MESSAGE DISPLAY
# ─────────────────────────────────────────────────────────────────
def show_user_message(message: str):
    """Display user input message."""
    panel = Panel(
        Text(message, style="bright_white"),
        title="[bold bright_green]👤 You[/]",
        title_align="left",
        border_style="bright_green",
        box=ROUNDED,
        padding=(0, 2),
    )
    console.print(panel)


def show_ai_response_start(agent_name: str = "NexaCode", icon: str = "🤖", color: str = "bright_cyan"):
    """Show the start of an AI response."""
    console.print(
        f"\n[bold {color}]{icon} {agent_name}[/] [dim]is responding...[/dim]"
    )
    console.print(f"[{color}]{'─' * 60}[/]")


def show_ai_response_end(agent_name: str = "", tokens: int = 0, time_taken: float = 0, color: str = "bright_cyan"):
    """Show the end of an AI response."""
    console.print(f"\n[{color}]{'─' * 60}[/]")
    stats = []
    if tokens:
        stats.append(f"[dim]🔤 {tokens:,} tokens[/]")
    if time_taken:
        stats.append(f"[dim]⏱️ {time_taken:.1f}s[/]")
    if stats:
        console.print(" ".join(stats))
    console.print()


def print_streaming_token(token: str):
    """Print a single streaming token without newline."""
    try:
        console.print(safe_text(token), end="", highlight=False)
    except UnicodeEncodeError:
        sys.stdout.write(token.encode('ascii', errors='replace').decode('ascii'))
        sys.stdout.flush()


def show_markdown_response(content: str, title: str = "Response"):
    """Display a full markdown response in a panel."""
    md = Markdown(content)
    panel = Panel(
        md,
        title=f"[bold bright_white]{title}[/]",
        border_style="bright_cyan",
        box=ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)


# ─────────────────────────────────────────────────────────────────
# CODE DISPLAY
# ─────────────────────────────────────────────────────────────────
def show_code(code: str, language: str = "python", title: str = "", line_numbers: bool = True):
    """Display syntax-highlighted code."""
    syntax = Syntax(
        code,
        language,
        theme="monokai",
        line_numbers=line_numbers,
        word_wrap=True,
    )
    if title:
        panel = Panel(
            syntax,
            title=f"[bold bright_white]📄 {title}[/]",
            border_style="bright_green",
            box=ROUNDED,
        )
        console.print(panel)
    else:
        console.print(syntax)


def show_diff(diff_text: str):
    """Display a colored diff."""
    for line in diff_text.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            console.print(f"[bright_green]{line}[/]")
        elif line.startswith("-") and not line.startswith("---"):
            console.print(f"[bright_red]{line}[/]")
        elif line.startswith("@@"):
            console.print(f"[bright_cyan]{line}[/]")
        else:
            console.print(f"[dim]{line}[/]")


# ─────────────────────────────────────────────────────────────────
# EXECUTION RESULTS
# ─────────────────────────────────────────────────────────────────
def show_execution_result(result: dict):
    """Display command execution results."""
    success = result.get("success", False)
    icon = "✅" if success else "❌"
    color = "bright_green" if success else "bright_red"

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="dim", width=12)
    table.add_column("Value")

    table.add_row("Command", f"[bold]{result.get('command', '')}[/]")
    table.add_row("Status", f"[{color}]{icon} Exit code: {result.get('exit_code', -1)}[/]")
    table.add_row("Time", f"{result.get('execution_time', 0):.2f}s")

    content_parts = [table]

    stdout = result.get("stdout", "")
    if stdout:
        content_parts.append(Text())
        content_parts.append(Text("stdout:", style="bold bright_green"))
        content_parts.append(Syntax(stdout[:3000], "text", theme="monokai", word_wrap=True))

    stderr = result.get("stderr", "")
    if stderr:
        content_parts.append(Text())
        content_parts.append(Text("stderr:", style="bold bright_red"))
        content_parts.append(Syntax(stderr[:3000], "text", theme="monokai", word_wrap=True))

    panel = Panel(
        Group(*content_parts),
        title=f"[bold {color}]⚡ Execution Result[/]",
        border_style=color,
        box=ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)


def show_test_results(results: dict):
    """Display test execution results."""
    passed = results.get("passed", 0)
    failed = results.get("failed", 0)
    total = passed + failed
    color = "bright_green" if failed == 0 else "bright_red"

    bar_width = 40
    pass_width = int((passed / max(total, 1)) * bar_width)
    fail_width = bar_width - pass_width

    bar = f"[bright_green]{'█' * pass_width}[/][bright_red]{'█' * fail_width}[/]"

    content = (
        f"  {bar}\n\n"
        f"  [bright_green]✅ Passed: {passed}[/]  |  [bright_red]❌ Failed: {failed}[/]  |  "
        f"[dim]Total: {total}[/]\n"
        f"  [dim]Coverage: {results.get('coverage', 'N/A')}[/]\n"
        f"  [dim]Time: {results.get('time', 'N/A')}[/]"
    )

    panel = Panel(
        content,
        title=f"[bold {color}]🧪 Test Results[/]",
        border_style=color,
        box=ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)


# ─────────────────────────────────────────────────────────────────
# FILE TREE DISPLAY
# ─────────────────────────────────────────────────────────────────
def show_file_tree(tree_data: List[Dict], root_name: str = "Project"):
    """Display a beautiful file tree."""
    rich_tree = Tree(
        f"[bold bright_cyan]📁 {root_name}[/]",
        guide_style="bright_cyan",
    )
    _build_rich_tree(rich_tree, tree_data)

    panel = Panel(
        rich_tree,
        title="[bold bright_white]📂 Project Structure[/]",
        border_style="bright_cyan",
        box=ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)


def _build_rich_tree(tree: Tree, items: List[Dict]):
    """Recursively build Rich tree."""
    file_icons = {
        ".py": "🐍", ".js": "📜", ".ts": "📘", ".tsx": "⚛️",
        ".html": "🌐", ".css": "🎨", ".json": "📋", ".md": "📝",
        ".yml": "⚙️", ".yaml": "⚙️", ".sql": "🗄️", ".sh": "🔧",
        ".go": "🔷", ".rs": "🦀", ".java": "☕", ".rb": "💎",
        ".env": "🔐", ".lock": "🔒", ".toml": "⚙️",
    }

    for item in items:
        if item["is_dir"]:
            branch = tree.add(
                f"[bold bright_cyan]📁 {item['name']}[/]"
            )
            if "children" in item:
                _build_rich_tree(branch, item["children"])
        else:
            ext = item.get("extension", "")
            icon = file_icons.get(ext, "📄")
            size = item.get("size", 0)
            size_str = _format_size(size)
            tree.add(f"{icon} [bright_white]{item['name']}[/] [dim]({size_str})[/]")


def _format_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.0f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


# ─────────────────────────────────────────────────────────────────
# MODEL & API DISPLAY
# ─────────────────────────────────────────────────────────────────
def show_models_table(models: Dict, active_model: str = ""):
    """Display configured models."""
    table = Table(
        title="[bold bright_white]🤖 Configured AI Models[/]",
        box=ROUNDED,
        border_style="bright_cyan",
        show_lines=True,
        padding=(0, 1),
    )
    table.add_column("", width=3, justify="center")
    table.add_column("Name", style="bold", width=20)
    table.add_column("Provider", width=14)
    table.add_column("Model ID", width=30)
    table.add_column("Base URL", width=30)
    table.add_column("Status", width=10, justify="center")

    provider_colors = {
        "openai": "bright_green",
        "anthropic": "bright_yellow",
        "gemini": "bright_blue",
        "openrouter": "bright_magenta",
        "groq": "bright_red",
        "deepseek": "bright_cyan",
        "ollama": "white",
        "custom": "bright_white",
    }

    for name, model in models.items():
        is_active = "▶️" if name == active_model else ""
        color = provider_colors.get(model.provider, "white")
        status = "[bright_green]●[/]" if model.enabled else "[dim]○[/]"
        base_url = model.base_url[:28] + ".." if len(model.base_url) > 30 else model.base_url

        table.add_row(
            is_active,
            f"[{color}]{name}[/]",
            f"[{color}]{model.provider}[/]",
            model.model_id,
            base_url or "[dim]default[/dim]",
            status,
        )

    console.print(table)
    console.print()


def show_providers_table():
    """Display available providers."""
    from nexacode.config.settings import DEFAULT_PROVIDERS

    table = Table(
        title="[bold bright_white]🌐 Supported AI Providers[/]",
        box=ROUNDED,
        border_style="bright_cyan",
        show_lines=True,
    )
    table.add_column("Provider", style="bold bright_cyan", width=14)
    table.add_column("Base URL", width=40)
    table.add_column("Models", width=40)

    for provider, info in DEFAULT_PROVIDERS.items():
        models = ", ".join(info["models"][:3])
        if len(info["models"]) > 3:
            models += f" (+{len(info['models']) - 3} more)"
        table.add_row(
            provider.title(),
            info["base_url"] or "[dim]Custom[/dim]",
            models or "[dim]User-defined[/dim]",
        )

    console.print(table)
    console.print()


# ─────────────────────────────────────────────────────────────────
# HELP & COMMANDS
# ─────────────────────────────────────────────────────────────────
def show_help():
    """Display simple, clean help - not confusing."""
    console.print()
    console.print("[bold bright_cyan]NexaCode Commands[/]\n")
    
    # Main commands - simple table
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
    )
    table.add_column("Command", style="bold bright_cyan", width=28)
    table.add_column("Description", style="bright_white")

    # Most important commands first
    table.add_row("[bold yellow]Just type anything[/]", "[bold]AI plans first -> you approve -> AI codes -> auto-runs[/]")
    table.add_row("", "")
    table.add_row("/ask <message>", "Ask AI (auto-creates project if none active)")
    table.add_row("/project new [name]", "New project (random name if blank)")
    table.add_row("/project open <name>", "Resume a saved project")
    table.add_row("/project list", "See all your projects")
    table.add_row("", "")
    table.add_row("/model add", "Add AI model (OpenAI, Gemini, etc)")
    table.add_row("/apikey <provider> <key>", "Set API key (openai, gemini, etc)")
    table.add_row("/model list", "See configured models")
    table.add_row("", "")
    table.add_row("/run <command>", "Run terminal command")
    table.add_row("/read <file>", "Read a file")
    table.add_row("/tree", "Show file tree")
    table.add_row("/clear", "Clear conversation")
    table.add_row("/help full", "Show ALL commands")
    table.add_row("/quit", "Exit NexaCode")

    panel = Panel(
        table,
        border_style="bright_cyan",
        box=ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)
    console.print(
        "\n[dim]How it works: You type -> AI thinks & plans -> You say 'ok' -> AI codes -> Auto-saves & runs[/dim]"
        "\n[dim]If error comes, AI auto-fixes it. Simple.[/dim]\n"
    )


def show_help_full():
    """Display ALL commands - for advanced users."""
    sections = [
        (
            "AI & Chat",
            [
                ("/ask <message>", "Ask AI (auto-creates project)"),
                ("/pipeline <task>", "Run full agent pipeline"),
                ("/agent <name>", "Switch agent (coder/architect/reviewer/tester/devops)"),
                ("/agents", "Show all agents"),
                ("/retry", "Retry last failed request"),
                ("/clear", "Clear conversation"),
            ],
        ),
        (
            "Project",
            [
                ("/project new [name]", "New project (random name if blank)"),
                ("/project open <name>", "Resume project with memory"),
                ("/project list", "List saved projects"),
                ("/project save", "Save project memory"),
                ("/project info <name>", "Project details"),
                ("/project close", "Close active project"),
                ("/project delete <name>", "Delete project memory"),
            ],
        ),
        (
            "Model",
            [
                ("/model add", "Add new model"),
                ("/model list", "List models"),
                ("/model use <name>", "Switch model"),
                ("/model remove <name>", "Remove model"),
                ("/providers", "See all providers"),
                ("/apikey <provider> <key>", "Set API key"),
            ],
        ),
        (
            "Files",
            [
                ("/read <path>", "Read file"),
                ("/write <path>", "Write file"),
                ("/edit <path>", "Edit file (find/replace)"),
                ("/save [all|1 2 3]", "Save AI-generated files"),
                ("/tree [path]", "File tree"),
                ("/glob <pattern>", "Search files by pattern"),
                ("/grep <pattern>", "Search file contents"),
                ("/mkdir <dir>", "Create directory"),
                ("/delete <path>", "Delete file/dir"),
                ("/move <src> <dst>", "Move/rename"),
                ("/copy <src> <dst>", "Copy"),
            ],
        ),
        (
            "Run & Test",
            [
                ("/run <command>", "Run shell command"),
                ("/exec <lang>", "Execute code"),
                ("/test [path]", "Run tests"),
                ("/lint [path]", "Run linter"),
                ("/install", "Install dependencies"),
            ],
        ),
        (
            "Session",
            [
                ("/session new <name>", "New session"),
                ("/session list", "List sessions"),
                ("/session load <id>", "Load session"),
                ("/history", "Chat history"),
                ("/search <query>", "Search history"),
                ("/usage", "Token usage"),
                ("/export", "Export session"),
            ],
        ),
        (
            "Settings",
            [
                ("/config", "Show config"),
                ("/config set <key> <val>", "Change setting"),
                ("/workspace <path>", "Change workspace"),
                ("/version", "Version info"),
                ("/stats", "Project stats"),
                ("/quit", "Exit"),
            ],
        ),
    ]

    for section_title, commands in sections:
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Command", style="bold bright_cyan", width=28)
        table.add_column("Description", style="bright_white")
        for cmd, desc in commands:
            table.add_row(cmd, desc)
        panel = Panel(
            table,
            title=f"[bold bright_white]{section_title}[/]",
            border_style="bright_cyan",
            box=ROUNDED,
            padding=(0, 1),
        )
        console.print(panel)
    console.print()


# ─────────────────────────────────────────────────────────────────
# PROGRESS & SPINNERS
# ─────────────────────────────────────────────────────────────────
def create_progress() -> Progress:
    """Create a styled progress bar."""
    return Progress(
        SpinnerColumn("dots", style="bright_cyan"),
        TextColumn("[bold bright_white]{task.description}[/]"),
        BarColumn(bar_width=30, style="bright_cyan", complete_style="bright_green"),
        TextColumn("[dim]{task.percentage:>3.0f}%[/]"),
        TimeElapsedColumn(),
        console=console,
    )


def create_spinner(message: str = "Thinking...") -> Progress:
    """Create a simple spinner."""
    return Progress(
        SpinnerColumn("dots12", style="bright_cyan"),
        TextColumn(f"[bold bright_white]{message}[/]"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )


# ─────────────────────────────────────────────────────────────────
# ERROR & WARNING DISPLAY
# ─────────────────────────────────────────────────────────────────
def show_error(message: str, title: str = "Error"):
    """Display an error message - ALWAYS in RED."""
    panel = Panel(
        Text(message, style="bold bright_red"),
        title=f"[bold bright_red]❌ {title}[/]",
        border_style="bright_red",
        box=ROUNDED,
        padding=(0, 2),
    )
    console.print(panel)


def show_warning(message: str):
    """Display a warning message - YELLOW."""
    console.print(f"[bold bright_yellow]⚠️  {message}[/]")


def show_success(message: str):
    """Display a success message - ALWAYS in GREEN."""
    console.print(f"[bold bright_green]✅ {message}[/]")


def show_info(message: str):
    """Display an info message - BLUE."""
    console.print(f"[bright_blue]ℹ️  {message}[/]")


# ─────────────────────────────────────────────────────────────────
# USAGE STATS DISPLAY
# ─────────────────────────────────────────────────────────────────
def show_usage_stats(stats: dict):
    """Display token usage and cost statistics."""
    table = Table(
        title="[bold bright_white]📊 Usage Statistics[/]",
        box=ROUNDED,
        border_style="bright_cyan",
        show_lines=True,
    )
    table.add_column("Model", style="bold bright_cyan")
    table.add_column("Requests", justify="right")
    table.add_column("Input Tokens", justify="right", style="bright_green")
    table.add_column("Output Tokens", justify="right", style="bright_yellow")
    table.add_column("Total Tokens", justify="right", style="bold")
    table.add_column("Cost", justify="right", style="bright_magenta")

    for model, data in stats.get("by_model", {}).items():
        total = (data.get("input_tokens", 0) or 0) + (data.get("output_tokens", 0) or 0)
        table.add_row(
            model,
            str(data.get("requests", 0)),
            f"{data.get('input_tokens', 0):,}",
            f"{data.get('output_tokens', 0):,}",
            f"{total:,}",
            f"${data.get('total_cost', 0):.4f}",
        )

    total = stats.get("total", {})
    total_tokens = (total.get("t_in", 0) or 0) + (total.get("t_out", 0) or 0)
    table.add_row(
        "[bold]TOTAL[/]",
        str(total.get("t_req", 0) or 0),
        f"{total.get('t_in', 0) or 0:,}",
        f"{total.get('t_out', 0) or 0:,}",
        f"[bold]{total_tokens:,}[/]",
        f"[bold]${total.get('t_cost', 0) or 0:.4f}[/]",
    )

    console.print(table)
    console.print()


# ─────────────────────────────────────────────────────────────────
# SESSION DISPLAY
# ─────────────────────────────────────────────────────────────────
def show_sessions_table(sessions: List[Dict]):
    """Display session list."""
    table = Table(
        title="[bold bright_white]💾 Sessions[/]",
        box=ROUNDED,
        border_style="bright_cyan",
        show_lines=True,
    )
    table.add_column("ID", style="dim", width=12)
    table.add_column("Name", style="bold bright_white", width=24)
    table.add_column("Workspace", width=30)
    table.add_column("Model", width=16)
    table.add_column("Created", width=20)

    for s in sessions:
        created = datetime.fromtimestamp(s.get("created_at", 0)).strftime("%Y-%m-%d %H:%M")
        table.add_row(
            s.get("id", "")[:12],
            s.get("name", ""),
            s.get("workspace", ""),
            s.get("model", ""),
            created,
        )

    console.print(table)
    console.print()


# ─────────────────────────────────────────────────────────────────
# CONVERSATION HISTORY
# ─────────────────────────────────────────────────────────────────
def show_history(messages: List[Dict]):
    """Display conversation history."""
    if not messages:
        show_info("No messages in history.")
        return

    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        agent = msg.get("agent_name", "")
        ts = datetime.fromtimestamp(msg.get("timestamp", 0)).strftime("%H:%M:%S")

        if role == "user":
            console.print(f"[dim]{ts}[/] [bold bright_green]👤 You:[/] {content[:200]}")
        elif role == "assistant":
            name = agent or "AI"
            console.print(f"[dim]{ts}[/] [bold bright_cyan]🤖 {name}:[/] {content[:200]}")
        console.print()


# ─────────────────────────────────────────────────────────────────
# PROJECT STATS DISPLAY
# ─────────────────────────────────────────────────────────────────
def show_project_stats(stats: dict):
    """Display project statistics."""
    content_parts = []

    overview = Table(show_header=False, box=None, padding=(0, 2))
    overview.add_column("Metric", style="bright_cyan", width=20)
    overview.add_column("Value", style="bright_white")
    overview.add_row("📄 Total Files", str(stats.get("total_files", 0)))
    overview.add_row("📁 Total Dirs", str(stats.get("total_dirs", 0)))
    overview.add_row("💾 Total Size", _format_size(stats.get("total_size", 0)))
    content_parts.append(overview)

    # By extension
    if stats.get("by_extension"):
        ext_table = Table(
            title="[bold]Files by Type[/]",
            show_header=True,
            box=SIMPLE_HEAVY,
            padding=(0, 1),
        )
        ext_table.add_column("Extension", style="bright_cyan")
        ext_table.add_column("Count", justify="right", style="bright_white")

        sorted_ext = sorted(stats["by_extension"].items(), key=lambda x: x[1], reverse=True)
        for ext, count in sorted_ext[:15]:
            ext_table.add_row(ext, str(count))
        content_parts.append(Text())
        content_parts.append(ext_table)

    panel = Panel(
        Group(*content_parts),
        title="[bold bright_white]📊 Project Statistics[/]",
        border_style="bright_cyan",
        box=ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)
    console.print()


# ─────────────────────────────────────────────────────────────────
# PIPELINE PROGRESS
# ─────────────────────────────────────────────────────────────────
def show_pipeline_start(pipeline: List[str]):
    """Show pipeline execution start."""
    agents_str = " → ".join(
        f"[bold bright_cyan]{name}[/]" for name in pipeline
    )
    console.print(
        Panel(
            f"  🔄 Pipeline: {agents_str}\n"
            f"  [dim]Executing multi-agent pipeline...[/dim]",
            title="[bold bright_white]🚀 Agent Pipeline[/]",
            border_style="bright_magenta",
            box=ROUNDED,
            padding=(0, 2),
        )
    )
    console.print()


def show_pipeline_result(result: dict):
    """Show pipeline completion summary."""
    table = Table(show_header=True, box=ROUNDED, border_style="bright_cyan")
    table.add_column("Agent", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Time", justify="right")
    table.add_column("Tokens", justify="right")

    for agent_result in result.get("results", []):
        status_icon = "✅" if agent_result.get("status") == "done" else "❌"
        table.add_row(
            f"{agent_result.get('icon', '🤖')} {agent_result['agent_name']}",
            status_icon,
            f"{agent_result.get('execution_time', 0):.1f}s",
            str(agent_result.get("tokens_used", 0)),
        )

    console.print(
        Panel(
            table,
            title="[bold bright_white]🎯 Pipeline Complete[/]",
            border_style="bright_green",
            box=ROUNDED,
            padding=(1, 2),
        )
    )
