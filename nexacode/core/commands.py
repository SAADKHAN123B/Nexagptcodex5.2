"""
+======================================================================+
|                    NEXACODE COMMAND HANDLER v2.1                      |
|             Process All User Commands & Interactions                  |
|     Fixed: Auto-save code blocks, Smart prompts, Better errors,      |
|            /model add asyncio fix, prompt_toolkit compatibility       |
+======================================================================+
"""

import os
import re
import sys
import uuid
import random
import asyncio
from typing import Optional
from pathlib import Path

from nexacode.config.settings import (
    NexaCodeConfig, ModelConfig, AgentConfig,
    DEFAULT_PROVIDERS, APP_VERSION, APP_CODENAME, APP_NAME,
    TASK_SYSTEM_PROMPTS, detect_task_type,
)
from nexacode.core.engine import AIEngine
from nexacode.agents.orchestrator import AgentOrchestrator, AgentStatus
from nexacode.tools.file_manager import FileManager
from nexacode.tools.executor import CodeExecutor
from nexacode.db.database import Database
from nexacode.ui import terminal as ui
from nexacode.utils.helpers import extract_code_blocks, extract_file_actions
from nexacode.ui.terminal import safe_text


class CommandHandler:
    """Handles all user commands and interactions.
    
    v3.0 'Deep-Think' Enhancements:
    - Task-specific system prompts (planning, coding, debugging, etc.)
    - Plan-then-Execute workflow (AI plans -> user approves -> AI codes)
    - Auto-save code to files (not chat paste)
    - Auto-execute terminal commands after coding
    - Project folder isolation (each project gets its own folder)
    """

    # States for plan-then-execute workflow
    STATE_IDLE = "idle"
    STATE_PLAN_SHOWN = "plan_shown"       # Plan shown, waiting for user approval
    STATE_CODING = "coding"               # Approved, AI is generating code

    def __init__(
        self,
        config: NexaCodeConfig,
        engine: AIEngine,
        orchestrator: AgentOrchestrator,
        file_manager: FileManager,
        executor: CodeExecutor,
        database: Database,
    ):
        self.config = config
        self.engine = engine
        self.orchestrator = orchestrator
        self.fm = file_manager
        self.executor = executor
        self.db = database
        self.session_id = str(uuid.uuid4())[:8]
        self._pending_files: list = []  # Files detected in AI response
        self._state = self.STATE_IDLE
        self._pending_plan: str = ""     # The plan waiting for approval
        self._pending_task: str = ""     # The original user request
        self._current_project_folder: str = ""  # Active project folder name
        self._active_project_name: str = ""  # v3.1: active project memory name
        self._project_memory_cache: dict = {}  # v3.1: cached project memory data

    async def handle(self, user_input: str) -> bool:
        """
        Handle user input. Returns False if should exit.
        
        v3.0: Supports plan-then-execute workflow.
        v3.1: Added project memory - auto-saves context per project.
        When AI shows a plan, user says 'ok/start/go' to approve.
        """
        text = user_input.strip()
        if not text:
            return True

        # --- EXIT (auto-save project memory before quitting) ---
        if text.lower() in ("/quit", "/exit", "/q", "exit", "quit"):
            await self._auto_save_project_memory()
            return False

        # --- SLASH COMMANDS ---
        if text.startswith("/"):
            # Special: just "/" alone = show help
            if text.strip() == "/":
                ui.show_help()
                return True
            await self._handle_command(text)
            return True

        # --- PLAN APPROVAL CHECK ---
        if self._state == self.STATE_PLAN_SHOWN:
            approval_words = [
                "ok", "okay", "yes", "y", "start", "go", "go ahead",
                "approved", "looks good", "perfect", "do it", "proceed",
                "theek hai", "theek", "sahi hai", "sahi", "haan",
                "han", "karo", "kar do", "shuru", "shuru karo",
                "chalo", "bana do", "likh do", "kardo", "karde",
                "start karo", "start kardo", "ok start",
            ]
            text_lower = text.lower().strip()
            is_approval = any(word == text_lower or text_lower.startswith(word + " ") for word in approval_words)
            
            if is_approval:
                ui.console.print("\n[bold bright_green]\u2705 Plan approved! Starting code generation...[/]\n")
                self._state = self.STATE_CODING
                await self._execute_plan()
                return True
            elif text_lower in ("no", "nahi", "cancel", "nah", "change", "badal"):
                self._state = self.STATE_IDLE
                self._pending_plan = ""
                self._pending_task = ""
                ui.show_info("Plan cancelled. Tell me what you'd like to change.")
                return True
            else:
                ui.console.print("\n[bright_yellow]\ud83d\udd04 Updating plan with your feedback...[/]\n")
                combined = f"Original task: {self._pending_task}\n\nPrevious plan:\n{self._pending_plan}\n\nUser feedback: {text}\n\nPlease create an updated plan incorporating the user's feedback."
                self._pending_task = combined
                await self._chat_with_ai(combined, force_task_type="planning")
                return True

        # --- NATURAL LANGUAGE -> AI ---
        await self._chat_with_ai(text)
        return True

    # =================================================================
    # COMMAND ROUTER
    # =================================================================
    async def _handle_command(self, text: str):
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        command_map = {
            "/help": lambda: ui.show_help() if not args else (ui.show_help_full() if args.strip() == "full" else ui.show_help()),
            "/": lambda: ui.show_help(),
            "/version": lambda: self._show_version(),
            "/clear": lambda: self._clear_conversation(),
            "/agents": lambda: self._show_agents(),
            "/providers": lambda: ui.show_providers_table(),
            "/stats": lambda: self._show_project_stats(),
        }

        # Simple commands (no args needed)
        if cmd in command_map:
            if cmd == "/help":
                # /help or /help full
                result = command_map[cmd]()
            elif not args:
                result = command_map[cmd]()
            else:
                result = None
            if result is not None and asyncio.iscoroutine(result):
                await result
            if cmd in command_map and (not args or cmd == "/help" or cmd == "/"):
                return

        # Complex commands
        if cmd == "/model":
            await self._handle_model_command(args)
        elif cmd == "/agent":
            self._switch_agent(args)
        elif cmd == "/apikey":
            self._set_api_key(args)
        elif cmd == "/ask":
            await self._chat_with_ai(args)
        elif cmd == "/pipeline":
            await self._run_pipeline(args)
        elif cmd == "/read":
            self._read_file(args)
        elif cmd == "/write":
            await self._write_file_interactive(args)
        elif cmd == "/edit":
            await self._edit_file_interactive(args)
        elif cmd == "/tree":
            self._show_tree(args)
        elif cmd == "/glob":
            self._glob_search(args)
        elif cmd == "/grep":
            self._grep_search(args)
        elif cmd == "/run":
            await self._run_command(args)
        elif cmd == "/exec":
            await self._exec_code_interactive(args)
        elif cmd == "/test":
            await self._run_tests(args)
        elif cmd == "/lint":
            await self._run_lint(args)
        elif cmd == "/install":
            await self._install_deps(args)
        elif cmd == "/session":
            await self._handle_session_command(args)
        elif cmd == "/history":
            await self._show_history()
        elif cmd == "/search":
            await self._search_history(args)
        elif cmd == "/usage":
            await self._show_usage()
        elif cmd == "/workspace":
            self._change_workspace(args)
        elif cmd == "/config":
            self._handle_config(args)
        elif cmd == "/export":
            await self._export_session()
        elif cmd == "/diff":
            self._show_diff(args)
        elif cmd == "/mkdir":
            self._mkdir(args)
        elif cmd == "/delete":
            self._delete_path(args)
        elif cmd == "/move":
            self._move_path(args)
        elif cmd == "/copy":
            self._copy_path(args)
        elif cmd == "/save":
            await self._save_pending_files(args)
        elif cmd == "/project":
            await self._handle_project_command(args)
        elif cmd == "/retry":
            await self._retry_last()
        else:
            ui.show_error(f"Unknown command: {cmd}\nType /help for available commands.")

    # =================================================================
    # AI CHAT - v3.0 with task detection, planning, and auto-execute
    # =================================================================
    async def _chat_with_ai(self, message: str, force_task_type: str = ""):
        """Chat with AI using task-specific system prompts.
        
        v3.2 enhancements:
        - Auto-create project with random name if /ask used without project
        - Project memory context injection
        - Auto-read existing project files before editing/coding
        - Auto-save project memory after each interaction
        - Auto-run and auto-fix errors after coding
        """
        if not message:
            ui.show_warning("Please provide a message.")
            return

        if not self.config.active_model:
            ui.show_error(
                "No model configured!\n\n"
                "Quick setup:\n"
                "  /apikey gemini YOUR_KEY\n"
                "  /apikey openai YOUR_KEY\n"
                "  /model add\n\n"
                "Run /providers to see all supported AI providers"
            )
            return

        # v3.2: AUTO-CREATE PROJECT if no active project
        if not self._active_project_name:
            project_name = self._generate_random_project_name()
            self._active_project_name = project_name
            self._current_project_folder = project_name
            self._project_memory_cache = {}
            # Create project directory
            project_dir = Path(self.config.workspace) / project_name
            project_dir.mkdir(parents=True, exist_ok=True)
            # Initialize memory in database
            await self.db.save_project_memory(
                project_name=project_name,
                workspace=str(project_dir),
                summary=f"Auto-created project: {project_name}",
                files_list=[],
                tech_stack="",
                last_task=message[:200],
                conversation_snapshot=[],
            )
            # Clear conversation for fresh start
            self.engine.get_conversation().clear()
            ui.console.print(
                f"\n[bold bright_green]Project auto-created: [bright_cyan]{project_name}[/bright_cyan][/]\n"
            )

        # Detect task type
        task_type = force_task_type or detect_task_type(message)
        
        # Get task-specific system prompt
        task_prompt = TASK_SYSTEM_PROMPTS.get(task_type, TASK_SYSTEM_PROMPTS["default"])

        ui.show_user_message(message)

        agent_config = self.config.agents.get(self.config.active_agent)
        icon = agent_config.icon if agent_config else "~"
        color = agent_config.color if agent_config else "bright_cyan"
        name = agent_config.name if agent_config else "NexaCode"

        # Show task type indicator
        task_icons = {
            "planning": "\ud83e\udde0 Planning",
            "coding": "\ud83d\udcbb Coding",
            "debugging": "\ud83d\udc1b Debugging",
            "editing": "\u270f\ufe0f Editing",
            "explaining": "\ud83d\udcda Explaining",
            "reviewing": "\ud83d\udd0d Reviewing",
            "default": "\ud83e\udd16 Thinking",
        }
        task_label = task_icons.get(task_type, "\ud83e\udd16 Processing")
        ui.console.print(f"\n[dim]\u2500 Mode: [bold bright_cyan]{task_label}[/bold bright_cyan][/dim]")

        # v3.1: Read existing project files for editing/coding/debugging tasks
        code_context = ""
        if task_type in ("editing", "debugging", "coding") and self._current_project_folder:
            code_context = self._read_project_code_context()
            if code_context:
                ui.console.print(f"[dim]\u2500 \ud83d\udcc2 Loaded existing project code into context[/dim]")

        # v3.1: Load project memory context
        memory_context = ""
        if self._active_project_name:
            mem = await self.db.get_project_memory(self._active_project_name)
            if mem:
                memory_context = self._format_memory_context(mem)
                ui.console.print(f"[dim]\u2500 \ud83e\udde0 Project memory loaded: {self._active_project_name}[/dim]")

        # Enhance system prompt with workspace context + memory + code
        enhanced_prompt = self._build_enhanced_system_prompt(
            task_prompt, memory_context=memory_context, code_context=code_context
        )

        # Show thinking indicator for thinking models
        model_config = self.config.get_active_model()
        is_thinking = model_config and self.engine._is_thinking_model(model_config)
        if is_thinking:
            ui.console.print(f"[dim]\u2500 \ud83e\udde0 Deep thinking enabled (Gemini reasoning mode)[/dim]")

        ui.show_ai_response_start(name, icon, color)

        import time
        start_time = time.time()
        full_response = ""

        async for chunk in self.engine.chat(
            prompt=message,
            system_prompt=enhanced_prompt,
            stream=True,
        ):
            ui.print_streaming_token(chunk)
            full_response += chunk

        elapsed = time.time() - start_time
        ui.show_ai_response_end(name, len(full_response) // 4, elapsed, color)

        # Save to database
        await self.db.save_message(self.session_id, "user", message)
        await self.db.save_message(
            self.session_id, "assistant", full_response,
            agent_name=name, model=self.config.active_model,
        )

        # --- TASK-SPECIFIC POST-PROCESSING ---
        if task_type == "planning":
            # Auto-detect project name from plan
            self._auto_detect_project_name(full_response, message)
            
            self._state = self.STATE_PLAN_SHOWN
            self._pending_plan = full_response
            self._pending_task = message
            ui.console.print("\n[bold bright_yellow]Review the plan above.[/]")
            ui.console.print("[bright_cyan]  ok / start  [/] [dim]-> approve & start coding[/dim]")
            ui.console.print("[bright_cyan]  no / cancel  [/] [dim]-> cancel plan[/dim]")
            ui.console.print("[bright_cyan]  anything else [/] [dim]-> update plan with your feedback[/dim]\n")
        else:
            # For non-planning tasks: auto-detect files and auto-save
            files_found = self._detect_files_in_response(full_response)
            if files_found:
                await self._auto_save_files(files_found)
            
            # Auto-detect and run commands
            commands_found = self._detect_commands_in_response(full_response)
            if commands_found:
                error_output = await self._auto_execute_commands_with_fix(commands_found)
                # v3.2: AUTO-FIX ERRORS
                if error_output:
                    await self._auto_fix_errors(error_output, full_response)

        # v3.1: Auto-save project memory after every AI interaction
        await self._auto_save_project_memory()

    async def _execute_plan(self):
        """Execute the approved plan - generate actual code.
        
        v3.3: MASSIVELY improved prompt to force AI to write real code,
        not just describe what code to write.
        """
        # Extract file paths from the plan for emphasis
        import re
        file_paths = re.findall(r'[\w\-]+/[\w\-/\.]+\.\w{1,10}', self._pending_plan)
        file_list = "\n".join(f"  - {fp}" for fp in file_paths[:20]) if file_paths else "  (see plan above)"

        coding_prompt = (
            f"## TASK: WRITE ALL THE CODE NOW\n\n"
            f"The user APPROVED the plan below. Your job now is to OUTPUT ACTUAL CODE.\n\n"
            f"### WHAT YOU MUST DO:\n"
            f"Write the FULL, COMPLETE source code for EVERY file.\n"
            f"Each file must be in its own code block starting with # File: path\n\n"
            f"### FILES TO GENERATE (write ALL of these):\n{file_list}\n\n"
            f"### APPROVED PLAN:\n{self._pending_plan}\n\n"
            f"### ORIGINAL REQUEST:\n{self._pending_task}\n\n"
            f"### CRITICAL INSTRUCTIONS:\n"
            f"1. Output ACTUAL CODE — not descriptions, not summaries, not file lists\n"
            f"2. Every code block = one complete file with # File: header\n"
            f"3. Write EVERY LINE of code — no placeholders, no TODOs, no '...'\n"
            f"4. Include ALL imports, ALL functions, ALL routes, ALL HTML\n"
            f"5. After all files, add a ```commands``` block to run the project\n\n"
            f"### START WRITING CODE NOW — file by file:\n"
        )
        self._state = self.STATE_IDLE
        await self._chat_with_ai(coding_prompt, force_task_type="coding")

    def _build_enhanced_system_prompt(self, base_prompt: str, memory_context: str = "", code_context: str = "") -> str:
        """Build an enhanced system prompt with workspace context, memory, and code."""
        workspace_info = f"\n\n## WORKSPACE CONTEXT\n"
        workspace_info += f"- Working directory: {self.config.workspace}\n"

        if self._current_project_folder:
            workspace_info += f"- Active project folder: {self._current_project_folder}\n"
            workspace_info += f"  IMPORTANT: ALL files MUST be saved inside '{self._current_project_folder}/' folder!\n"
            workspace_info += f"  Use paths like: {self._current_project_folder}/app.py, {self._current_project_folder}/templates/index.html\n"

        ws = Path(self.config.workspace)
        if (ws / "package.json").exists():
            workspace_info += "- Project type: Node.js/JavaScript\n"
        elif (ws / "requirements.txt").exists():
            workspace_info += "- Project type: Python\n"
        elif (ws / "Cargo.toml").exists():
            workspace_info += "- Project type: Rust\n"
        elif (ws / "go.mod").exists():
            workspace_info += "- Project type: Go\n"
        elif (ws / "pom.xml").exists():
            workspace_info += "- Project type: Java\n"

        # v3.1: Inject project memory context
        if memory_context:
            workspace_info += f"\n## PROJECT MEMORY (from previous sessions)\n{memory_context}\n"

        # v3.1: Inject existing code context
        if code_context:
            workspace_info += f"\n## EXISTING PROJECT CODE (read before making changes!)\n"
            workspace_info += "IMPORTANT: Read and understand ALL existing code below before modifying ANYTHING.\n"
            workspace_info += "Preserve existing functionality. Only change what the user asks to change.\n"
            workspace_info += code_context + "\n"

        workspace_info += "\n## FILE FORMAT RULES (CRITICAL!)\n"
        workspace_info += "When creating files, you MUST use this format for auto-save:\n"
        if self._current_project_folder:
            workspace_info += f"IMPORTANT: Use '{self._current_project_folder}/' as the project folder prefix!\n"
            workspace_info += f"```language\n# File: {self._current_project_folder}/path/to/file.ext\n<complete file content>\n```\n"
            workspace_info += f"\nFor HTML files:\n"
            workspace_info += f"```html\n<!-- File: {self._current_project_folder}/templates/index.html -->\n<complete content>\n```\n"
        else:
            workspace_info += "```language\n# File: project-folder/path/to/file.ext\n<complete file content>\n```\n"
            workspace_info += "\nFor HTML files:\n"
            workspace_info += "```html\n<!-- File: project-folder/templates/index.html -->\n<complete content>\n```\n"
        workspace_info += "\n## PROJECT FOLDER RULE\n"
        workspace_info += "EVERY project MUST have its own folder. Never put files in workspace root.\n"
        if self._current_project_folder:
            workspace_info += f"Current project folder: {self._current_project_folder}/\n"
        else:
            workspace_info += "Example: my-todo-app/app.py, my-todo-app/templates/index.html\n"
        workspace_info += "\n## COMMANDS FORMAT\n"
        workspace_info += "Wrap terminal commands in ```commands``` block for auto-execution:\n"
        if self._current_project_folder:
            workspace_info += f"```commands\ncd {self._current_project_folder}\npip install -r requirements.txt\npython app.py\n```\n"
        else:
            workspace_info += "```commands\ncd project-folder\npip install -r requirements.txt\npython app.py\n```\n"

        return base_prompt + workspace_info

    def _detect_and_offer_save(self, response: str):
        """Legacy: Detect code blocks with file paths and offer to save.
        
        v3.0 Note: Auto-save is now the primary method. This is kept
        as fallback for /save command compatibility.
        """
        self._pending_files = self._detect_files_in_response(response)

    def _detect_files_in_response(self, response: str) -> list:
        """Detect code blocks with file paths in AI response."""
        files = []

        # Pattern 1: ```lang\n# File: path\ncontent``` or ```lang\n// File: path\ncontent```
        pattern1 = r'```(\w*)\s*\n(?:#|//)\s*[Ff]ile:\s*(.+?)\n(.*?)```'
        for match in re.finditer(pattern1, response, re.DOTALL):
            lang, filepath, content = match.group(1), match.group(2).strip(), match.group(3).strip()
            if filepath and content:
                files.append({"path": filepath, "content": content, "language": lang})

        # Pattern 2: ```lang\n<!-- File: path -->\ncontent```  (HTML)
        pattern2 = r'```(\w*)\s*\n<!--\s*[Ff]ile:\s*(.+?)\s*-->\n(.*?)```'
        for match in re.finditer(pattern2, response, re.DOTALL):
            lang, filepath, content = match.group(1), match.group(2).strip(), match.group(3).strip()
            if filepath and content and not any(f["path"] == filepath for f in files):
                files.append({"path": filepath, "content": content, "language": lang})

        # Pattern 3: ACTION: create\nFILE: path\nCONTENT:\ncontent
        actions = extract_file_actions(response)
        for action in actions:
            if action.get("action") in ("create", "write") and action.get("file"):
                fp = action["file"]
                if not any(f["path"] == fp for f in files):
                    files.append({"path": fp, "content": action.get("content", ""), "language": ""})

        # Pattern 4: filename markers like "**`src/app.py`**:" followed by code block
        pattern4 = r'(?:\*\*`|`)([\.\\w/\\\\-]+\.\w{1,10})(?:`\*\*|`)[:\s]*\n```\w*\n(.*?)```'
        for match in re.finditer(pattern4, response, re.DOTALL):
            filepath, content = match.group(1).strip(), match.group(2).strip()
            if filepath and content and not any(f["path"] == filepath for f in files):
                files.append({"path": filepath, "content": content, "language": ""})

        return files

    def _detect_commands_in_response(self, response: str) -> list:
        """Detect terminal commands in AI response."""
        commands = []
        pattern = r'```(?:commands|bash|shell|sh)\s*\n(.*?)```'
        for match in re.finditer(pattern, response, re.DOTALL):
            block = match.group(1).strip()
            for line in block.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    commands.append(line)
        return commands

    async def _auto_save_files(self, files: list):
        """Automatically save detected files to disk."""
        if not files:
            return

        ui.console.print(f"\n[bold bright_cyan]\ud83d\udcbe Auto-saving {len(files)} file(s)...[/]")
        
        saved = 0
        for f in files:
            filepath = f["path"]
            content = f["content"]
            
            if not content.strip():
                ui.show_warning(f"Skipped empty file: {filepath}")
                continue

            result = self.fm.write_file(filepath, content)
            if result["success"]:
                ui.console.print(
                    f"  [bold bright_green]\u2705 {filepath}[/] "
                    f"[dim]({result['lines']} lines, {result['size']} bytes)[/dim]"
                )
                saved += 1
                await self.db.log_file_operation(
                    self.session_id, "write", filepath, content_after=content[:500]
                )
            else:
                ui.console.print(f"  [bold bright_red]\u274c {filepath}: {result['error']}[/]")

        if saved:
            ui.console.print(
                f"\n[bold bright_green]\u2705 {saved}/{len(files)} file(s) saved to workspace![/]\n"
            )
        
        self._pending_files = files

    async def _auto_execute_commands(self, commands: list):
        """Automatically execute terminal commands found in AI response."""
        if not commands:
            return

        ui.console.print(f"\n[bold bright_cyan]\ud83d\ude80 Auto-running {len(commands)} command(s)...[/]")
        
        for cmd in commands:
            ui.console.print(f"\n[bright_yellow]$ {cmd}[/]")
            
            try:
                result = await self.executor.execute_command(cmd, timeout=60)
                
                if result.success:
                    ui.console.print(f"[bold bright_green]\u2705 OK[/] [dim]({result.execution_time:.1f}s)[/dim]")
                    if result.stdout.strip():
                        output = result.stdout.strip()
                        if len(output) > 500:
                            output = output[:500] + "\n... (truncated)"
                        ui.console.print(f"[dim]{output}[/dim]")
                else:
                    ui.console.print(f"[bold bright_red]\u274c FAILED[/] [dim](exit: {result.exit_code})[/dim]")
                    if result.stderr.strip():
                        stderr = result.stderr.strip()
                        if len(stderr) > 300:
                            stderr = stderr[:300] + "\n... (truncated)"
                        ui.console.print(f"[bold bright_red]{stderr}[/]")
            except Exception as e:
                ui.console.print(f"[bold bright_red]\u274c Error: {e}[/]")

        ui.console.print()

    async def _auto_execute_commands_with_fix(self, commands: list) -> str:
        """Execute commands and return error output if any failed."""
        if not commands:
            return ""

        ui.console.print(f"\n[bold bright_cyan]\ud83d\ude80 Auto-running {len(commands)} command(s)...[/]")
        
        all_errors = ""
        for cmd in commands:
            ui.console.print(f"\n[bright_yellow]$ {cmd}[/]")
            
            try:
                result = await self.executor.execute_command(cmd, timeout=60)
                
                if result.success:
                    ui.console.print(f"[bold bright_green]\u2705 OK[/] [dim]({result.execution_time:.1f}s)[/dim]")
                    if result.stdout.strip():
                        output = result.stdout.strip()
                        if len(output) > 500:
                            output = output[:500] + "\n..."
                        ui.console.print(f"[dim]{output}[/dim]")
                else:
                    ui.console.print(f"[bold bright_red]\u274c FAILED[/] [dim](exit: {result.exit_code})[/dim]")
                    error_text = result.stderr.strip() or result.stdout.strip()
                    if error_text:
                        if len(error_text) > 500:
                            error_text = error_text[:500] + "\n..."
                        ui.console.print(f"[bold bright_red]{error_text}[/]")
                        all_errors += f"\nCommand: {cmd}\nError:\n{error_text}\n"
            except Exception as e:
                ui.console.print(f"[bold bright_red]\u274c Error: {e}[/]")
                all_errors += f"\nCommand: {cmd}\nException: {e}\n"

        ui.console.print()
        return all_errors

    async def _auto_fix_errors(self, error_output: str, original_response: str, attempt: int = 1):
        """v3.2: AI auto-fixes errors after running commands."""
        MAX_FIX_ATTEMPTS = 3
        if attempt > MAX_FIX_ATTEMPTS:
            ui.console.print(
                f"\n[bold bright_red]\u274c Tried {MAX_FIX_ATTEMPTS} times to fix. Please check manually.[/]"
                f"\n[dim]Use /ask to tell AI what's wrong[/dim]\n"
            )
            return

        ui.console.print(
            f"\n[bold bright_yellow]\u26a0\ufe0f  Error detected! AI auto-fixing (attempt {attempt}/{MAX_FIX_ATTEMPTS})...[/]\n"
        )

        fix_prompt = (
            f"## ERROR FIX REQUIRED\n\n"
            f"The code has errors. FIX THEM NOW.\n\n"
            f"### ERROR OUTPUT:\n```\n{error_output[:2000]}\n```\n\n"
            f"### INSTRUCTIONS:\n"
            f"1. Output the FIXED files with COMPLETE code (not just the changed parts)\n"
            f"2. Use # File: path/to/file.ext header in each code block\n"
            f"3. Write the ENTIRE file content, not patches\n"
            f"4. After fixes, include ```commands``` block to re-run\n"
        )

        # Run AI to fix
        agent_config = self.config.agents.get(self.config.active_agent)
        icon = agent_config.icon if agent_config else "~"
        color = agent_config.color if agent_config else "bright_cyan"
        name = agent_config.name if agent_config else "NexaCode"

        ui.console.print(f"[dim]Mode: Bug Fixing (auto)[/dim]")

        # Build context with existing code
        code_context = self._read_project_code_context()
        memory_context = ""
        if self._active_project_name:
            mem = await self.db.get_project_memory(self._active_project_name)
            if mem:
                memory_context = self._format_memory_context(mem)

        task_prompt = TASK_SYSTEM_PROMPTS.get("debugging", TASK_SYSTEM_PROMPTS["default"])
        enhanced_prompt = self._build_enhanced_system_prompt(
            task_prompt, memory_context=memory_context, code_context=code_context
        )

        ui.show_ai_response_start(name, icon, color)

        import time as time_mod
        start_time = time_mod.time()
        full_response = ""

        async for chunk in self.engine.chat(
            prompt=fix_prompt,
            system_prompt=enhanced_prompt,
            stream=True,
        ):
            ui.print_streaming_token(chunk)
            full_response += chunk

        elapsed = time_mod.time() - start_time
        ui.show_ai_response_end(name, len(full_response) // 4, elapsed, color)

        # Save to database
        await self.db.save_message(self.session_id, "user", fix_prompt)
        await self.db.save_message(
            self.session_id, "assistant", full_response,
            agent_name=name, model=self.config.active_model,
        )

        # Auto-save fixed files
        files_found = self._detect_files_in_response(full_response)
        if files_found:
            await self._auto_save_files(files_found)

        # Auto-run commands again
        commands_found = self._detect_commands_in_response(full_response)
        if commands_found:
            new_errors = await self._auto_execute_commands_with_fix(commands_found)
            if new_errors:
                # Recursively try to fix again
                await self._auto_fix_errors(new_errors, full_response, attempt + 1)
            else:
                ui.console.print("[bold bright_green]\u2705 Fixed! Everything running now.[/]\n")
        else:
            ui.console.print("[dim]No commands to re-run. Check if fix is correct.[/dim]\n")

        await self._auto_save_project_memory()

    async def _save_pending_files(self, args: str):
        """Save detected files from AI response. v3.1.1: async + continue after save."""
        if not self._pending_files:
            ui.show_info("No pending files to save. Chat with AI and it will suggest files.")
            return

        indices = []
        if args.strip().lower() in ("", "all"):
            indices = list(range(len(self._pending_files)))
        else:
            try:
                for part in args.split():
                    idx = int(part) - 1
                    if 0 <= idx < len(self._pending_files):
                        indices.append(idx)
            except ValueError:
                ui.show_error("Usage: /save [all | 1 2 3 ...]")
                return

        saved = 0
        for idx in indices:
            f = self._pending_files[idx]
            result = self.fm.write_file(f["path"], f["content"])
            if result["success"]:
                ui.show_success(f"Saved: {f['path']} ({result['lines']} lines)")
                saved += 1
                await self.db.log_file_operation(
                    self.session_id, "write", f["path"], content_after=f["content"][:500]
                )
            else:
                ui.show_error(f"Failed to save {f['path']}: {result['error']}")

        if saved:
            ui.show_success(f"\n{saved}/{len(indices)} file(s) saved to workspace!")
        
        # v3.1.1: Auto-save project memory after manual save
        await self._auto_save_project_memory()
        
        # v3.1.1: Keep pending files for reference but tell user they can continue
        ui.console.print(
            "\n[bold bright_green]Files saved! You can continue working:[/bold bright_green]\n"
            "[dim]  - Type naturally to add/change features\n"
            "  - /ask <message> to ask AI for changes\n"
            "  - /project save to manually save memory\n"
            "  - /project open <name> to resume this project later\n"
            "  AI will read existing code before making changes.[/dim]\n"
        )

    async def _retry_last(self):
        """Retry the last failed AI request."""
        conv = self.engine.get_conversation()
        if conv._retry_buffer:
            ui.show_info("Retrying last message...")
            # Remove failed response and last user msg
            conv.pop_last_failed()
            if conv.messages and conv.messages[-1].role == "user":
                msg = conv.messages.pop()
                await self._chat_with_ai(msg.content)
            else:
                await self._chat_with_ai(conv._retry_buffer.content)
        else:
            ui.show_warning("Nothing to retry. Send a message first.")

    # =================================================================
    # PIPELINE EXECUTION
    # =================================================================
    async def _run_pipeline(self, task: str):
        if not task:
            ui.show_warning("Usage: /pipeline <task description>")
            return
        if not self.config.active_model:
            ui.show_error("No model configured! Use /model add first.")
            return

        pipeline = self.config.agent_pipeline
        ui.show_pipeline_start(pipeline)

        # Get project context
        tree_result = self.fm.list_dir(recursive=True, max_depth=2)
        context = f"Workspace: {self.config.workspace}\n"
        if tree_result["success"]:
            context += "Project structure available.\n"

        def on_agent_start(name, agent_cfg):
            ui.console.print(
                f"\n[bold {agent_cfg.color}]{agent_cfg.icon} {agent_cfg.name}[/] "
                f"[dim]is working...[/dim]"
            )
            ui.console.print(f"[{agent_cfg.color}]{'~' * 50}[/]")

        def on_token(agent_name, chunk):
            ui.print_streaming_token(chunk)

        def on_agent_done(name, result):
            ui.console.print(f"\n[dim]{'~' * 50}[/]")
            status = "+" if result.status == AgentStatus.DONE else "X"
            ui.console.print(
                f"[dim]{status} {name} finished in {result.execution_time:.1f}s "
                f"({result.tokens_used} tokens)[/dim]\n"
            )

        result = await self.orchestrator.run_pipeline(
            task=task,
            context=context,
            pipeline=pipeline,
            on_agent_start=on_agent_start,
            on_token=on_token,
            on_agent_done=on_agent_done,
        )

        # Show summary
        summary = {
            "results": [
                {
                    "agent_name": r.agent_name,
                    "status": r.status.value,
                    "execution_time": r.execution_time,
                    "tokens_used": r.tokens_used,
                    "icon": self.config.agents.get(r.role, AgentConfig(name="", role="", system_prompt="")).icon,
                }
                for r in result.results
            ]
        }
        ui.show_pipeline_result(summary)

        # Check pipeline output for files -> auto-save
        if result.final_output:
            files_found = self._detect_files_in_response(result.final_output)
            if files_found:
                await self._auto_save_files(files_found)
            commands_found = self._detect_commands_in_response(result.final_output)
            if commands_found:
                await self._auto_execute_commands(commands_found)

    # =================================================================
    # MODEL MANAGEMENT - Enhanced
    # =================================================================
    async def _handle_model_command(self, args: str):
        parts = args.split(maxsplit=1)
        subcmd = parts[0].lower() if parts else "list"

        if subcmd == "list":
            ui.show_models_table(self.config.models, self.config.active_model)
        elif subcmd == "add":
            await self._add_model_interactive()
        elif subcmd == "use":
            name = parts[1] if len(parts) > 1 else ""
            self._use_model(name)
        elif subcmd == "remove":
            name = parts[1] if len(parts) > 1 else ""
            self._remove_model(name)
        elif subcmd == "info":
            self._show_model_info()
        else:
            # Treat as model name to use
            self._use_model(subcmd)

    async def _add_model_interactive(self):
        """Interactive model addition wizard.
        
        FIXED: Use run_in_executor to avoid 'asyncio.run() cannot be called
        from a running event loop' error when prompt_toolkit.prompt() is
        called inside an async function.
        """
        ui.console.print("\n[bold bright_cyan]~~ Add New AI Model[/]\n")
        ui.show_providers_table()

        try:
            loop = asyncio.get_event_loop()

            def _sync_prompt(message: str, default: str = "") -> str:
                """Synchronous prompt that works in executor."""
                try:
                    from prompt_toolkit import prompt as pt_prompt
                    result = pt_prompt(message)
                    return result.strip() if result else default
                except (KeyboardInterrupt, EOFError):
                    return default

            provider = await loop.run_in_executor(
                None, _sync_prompt,
                "Provider (openai/anthropic/gemini/openrouter/groq/deepseek/ollama/custom): ", ""
            )
            if not provider:
                ui.show_warning("Cancelled.")
                return
            provider = provider.lower()

            # Show available models for the provider
            provider_info = DEFAULT_PROVIDERS.get(provider, {})
            available_models = provider_info.get("models", [])
            if available_models:
                ui.console.print(f"\n[bold]Available {provider.title()} models:[/]")
                for i, m in enumerate(available_models, 1):
                    ui.console.print(f"  [bright_cyan]{i}[/]. {m}")
                choice = await loop.run_in_executor(
                    None, _sync_prompt,
                    f"\nChoose model number or type custom ID [1]: ", ""
                )
                if choice.isdigit():
                    idx = int(choice) - 1
                    model_id = available_models[min(idx, len(available_models) - 1)]
                elif choice:
                    model_id = choice
                else:
                    model_id = available_models[0]
            else:
                model_id = await loop.run_in_executor(
                    None, _sync_prompt,
                    "Model ID (e.g., gpt-4o, claude-sonnet-4-20250514): ", ""
                )
                if not model_id:
                    ui.show_warning("Cancelled.")
                    return

            default_name = model_id.split('/')[-1]
            # Avoid double prefix: if model_id already starts with provider, don't prepend
            if not default_name.startswith(provider):
                default_name = f"{provider}-{default_name}"
            name = await loop.run_in_executor(
                None, _sync_prompt,
                f"Display name [{default_name}]: ", default_name
            )

            # Get base URL
            default_url = provider_info.get("base_url", "")
            base_url = await loop.run_in_executor(
                None, _sync_prompt,
                f"Base URL [{default_url}]: ", default_url
            )

            # Get API key
            api_key = ""
            env_key = os.environ.get(f"{provider.upper()}_API_KEY", "")
            if env_key:
                use_env = await loop.run_in_executor(
                    None, _sync_prompt,
                    f"Use existing API key from env? (Y/n): ", "y"
                )
                if use_env.lower() != "n":
                    api_key = env_key
            if not api_key and provider not in ("ollama", "lmstudio"):
                api_key = await loop.run_in_executor(
                    None, _sync_prompt,
                    "API Key: ", ""
                )

            # Advanced settings
            max_tokens_str = await loop.run_in_executor(
                None, _sync_prompt,
                "Max tokens [4096]: ", "4096"
            )
            max_tokens = int(max_tokens_str) if max_tokens_str.isdigit() else 4096

            temp_str = await loop.run_in_executor(
                None, _sync_prompt,
                "Temperature [0.7]: ", "0.7"
            )
            try:
                temperature = float(temp_str)
            except ValueError:
                temperature = 0.7

            # Custom headers
            custom_headers = {}
            add_headers = await loop.run_in_executor(
                None, _sync_prompt,
                "Add custom headers? (y/N): ", "n"
            )
            if add_headers.lower() == "y":
                while True:
                    header = await loop.run_in_executor(
                        None, _sync_prompt,
                        "Header (key:value, empty to stop): ", ""
                    )
                    if not header:
                        break
                    if ":" in header:
                        k, v = header.split(":", 1)
                        custom_headers[k.strip()] = v.strip()

            model_config = ModelConfig(
                name=name,
                provider=provider,
                model_id=model_id,
                api_key=api_key,
                base_url=base_url,
                max_tokens=max_tokens,
                temperature=temperature,
                headers=custom_headers,
            )

            self.config.add_model(name, model_config)
            if api_key and provider in ("openai", "anthropic", "gemini", "openrouter", "groq", "deepseek"):
                self.config.save_api_key(provider, api_key)

            ui.show_success(f"Model '{name}' added successfully!")
            if not self.config.active_model or self.config.active_model == name:
                self.config.active_model = name
                self.config.save_config()
                ui.show_info(f"Active model set to '{name}'")

            # Reinitialize engine to pick up new model
            self.engine = AIEngine(self.config)
            self.orchestrator = AgentOrchestrator(self.config, self.engine)

        except (KeyboardInterrupt, EOFError):
            ui.show_warning("Cancelled.")
        except Exception as e:
            ui.show_error(f"Error adding model: {type(e).__name__}: {str(e)}")

    def _use_model(self, name: str):
        if not name:
            ui.show_warning("Usage: /model use <name>")
            return
        if name not in self.config.models:
            # Try partial match
            matches = [k for k in self.config.models if name.lower() in k.lower()]
            if len(matches) == 1:
                name = matches[0]
            elif matches:
                ui.show_warning(f"Multiple matches: {', '.join(matches)}")
                return
            else:
                ui.show_error(f"Model '{name}' not found. Use /model list to see available models.")
                return
        self.config.active_model = name
        self.config.save_config()
        model = self.config.models[name]
        ui.show_success(f"Switched to: {name} ({model.provider}/{model.model_id})")

    def _remove_model(self, name: str):
        if not name:
            ui.show_warning("Usage: /model remove <name>")
            return
        if name not in self.config.models:
            ui.show_error(f"Model '{name}' not found.")
            return
        self.config.remove_model(name)
        ui.show_success(f"Model '{name}' removed.")

    def _show_model_info(self):
        """Show detailed info about the active model."""
        model = self.config.get_active_model()
        if not model:
            ui.show_warning("No active model. Use /model add first.")
            return

        table = ui.Table(
            title=f"[bold bright_white]~~ Model: {model.name}[/]",
            box=ui.ROUNDED, border_style="bright_cyan", show_lines=True,
        )
        table.add_column("Property", style="bright_cyan", width=20)
        table.add_column("Value", style="bright_white")

        table.add_row("Name", model.name)
        table.add_row("Provider", model.provider)
        table.add_row("Model ID", model.model_id)
        table.add_row("Base URL", model.base_url or "default")
        table.add_row("API Key", "***" + model.api_key[-4:] if model.api_key else "Not set")
        table.add_row("Max Tokens", str(model.max_tokens))
        table.add_row("Temperature", str(model.temperature))
        table.add_row("Top P", str(model.top_p))
        table.add_row("Timeout", f"{model.timeout}s")
        table.add_row("Enabled", str(model.enabled))

        ui.console.print(table)

    def _set_api_key(self, args: str):
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            ui.show_warning(
                "Usage: /apikey <provider> <key>\n"
                "Example: /apikey openai sk-xxxxx\n"
                "         /apikey anthropic sk-ant-xxxxx\n"
                "         /apikey gemini AIza-xxxxx\n"
                "         /apikey groq gsk_xxxxx\n"
                "         /apikey deepseek sk-xxxxx\n"
                "         /apikey openrouter sk-or-xxxxx"
            )
            return

        provider, key = parts[0].lower(), parts[1]
        self.config.save_api_key(provider, key)

        # Auto-create a default model for this provider
        provider_info = DEFAULT_PROVIDERS.get(provider, {})
        if provider_info and provider_info.get("models"):
            default_model = provider_info["models"][0]
            # Fix: avoid gemini-gemini-2.5-flash double-prefix
            short_id = default_model.split('/')[-1]
            if short_id.startswith(provider):
                model_name = short_id
            else:
                model_name = f"{provider}-{short_id}"
            model_config = ModelConfig(
                name=model_name,
                provider=provider,
                model_id=default_model,
                api_key=key,
                base_url=provider_info.get("base_url", ""),
            )
            self.config.add_model(model_name, model_config)
            ui.show_success(
                f"API key saved for {provider}!\n"
                f"Auto-created model: {model_name} ({default_model})\n"
                f"Active model: {self.config.active_model}"
            )
        else:
            ui.show_success(f"API key saved for {provider}. Use /model add to configure a model.")

    # =================================================================
    # AGENT MANAGEMENT
    # =================================================================
    def _switch_agent(self, name: str):
        if not name:
            ui.show_warning("Usage: /agent <name>\nAvailable: architect, coder, reviewer, tester, devops")
            return
        name = name.lower()
        if name not in self.config.agents:
            ui.show_error(f"Agent '{name}' not found. Available: {', '.join(self.config.agents.keys())}")
            return
        self.config.active_agent = name
        agent = self.config.agents[name]
        ui.show_success(f"Switched to agent: {agent.icon} {agent.name} ({agent.role})")

    def _show_agents(self):
        agents_info = {}
        for name, cfg in self.config.agents.items():
            agent = self.orchestrator.get_agent(name)
            is_active = " [ACTIVE]" if name == self.config.active_agent else ""
            agents_info[name] = {
                "role": cfg.role,
                "icon": cfg.icon,
                "status": agent.status.value if agent else "idle",
                "model": cfg.model or self.config.active_model or "none",
                "tokens": 0,
                "active": name == self.config.active_agent,
            }
        ui.show_agent_status(agents_info)

    # =================================================================
    # FILE OPERATIONS
    # =================================================================
    def _read_file(self, path: str):
        if not path:
            ui.show_warning("Usage: /read <filepath>")
            return
        result = self.fm.read_file(path)
        if result["success"]:
            ext = Path(path).suffix.lstrip(".")
            lang_map = {
                "py": "python", "js": "javascript", "ts": "typescript",
                "jsx": "jsx", "tsx": "tsx", "html": "html", "css": "css",
                "json": "json", "yaml": "yaml", "yml": "yaml", "toml": "toml",
                "sql": "sql", "sh": "bash", "md": "markdown", "rs": "rust",
                "go": "go", "java": "java", "rb": "ruby", "php": "php",
                "cpp": "cpp", "c": "c", "h": "c",
            }
            language = lang_map.get(ext, "text")
            ui.console.print(f"[bold bright_green]\u2705 Reading: {path}[/]")
            ui.show_code(
                result["content"],
                language=language,
                title=f"{path} ({result['total_lines']} lines, {ui._format_size(result['size'])})",
            )
        else:
            ui.show_error(f"Cannot read file: {result['error']}")

    async def _write_file_interactive(self, path: str):
        if not path:
            ui.show_warning("Usage: /write <filepath>\nThen type content, Ctrl+D to finish.")
            return
        ui.console.print(f"[bright_cyan]~~ Enter content for {path} (Ctrl+D to finish):[/]")
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass

        content = "\n".join(lines)
        if content:
            result = self.fm.write_file(path, content)
            if result["success"]:
                ui.show_success(f"Written {result['lines']} lines to {path}")
                await self.db.log_file_operation(self.session_id, "write", path, content_after=content)
            else:
                ui.show_error(result["error"])
        else:
            ui.show_warning("Empty content. File not written.")

    async def _edit_file_interactive(self, path: str):
        if not path:
            ui.show_warning("Usage: /edit <filepath>")
            return

        result = self.fm.read_file(path)
        if not result["success"]:
            ui.show_error(result["error"])
            return

        ui.show_code(result["content"], language="text", title=path)

        try:
            loop = asyncio.get_event_loop()

            def _sync_prompt(message: str) -> str:
                from prompt_toolkit import prompt as pt_prompt
                return pt_prompt(message)

            ui.console.print("[bright_cyan]Enter text to find:[/]")
            old_text = await loop.run_in_executor(None, _sync_prompt, "Find: ")
            if not old_text:
                return

            ui.console.print("[bright_cyan]Enter replacement text:[/]")
            new_text = await loop.run_in_executor(None, _sync_prompt, "Replace: ")

            edit_result = self.fm.edit_file(path, old_text, new_text)
            if edit_result["success"]:
                ui.show_success(f"File edited: {path}")
                await self.db.log_file_operation(self.session_id, "edit", path)
            else:
                ui.show_error(edit_result["error"])
        except (KeyboardInterrupt, EOFError):
            ui.show_warning("Edit cancelled.")

    def _show_tree(self, path: str = ""):
        result = self.fm.list_dir(path or None, recursive=True, max_depth=4)
        if result["success"]:
            root_name = Path(result["path"]).name or result["path"]
            ui.show_file_tree(result["tree"], root_name)
        else:
            ui.show_error(result["error"])

    def _glob_search(self, pattern: str):
        if not pattern:
            ui.show_warning("Usage: /glob <pattern>\nExample: /glob *.py  or  /glob **/*.js")
            return
        results = self.fm.glob_search(pattern)
        if results:
            table = ui.Table(
                title=f"[bold]~~ Glob: {pattern} ({len(results)} results)[/]",
                box=ui.ROUNDED, border_style="bright_cyan",
            )
            table.add_column("File", style="bright_white")
            table.add_column("Size", justify="right", style="dim")
            table.add_column("Modified", style="dim")
            for r in results[:50]:
                table.add_row(
                    r["relative"],
                    ui._format_size(r["size"]),
                    r["modified"][:19],
                )
            ui.console.print(table)
        else:
            ui.show_info(f"No files matching '{pattern}'")

    def _grep_search(self, pattern: str):
        if not pattern:
            ui.show_warning("Usage: /grep <pattern>\nExample: /grep 'def main'  or  /grep 'TODO'")
            return
        results = self.fm.grep_search(pattern)
        if results:
            ui.console.print(f"[bold bright_cyan]~~ Grep: '{pattern}' ({len(results)} matches)[/]\n")
            for r in results[:30]:
                ui.console.print(f"[bright_green]{r['file']}[/]:[bright_yellow]{r['line']}[/]")
                ui.console.print(f"[dim]{r['context']}[/dim]\n")
        else:
            ui.show_info(f"No matches for '{pattern}'")

    def _show_diff(self, path: str):
        if not path:
            ui.show_warning("Usage: /diff <filepath>")
            return
        self._read_file(path)

    def _mkdir(self, path: str):
        if not path:
            ui.show_warning("Usage: /mkdir <directory>")
            return
        result = self.fm.create_dir(path)
        if result["success"]:
            ui.show_success(f"Created directory: {path}")
        else:
            ui.show_error(result["error"])

    def _delete_path(self, path: str):
        if not path:
            ui.show_warning("Usage: /delete <path>")
            return
        try:
            # Use simple input() instead of prompt_toolkit to avoid async issues
            confirm = input(f"Delete '{path}'? (y/N): ").strip().lower()
            if confirm == "y":
                result = self.fm.delete_path(path)
                if result["success"]:
                    ui.show_success(f"Deleted: {path}")
                else:
                    ui.show_error(result["error"])
        except (KeyboardInterrupt, EOFError):
            ui.show_warning("Cancelled.")

    def _move_path(self, args: str):
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            ui.show_warning("Usage: /move <source> <destination>")
            return
        result = self.fm.move_path(parts[0], parts[1])
        if result["success"]:
            ui.show_success(f"Moved: {parts[0]} -> {parts[1]}")
        else:
            ui.show_error(result["error"])

    def _copy_path(self, args: str):
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            ui.show_warning("Usage: /copy <source> <destination>")
            return
        result = self.fm.copy_path(parts[0], parts[1])
        if result["success"]:
            ui.show_success(f"Copied: {parts[0]} -> {parts[1]}")
        else:
            ui.show_error(result["error"])

    # =================================================================
    # CODE EXECUTION
    # =================================================================
    async def _run_command(self, command: str):
        if not command:
            ui.show_warning("Usage: /run <command>\nExample: /run python3 app.py")
            return

        with ui.create_spinner(f"Running: {command[:50]}..."):
            result = await self.executor.execute_command(command)

        ui.show_execution_result({
            "command": result.command,
            "exit_code": result.exit_code,
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_time": result.execution_time,
        })

    async def _exec_code_interactive(self, language: str):
        language = language or "python"
        ui.console.print(f"[bright_cyan]~~ Enter {language} code (Ctrl+D to execute):[/]")

        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass

        code = "\n".join(lines)
        if not code.strip():
            ui.show_warning("No code entered.")
            return

        ui.show_code(code, language=language, title=f"Executing {language}")

        with ui.create_spinner(f"Executing {language} code..."):
            result = await self.executor.execute_code(code, language)

        ui.show_execution_result({
            "command": f"Execute {language} code",
            "exit_code": result.exit_code,
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_time": result.execution_time,
        })

    async def _run_tests(self, args: str):
        parts = args.split() if args else []
        test_path = parts[0] if parts else None
        framework = parts[1] if len(parts) > 1 else "auto"

        with ui.create_spinner("Running tests..."):
            result = await self.executor.run_tests(test_path, framework)

        ui.show_execution_result({
            "command": result.command,
            "exit_code": result.exit_code,
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_time": result.execution_time,
        })

    async def _run_lint(self, args: str):
        with ui.create_spinner("Running linter..."):
            result = await self.executor.lint_code(args or None)

        ui.show_execution_result({
            "command": result.command,
            "exit_code": result.exit_code,
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_time": result.execution_time,
        })

    async def _install_deps(self, args: str):
        with ui.create_spinner("Installing dependencies..."):
            result = await self.executor.install_dependencies(args or "auto")

        ui.show_execution_result({
            "command": result.command,
            "exit_code": result.exit_code,
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_time": result.execution_time,
        })

    # =================================================================
    # SESSION MANAGEMENT
    # =================================================================
    async def _handle_session_command(self, args: str):
        parts = args.split(maxsplit=1)
        subcmd = parts[0].lower() if parts else "list"

        if subcmd == "list":
            sessions = await self.db.list_sessions()
            ui.show_sessions_table(sessions)
        elif subcmd == "new":
            name = parts[1] if len(parts) > 1 else f"session-{str(uuid.uuid4())[:6]}"
            self.session_id = str(uuid.uuid4())[:8]
            await self.db.create_session(
                self.session_id, name,
                workspace=self.config.workspace,
                model=self.config.active_model,
                agent=self.config.active_agent,
            )
            self.engine.get_conversation().clear()
            ui.show_success(f"New session: {name} (ID: {self.session_id})")
        elif subcmd == "load":
            session_id = parts[1] if len(parts) > 1 else ""
            if not session_id:
                ui.show_warning("Usage: /session load <id>")
                return
            session = await self.db.get_session(session_id)
            if session:
                self.session_id = session_id
                messages = await self.db.get_messages(session_id)
                conv = self.engine.get_conversation()
                conv.clear()
                for msg in messages:
                    conv.add_message(msg["role"], msg["content"])
                ui.show_success(f"Loaded session: {session['name']} ({len(messages)} messages)")
            else:
                ui.show_error(f"Session '{session_id}' not found.")
        elif subcmd == "delete":
            session_id = parts[1] if len(parts) > 1 else ""
            if session_id:
                await self.db.delete_session(session_id)
                ui.show_success(f"Session '{session_id}' deleted.")

    async def _show_history(self):
        messages = await self.db.get_messages(self.session_id)
        ui.show_history(messages)

    async def _search_history(self, query: str):
        if not query:
            ui.show_warning("Usage: /search <query>")
            return
        results = await self.db.search_messages(query)
        if results:
            ui.show_history(results)
        else:
            ui.show_info(f"No messages matching '{query}'")

    async def _show_usage(self):
        stats = await self.db.get_usage_summary()
        engine_stats = self.engine.get_usage_stats()
        ui.show_usage_stats(stats)
        ui.console.print(
            f"[dim]Current session: {engine_stats['total_requests']} requests, "
            f"{engine_stats['total_tokens']} tokens, {engine_stats['estimated_cost']} "
            f"({engine_stats['errors']} errors)[/dim]"
        )

    async def _export_session(self):
        messages = await self.db.get_messages(self.session_id)
        export_path = Path(self.config.workspace) / f"nexacode_session_{self.session_id}.md"
        content = f"# NexaCode Session: {self.session_id}\n\n"
        for msg in messages:
            role = "User" if msg["role"] == "user" else f"~~ {msg.get('agent_name', 'AI')}"
            content += f"## {role}\n{msg['content']}\n\n---\n\n"
        self.fm.write_file(str(export_path), content)
        ui.show_success(f"Session exported to: {export_path}")

    # =================================================================
    # SETTINGS & CONFIG
    # =================================================================
    def _change_workspace(self, path: str):
        if not path:
            ui.show_info(f"Current workspace: {self.config.workspace}")
            return
        path = os.path.expanduser(path)
        if os.path.isdir(path):
            self.config.workspace = os.path.abspath(path)
            self.fm = FileManager(self.config.workspace)
            self.executor = CodeExecutor(self.config.workspace)
            self.config.save_config()
            ui.show_success(f"Workspace changed to: {self.config.workspace}")
        else:
            ui.show_error(f"Directory not found: {path}")

    def _handle_config(self, args: str):
        if not args:
            self._show_config()
            return

        parts = args.split(maxsplit=2)
        if parts[0] == "set" and len(parts) >= 3:
            key, value = parts[1], parts[2]
            if hasattr(self.config, key):
                current = getattr(self.config, key)
                if isinstance(current, bool):
                    value = value.lower() in ("true", "1", "yes", "on")
                elif isinstance(current, int):
                    value = int(value)
                elif isinstance(current, float):
                    value = float(value)

                setattr(self.config, key, value)
                self.config.save_config()
                ui.show_success(f"Config updated: {key} = {value}")
            else:
                ui.show_error(f"Unknown config key: {key}")
        else:
            ui.show_warning("Usage: /config set <key> <value>")

    def _show_config(self):
        table = ui.Table(
            title="[bold bright_white]~~ Configuration[/]",
            box=ui.ROUNDED, border_style="bright_cyan", show_lines=True,
        )
        table.add_column("Setting", style="bright_cyan", width=20)
        table.add_column("Value", style="bright_white")

        model = self.config.get_active_model()
        model_display = f"{self.config.active_model}"
        if model:
            model_display += f" ({model.provider}/{model.model_id})"

        settings = {
            "workspace": self.config.workspace,
            "active_model": model_display if self.config.active_model else "[dim]None[/dim]",
            "active_agent": self.config.active_agent,
            "multi_agent_mode": str(self.config.multi_agent_mode),
            "auto_review": str(self.config.auto_review),
            "auto_test": str(self.config.auto_test),
            "stream_output": str(self.config.stream_output),
            "show_token_count": str(self.config.show_token_count),
            "show_cost": str(self.config.show_cost),
            "theme": self.config.theme,
            "max_history": str(self.config.max_history),
            "pipeline": " -> ".join(self.config.agent_pipeline),
        }

        for k, v in settings.items():
            table.add_row(k, v)
        ui.console.print(table)

    def _show_version(self):
        ui.console.print(
            ui.Panel(
                f"  [bold bright_cyan]{APP_NAME}[/] v{APP_VERSION} '[bright_magenta]{APP_CODENAME}[/]'\n\n"
                f"  [dim]AI-Powered Terminal Coding Assistant[/dim]\n"
                f"  [dim]Multi-Agent | Multi-Model | Full Stack[/dim]\n\n"
                f"  [bright_green]Features:[/]\n"
                f"  + 10+ AI Provider Support (OpenAI, Anthropic, Gemini, etc.)\n"
                f"  + 5 Specialized AI Agents Pipeline\n"
                f"  + Auto-Save Code Blocks from AI Responses\n"
                f"  + Full File Management (Read, Write, Edit, Search)\n"
                f"  + Code Execution in 12+ Languages\n"
                f"  + Session Persistence with SQLite\n"
                f"  + Custom API Endpoint Support\n"
                f"  + Real-time Streaming Responses\n"
                f"  + Error Recovery with Retry Support\n"
                f"  + Auto-Complete & Command History",
                title="[bold bright_white]~~ About[/]",
                border_style="bright_cyan",
                box=ui.ROUNDED,
                padding=(1, 2),
            )
        )

    def _clear_conversation(self):
        self.engine.get_conversation().clear()
        self.orchestrator.reset_all()
        self._pending_files = []
        ui.show_success("Conversation cleared.")

    def _show_project_stats(self):
        stats = self.fm.get_project_stats()
        ui.show_project_stats(stats)

    # =================================================================
    # PROJECT MEMORY SYSTEM (v3.1)
    # =================================================================
    async def _handle_project_command(self, args: str):
        """Handle /project commands for project memory management."""
        parts = args.split(maxsplit=1) if args else []
        subcmd = parts[0].lower() if parts else "list"
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd == "list":
            await self._list_projects()
        elif subcmd == "open" or subcmd == "load" or subcmd == "resume":
            await self._open_project(subargs)
        elif subcmd == "save":
            await self._save_project_memory_manual(subargs)
        elif subcmd == "new":
            await self._new_project(subargs)
        elif subcmd == "info":
            await self._show_project_info(subargs)
        elif subcmd == "delete":
            await self._delete_project(subargs)
        elif subcmd == "close":
            self._close_project()
        else:
            # Treat as project name to open
            await self._open_project(args.strip())

    async def _list_projects(self):
        """List all saved projects with memory."""
        projects = await self.db.list_project_memories()
        if not projects:
            ui.show_info("No saved projects yet. Projects are auto-saved as you work.")
            ui.console.print("[dim]Tip: Use '/project new my-app' to start a new project[/dim]\n")
            return

        table = ui.Table(
            title="[bold bright_white]Saved Projects[/]",
            box=ui.ROUNDED, border_style="bright_cyan", show_lines=True,
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Project", style="bold bright_cyan", width=20)
        table.add_column("Tech Stack", width=18)
        table.add_column("Last Task", width=30)
        table.add_column("Updated", width=16)

        from datetime import datetime
        for i, p in enumerate(projects, 1):
            updated = datetime.fromtimestamp(p.get("updated_at", 0)).strftime("%Y-%m-%d %H:%M")
            active = " [ACTIVE]" if p["project_name"] == self._active_project_name else ""
            last_task = (p.get("last_task", "") or "")[:28]
            if len(p.get("last_task", "") or "") > 28:
                last_task += "..."
            table.add_row(
                str(i),
                p["project_name"] + active,
                p.get("tech_stack", "") or "[dim]auto[/dim]",
                last_task or "[dim]none[/dim]",
                updated,
            )

        ui.console.print(table)
        ui.console.print(
            "\n[dim]Usage: /project open <name>  |  /project new <name>  |  /project info <name>[/dim]\n"
        )

    async def _open_project(self, project_name: str):
        """Open a project and load its memory into the conversation."""
        if not project_name:
            ui.show_warning("Usage: /project open <project-name>")
            return

        mem = await self.db.get_project_memory(project_name)
        if not mem:
            # Try fuzzy match
            all_projects = await self.db.list_project_memories()
            matches = [p for p in all_projects if project_name.lower() in p["project_name"].lower()]
            if len(matches) == 1:
                project_name = matches[0]["project_name"]
                mem = await self.db.get_project_memory(project_name)
            elif matches:
                ui.show_warning(f"Multiple matches: {', '.join(p['project_name'] for p in matches)}")
                return
            else:
                ui.show_error(f"Project '{project_name}' not found. Use /project list to see available projects.")
                return

        # Set active project
        self._active_project_name = project_name
        self._current_project_folder = project_name
        self._project_memory_cache = mem

        # Load conversation snapshot into engine
        conv = self.engine.get_conversation()
        conv.clear()
        for msg in mem.get("conversation_snapshot", []):
            if isinstance(msg, dict):
                conv.add_message(msg.get("role", "user"), msg.get("content", ""))

        # Read existing project files
        project_dir = Path(self.config.workspace) / project_name
        files_info = ""
        if project_dir.exists() and project_dir.is_dir():
            file_count = sum(1 for _ in project_dir.rglob("*") if _.is_file() and not self.fm._should_ignore(_))
            files_info = f"  Files on disk: {file_count}"

        ui.console.print(
            ui.Panel(
                f"  Project: [bold bright_cyan]{project_name}[/]\n"
                f"  Tech: {mem.get('tech_stack', 'auto')}\n"
                f"  Last task: {mem.get('last_task', 'none')[:60]}\n"
                f"  Memory: {len(mem.get('conversation_snapshot', []))} messages loaded\n"
                f"{files_info}",
                title="[bold bright_green]Project Opened[/]",
                border_style="bright_green",
                box=ui.ROUNDED,
                padding=(0, 2),
            )
        )
        ui.console.print(
            "[dim]Project memory loaded! AI remembers previous work.\n"
            "Just tell AI what to add/change and it will read existing code first.[/dim]\n"
        )

    # ─────────────────────────────────────────────────
    # RANDOM NAME GENERATOR
    # ─────────────────────────────────────────────────
    @staticmethod
    def _generate_random_project_name() -> str:
        """Generate a fun random project name like 'cosmic-tiger-42'."""
        adjectives = [
            "cosmic", "blazing", "neon", "cyber", "turbo", "hyper",
            "quantum", "stellar", "atomic", "rapid", "swift", "mighty",
            "shadow", "crystal", "thunder", "golden", "iron", "dark",
            "bright", "silent", "frozen", "pixel", "sonic", "lunar",
            "solar", "nova", "storm", "flash", "zen", "epic",
            "mega", "ultra", "alpha", "beta", "delta", "omega",
        ]
        nouns = [
            "tiger", "falcon", "wolf", "dragon", "phoenix", "panther",
            "cobra", "eagle", "shark", "lion", "hawk", "viper",
            "fox", "bear", "raven", "spider", "mantis", "scorpion",
            "knight", "ninja", "samurai", "pilot", "ranger", "wizard",
            "forge", "spark", "blade", "orbit", "pulse", "nexus",
            "code", "stack", "node", "core", "grid", "flux",
        ]
        adj = random.choice(adjectives)
        noun = random.choice(nouns)
        num = random.randint(10, 99)
        return f"{adj}-{noun}-{num}"

    async def _new_project(self, project_name: str):
        """Create a new project with memory tracking.
        
        If no name is given, a random fun name is auto-generated.
        """
        if not project_name:
            project_name = self._generate_random_project_name()
            ui.console.print(f"[dim]Auto-generated project name: [bold bright_cyan]{project_name}[/bold bright_cyan][/dim]")

        self._active_project_name = project_name
        self._current_project_folder = project_name
        self._project_memory_cache = {}

        # Create project directory
        project_dir = Path(self.config.workspace) / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        # Initialize memory in database
        await self.db.save_project_memory(
            project_name=project_name,
            workspace=str(project_dir),
            summary=f"New project: {project_name}",
            files_list=[],
            tech_stack="",
            last_task="",
            conversation_snapshot=[],
        )

        # Clear conversation for fresh start
        self.engine.get_conversation().clear()

        ui.show_success(f"New project '{project_name}' created!")
        ui.console.print(
            f"[dim]Folder: {project_dir}\n"
            f"Memory tracking enabled -- AI will remember this project.\n"
            f"Now use /ask to tell AI what to build![/dim]\n"
        )

    async def _save_project_memory_manual(self, note: str = ""):
        """Manually trigger a project memory save."""
        if not self._active_project_name:
            ui.show_warning("No active project. Use /project new <name> or /project open <name> first.")
            return

        await self._auto_save_project_memory(note)
        ui.show_success(f"Project memory saved for '{self._active_project_name}'!")

    async def _show_project_info(self, project_name: str = ""):
        """Show detailed info about a project's memory."""
        project_name = project_name or self._active_project_name
        if not project_name:
            ui.show_warning("Usage: /project info <project-name>")
            return

        mem = await self.db.get_project_memory(project_name)
        if not mem:
            ui.show_error(f"Project '{project_name}' not found.")
            return

        from datetime import datetime
        created = datetime.fromtimestamp(mem.get("created_at", 0)).strftime("%Y-%m-%d %H:%M:%S")
        updated = datetime.fromtimestamp(mem.get("updated_at", 0)).strftime("%Y-%m-%d %H:%M:%S")

        table = ui.Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bright_cyan", width=20)
        table.add_column("Value", style="bright_white")

        table.add_row("Project", mem["project_name"])
        table.add_row("Tech Stack", mem.get("tech_stack", "") or "auto")
        table.add_row("Summary", (mem.get("summary", "") or "none")[:80])
        table.add_row("Last Task", (mem.get("last_task", "") or "none")[:80])
        table.add_row("Files", str(len(mem.get("files_list", []))))
        table.add_row("Messages", str(len(mem.get("conversation_snapshot", []))))
        table.add_row("Created", created)
        table.add_row("Updated", updated)

        is_active = " (ACTIVE)" if project_name == self._active_project_name else ""
        ui.console.print(
            ui.Panel(
                table,
                title=f"[bold bright_white]Project: {project_name}{is_active}[/]",
                border_style="bright_cyan",
                box=ui.ROUNDED,
                padding=(1, 2),
            )
        )

    async def _delete_project(self, project_name: str):
        """Delete a project's memory (not files!)."""
        if not project_name:
            ui.show_warning("Usage: /project delete <project-name>")
            return

        await self.db.delete_project_memory(project_name)
        if self._active_project_name == project_name:
            self._active_project_name = ""
            self._current_project_folder = ""
            self._project_memory_cache = {}
        ui.show_success(f"Project memory for '{project_name}' deleted. (Files on disk are not affected.)")

    def _close_project(self):
        """Close the active project without deleting memory."""
        if self._active_project_name:
            ui.show_info(f"Closed project '{self._active_project_name}'. Memory is saved.")
        self._active_project_name = ""
        self._current_project_folder = ""
        self._project_memory_cache = {}
        self.engine.get_conversation().clear()

    async def _auto_save_project_memory(self, note: str = ""):
        """Auto-save current project memory to database."""
        if not self._active_project_name:
            return

        # Build conversation snapshot (last 30 messages max to save space)
        conv = self.engine.get_conversation()
        snapshot = []
        for msg in conv.messages[-30:]:
            snapshot.append({
                "role": msg.role,
                "content": msg.content[:2000],  # Truncate long messages
            })

        # Detect files in project folder
        project_dir = Path(self.config.workspace) / self._current_project_folder
        files_list = []
        if project_dir.exists():
            for fp in project_dir.rglob("*"):
                if fp.is_file() and not self.fm._should_ignore(fp):
                    try:
                        rel = str(fp.relative_to(self.config.workspace))
                        files_list.append(rel)
                    except Exception:
                        pass

        # Auto-detect tech stack
        tech_stack = self._detect_tech_stack(project_dir)

        # Get last user message as last_task
        last_task = ""
        for msg in reversed(conv.messages):
            if msg.role == "user":
                last_task = msg.content[:200]
                break

        await self.db.save_project_memory(
            project_name=self._active_project_name,
            workspace=str(project_dir),
            summary=note or self._project_memory_cache.get("summary", ""),
            files_list=files_list,
            tech_stack=tech_stack,
            last_task=last_task,
            conversation_snapshot=snapshot,
        )

    def _detect_tech_stack(self, project_dir: Path) -> str:
        """Auto-detect the tech stack of a project."""
        if not project_dir.exists():
            return ""
        
        indicators = []
        if (project_dir / "requirements.txt").exists() or (project_dir / "setup.py").exists():
            indicators.append("Python")
        if (project_dir / "package.json").exists():
            indicators.append("Node.js")
        if (project_dir / "Cargo.toml").exists():
            indicators.append("Rust")
        if (project_dir / "go.mod").exists():
            indicators.append("Go")
        
        # Check for frameworks
        for f in project_dir.rglob("*.py"):
            if not self.fm._should_ignore(f):
                try:
                    content = f.read_text(errors="replace")[:2000]
                    if "flask" in content.lower():
                        indicators.append("Flask")
                    elif "django" in content.lower():
                        indicators.append("Django")
                    elif "fastapi" in content.lower():
                        indicators.append("FastAPI")
                    break
                except Exception:
                    pass
        
        for f in project_dir.rglob("*.html"):
            if not self.fm._should_ignore(f):
                indicators.append("HTML/CSS")
                break
        
        return ", ".join(dict.fromkeys(indicators))  # unique, preserve order

    def _read_project_code_context(self) -> str:
        """Read all code files in the current project folder for AI context."""
        if not self._current_project_folder:
            return ""

        project_dir = Path(self.config.workspace) / self._current_project_folder
        if not project_dir.exists():
            return ""

        code_extensions = {
            ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
            ".json", ".yaml", ".yml", ".toml", ".sql", ".sh",
            ".go", ".rs", ".java", ".rb", ".php", ".md", ".txt",
            ".cfg", ".ini", ".env.example",
        }
        
        context_parts = []
        total_size = 0
        max_total_size = 50000  # 50KB max total context

        for fp in sorted(project_dir.rglob("*")):
            if not fp.is_file() or self.fm._should_ignore(fp):
                continue
            if fp.suffix.lower() not in code_extensions:
                continue
            if fp.stat().st_size > 20000:  # Skip files > 20KB individually
                continue

            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
                rel_path = str(fp.relative_to(self.config.workspace))
                file_block = f"\n### {rel_path}\n```\n{content}\n```\n"
                
                if total_size + len(file_block) > max_total_size:
                    context_parts.append(f"\n... (more files truncated, total size limit reached)")
                    break
                
                context_parts.append(file_block)
                total_size += len(file_block)
            except Exception:
                continue

        return "\n".join(context_parts) if context_parts else ""

    def _format_memory_context(self, mem: dict) -> str:
        """Format project memory into a context string for the system prompt."""
        parts = []
        if mem.get("summary"):
            parts.append(f"- Project summary: {mem['summary']}")
        if mem.get("tech_stack"):
            parts.append(f"- Tech stack: {mem['tech_stack']}")
        if mem.get("last_task"):
            parts.append(f"- Last task the user was working on: {mem['last_task']}")
        if mem.get("files_list"):
            files = mem["files_list"][:20]  # Max 20 files in context
            parts.append(f"- Known project files ({len(mem['files_list'])} total): {', '.join(files)}")
        return "\n".join(parts) if parts else ""

    def _auto_detect_project_name(self, response: str, message: str):
        """Auto-detect project name from plan response or user message."""
        if self._active_project_name:
            return  # Already have a project

        import re
        # Look for FOLDER: pattern in plan
        folder_match = re.search(r'FOLDER:\s*(\S+)', response)
        if folder_match:
            name = folder_match.group(1).strip().rstrip("/")
            self._active_project_name = name
            self._current_project_folder = name
            return

        # Look for PROJECT: pattern
        project_match = re.search(r'PROJECT:\s*(.+?)(?:\n|$)', response)
        if project_match:
            name = project_match.group(1).strip().lower().replace(" ", "-")
            name = re.sub(r'[^a-z0-9-_]', '', name)[:30]
            if name:
                self._active_project_name = name
                self._current_project_folder = name
                return
