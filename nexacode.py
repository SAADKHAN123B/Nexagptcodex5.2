#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║    ███╗   ██╗███████╗██╗  ██╗ █████╗  ██████╗ ██████╗ ██████╗ ███████╗  ║
║    ████╗  ██║██╔════╝╚██╗██╔╝██╔══██╗██╔════╝██╔═══██╗██╔══██╗██╔════╝  ║
║    ██╔██╗ ██║█████╗   ╚███╔╝ ███████║██║     ██║   ██║██║  ██║█████╗    ║
║    ██║╚██╗██║██╔══╝   ██╔██╗ ██╔══██║██║     ██║   ██║██║  ██║██╔══╝    ║
║    ██║ ╚████║███████╗██╔╝ ╚██╗██║  ██║╚██████╗╚██████╔╝██████╔╝███████╗  ║
║    ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝  ║
║                                                                          ║
║              AI-Powered Terminal Coding Assistant v2.1                    ║
║          Multi-Agent • Multi-Model • Full Stack Development              ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝

NexaCode — The Ultimate Terminal AI Coding Assistant

Like Claude Code, but running locally in YOUR terminal, with YOUR choice of AI models.
Supports OpenAI, Anthropic, Google Gemini, Groq, DeepSeek, Ollama, LM Studio,
OpenRouter, Together AI, or ANY custom OpenAI-compatible endpoint.

Features:
  • 5 Specialized AI Agents (Architect, Coder, Reviewer, Tester, DevOps)
  • Full File Manager (Read, Write, Edit, Glob, Grep, Tree)
  • Code Execution in 12+ Languages
  • Multi-Agent Pipeline (Architect → Coder → Reviewer → Tester)
  • Session Persistence with SQLite Database
  • Real-time Streaming Responses
  • Custom API Endpoint Support
  • Auto-Complete & Command History
  • Beautiful Rich Terminal UI

Usage:
  python3 nexacode.py                    # Start in current directory
  python3 nexacode.py --workspace /path  # Start in specific directory
  python3 nexacode.py --model gpt-4o     # Start with specific model
  python3 nexacode.py --setup            # Run interactive setup wizard
"""

import os
import sys
import uuid
import asyncio
import argparse
from pathlib import Path

# ─────────────────────────────────────────────────────────────────
# FORCE UTF-8 encoding — fixes UnicodeEncodeError on Termux/Android
# Must be done BEFORE any rich/print output
# ─────────────────────────────────────────────────────────────────
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
import io as _io
if hasattr(sys.stdout, 'buffer'):
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
            sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────
# Ensure our package is importable
# ─────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="nexacode",
        description="NexaCode — AI-Powered Terminal Coding Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nexacode                              Start in current directory
  nexacode --workspace ~/myproject      Start in specific directory  
  nexacode --setup                      Run first-time setup wizard
  nexacode --model gpt-4o               Use specific model
  nexacode --agent architect            Start with architect agent
  nexacode --provider openai --apikey sk-xxx  Quick API key setup
        """,
    )
    parser.add_argument(
        "--workspace", "-w",
        type=str,
        default=os.getcwd(),
        help="Working directory (default: current directory)",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="",
        help="AI model to use",
    )
    parser.add_argument(
        "--agent", "-a",
        type=str,
        default="coder",
        help="Active agent (architect/coder/reviewer/tester/devops)",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run interactive setup wizard",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="",
        help="AI provider for quick setup",
    )
    parser.add_argument(
        "--apikey",
        type=str,
        default="",
        help="API key for quick setup",
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Skip the startup banner",
    )
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version and exit",
    )
    return parser.parse_args()


async def run_setup_wizard(config):
    """Interactive first-time setup.
    
    FIXED: Use run_in_executor for prompt_toolkit to avoid
    asyncio.run() conflict in running event loop.
    """
    from nexacode.ui import terminal as ui
    from nexacode.config.settings import DEFAULT_PROVIDERS, ModelConfig

    ui.console.print("\n[bold bright_cyan]🧙 NexaCode Setup Wizard[/]\n")
    ui.console.print("[dim]Let's configure your AI model. You can always change this later with /model add[/dim]\n")

    ui.show_providers_table()

    try:
        loop = asyncio.get_event_loop()

        def _sync_prompt(message: str, default: str = "") -> str:
            """Synchronous prompt for use in executor."""
            try:
                from prompt_toolkit import prompt as pt_prompt
                result = pt_prompt(message)
                return result.strip() if result else default
            except (KeyboardInterrupt, EOFError):
                return default

        provider = await loop.run_in_executor(
            None, _sync_prompt,
            "Choose provider (openai/anthropic/gemini/groq/deepseek/ollama/custom): ", ""
        )
        provider = provider.lower()
        if not provider:
            ui.show_warning("Setup skipped. Use /model add later.")
            return

        provider_info = DEFAULT_PROVIDERS.get(provider, {})

        if provider in ("ollama", "lmstudio"):
            # Local models don't need API keys
            base_url = provider_info.get("base_url", "")
            model_id = await loop.run_in_executor(
                None, _sync_prompt,
                f"Model name (e.g., llama3.2, codellama): ", "llama3.2"
            )
            api_key = ""
        else:
            api_key = await loop.run_in_executor(
                None, _sync_prompt,
                f"Enter your {provider.title()} API key: ", ""
            )
            if not api_key:
                ui.show_warning("No API key provided. Setup skipped.")
                return

            models = provider_info.get("models", [])
            if models:
                ui.console.print(f"\n[bold]Available models:[/]")
                for i, m in enumerate(models, 1):
                    ui.console.print(f"  [bright_cyan]{i}[/]. {m}")
                choice = await loop.run_in_executor(
                    None, _sync_prompt,
                    f"\nChoose model number [1]: ", "1"
                )
                idx = int(choice) - 1 if choice.isdigit() else 0
                model_id = models[min(idx, len(models) - 1)]
            else:
                model_id = await loop.run_in_executor(
                    None, _sync_prompt,
                    "Model ID: ", ""
                )

            base_url = provider_info.get("base_url", "")

        # Fix: avoid double-prefix (gemini-gemini-2.5-flash)
        short_id = model_id.split('/')[-1]
        if short_id.startswith(provider):
            name = short_id
        else:
            name = f"{provider}-{short_id}"
        model_config = ModelConfig(
            name=name,
            provider=provider,
            model_id=model_id,
            api_key=api_key,
            base_url=base_url,
        )

        config.add_model(name, model_config)
        config.active_model = name
        if api_key:
            config.save_api_key(provider, api_key)
        config.save_config()

        ui.show_success(f"\n✅ Setup complete! Model '{name}' configured and active.\n")

    except (KeyboardInterrupt, EOFError):
        ui.show_warning("\nSetup cancelled.")
    except Exception as e:
        ui.show_warning(f"Setup error: {e}. Use /model add later.")


async def main():
    """Main entry point for NexaCode."""
    args = parse_args()

    # ─── IMPORTS ───
    from nexacode.config.settings import NexaCodeConfig, APP_VERSION, APP_CODENAME
    from nexacode.core.engine import AIEngine
    from nexacode.agents.orchestrator import AgentOrchestrator
    from nexacode.tools.file_manager import FileManager
    from nexacode.tools.executor import CodeExecutor
    from nexacode.db.database import Database
    from nexacode.core.commands import CommandHandler
    from nexacode.ui import terminal as ui
    from nexacode.ui.prompt import create_prompt_session, get_prompt_message

    # ─── VERSION CHECK ───
    if args.version:
        print(f"NexaCode v{APP_VERSION} '{APP_CODENAME}'")
        sys.exit(0)

    # ─── INITIALIZE CONFIG ───
    config = NexaCodeConfig()
    config.workspace = os.path.abspath(args.workspace)

    if args.model:
        config.active_model = args.model
    if args.agent:
        config.active_agent = args.agent

    # Quick API key setup
    if args.provider and args.apikey:
        provider = args.provider.lower()
        config.save_api_key(provider, args.apikey)
        from nexacode.config.settings import DEFAULT_PROVIDERS, ModelConfig
        provider_info = DEFAULT_PROVIDERS.get(provider, {})
        if provider_info and provider_info.get("models"):
            default_model = provider_info["models"][0]
            # Model name: use short ID after last slash (e.g. "gemini-2.5-flash")
            # For non-slash models like "gemini-2.5-flash", split('/')[-1] returns the whole string
            short_id = default_model.split('/')[-1]
            # Avoid duplication: if short_id already starts with provider name, don't prepend
            if short_id.startswith(provider):
                model_name = short_id
            else:
                model_name = f"{provider}-{short_id}"
            mc = ModelConfig(
                name=model_name,
                provider=provider,
                model_id=default_model,
                api_key=args.apikey,
                base_url=provider_info.get("base_url", ""),
            )
            config.add_model(mc.name, mc)
            # Also purge any stale model configs with wrong names from old versions
            stale_keys = [
                k for k in list(config.models.keys())
                if k != model_name and k.startswith(f"{provider}-{provider}")
            ]
            for k in stale_keys:
                config.remove_model(k)

    # ─── INITIALIZE COMPONENTS ───
    engine = AIEngine(config)
    orchestrator = AgentOrchestrator(config, engine)
    file_manager = FileManager(config.workspace)
    executor = CodeExecutor(config.workspace)
    database = Database()
    await database.connect()

    handler = CommandHandler(
        config=config,
        engine=engine,
        orchestrator=orchestrator,
        file_manager=file_manager,
        executor=executor,
        database=database,
    )

    # Create session
    session_name = f"session-{Path(config.workspace).name}"
    await database.create_session(
        handler.session_id, session_name,
        workspace=config.workspace,
        model=config.active_model,
        agent=config.active_agent,
    )

    # ─── BANNER ───
    if not args.no_banner:
        ui.show_banner()
        ui.show_welcome(
            workspace=config.workspace,
            model=config.active_model,
            session=handler.session_id,
        )

    # ─── SETUP WIZARD ───
    if args.setup or not config.models:
        if not config.models:
            ui.console.print(
                "[bright_yellow]⚠️  No AI models configured. Let's set one up![/]\n"
            )
        await run_setup_wizard(config)
        # Reinitialize engine with new config
        engine = AIEngine(config)
        orchestrator = AgentOrchestrator(config, engine)
        handler.engine = engine
        handler.orchestrator = orchestrator

    # ─── QUICK START TIPS ───
    if not args.no_banner:
        if config.active_model:
            ui.console.print(
                f"[dim]Type anything to start -> AI plans -> you approve -> AI codes -> auto-runs[/dim]\n"
                f"[dim]Type / or /help for commands[/dim]\n"
            )
        else:
            ui.console.print(
                "[bright_yellow]Setup needed:[/]\n"
                "  [bright_cyan]/apikey gemini YOUR_KEY[/]\n"
                "  [bright_cyan]/apikey openai YOUR_KEY[/]\n"
                "  [bright_cyan]/model add[/]  (interactive setup)\n"
            )

    # ─── MAIN LOOP ───
    prompt_session = create_prompt_session(config.workspace)

    while True:
        try:
            prompt_msg = get_prompt_message(config.workspace, config.active_agent)
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: prompt_session.prompt(prompt_msg),
            )

            if not user_input.strip():
                continue

            should_continue = await handler.handle(user_input)
            if not should_continue:
                break

        except KeyboardInterrupt:
            ui.console.print("\n[dim]Use /quit to exit[/dim]")
            continue
        except EOFError:
            break
        except Exception as e:
            try:
                ui.show_error(f"Unexpected error: {type(e).__name__}: {str(e)}")
            except UnicodeEncodeError:
                sys.stderr.write(f"Error: {type(e).__name__}: {str(e)}\n")
            continue

    # ─── CLEANUP ───
    # Auto-save project memory before exiting
    if handler._active_project_name:
        try:
            await handler._auto_save_project_memory()
        except Exception:
            pass
    ui.console.print("\n[bold bright_cyan]Thanks for using NexaCode! Happy coding![/]\n")
    config.save_config()
    await engine.close()
    await database.close()


def entry_point():
    """CLI entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        try:
            print("\n\nGoodbye!")
        except UnicodeEncodeError:
            sys.stdout.write("\n\nGoodbye!\n")
        sys.exit(0)
    except UnicodeEncodeError:
        sys.stderr.write(
            "\nUnicodeEncodeError: Set PYTHONIOENCODING=utf-8\n"
            "Run:  export PYTHONIOENCODING=utf-8  then try again.\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    entry_point()
