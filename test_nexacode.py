#!/usr/bin/env python3
"""
+======================================================================+
|                  NEXACODE v2.1 FULL TEST SUITE                       |
|        Tests all modules including new fixes and features            |
+======================================================================+
"""
import sys
import os
import asyncio
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}" + (f" -- {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))


def test_all():
    global PASS, FAIL

    # ==================================================================
    # TEST 1: CONFIG MODULE
    # ==================================================================
    print("\n=== Test 1: Configuration ===")
    from nexacode.config.settings import (
        NexaCodeConfig, ModelConfig, AgentConfig,
        DEFAULT_PROVIDERS, APP_NAME, APP_VERSION, APP_CODENAME,
        TASK_SYSTEM_PROMPTS, detect_task_type,
    )

    config = NexaCodeConfig()
    providers = list(DEFAULT_PROVIDERS.keys())
    agents = list(config.agents.keys())

    check("App name", APP_NAME == "NexaCode", f"{APP_NAME}")
    check("Version format", "." in APP_VERSION, f"v{APP_VERSION}")
    check("Version is 3.x", APP_VERSION.startswith("3."), f"v{APP_VERSION}")
    check("Codename is Deep-Think", APP_CODENAME == "Deep-Think", f"'{APP_CODENAME}'")
    check("10 providers", len(DEFAULT_PROVIDERS) >= 10, f"{len(DEFAULT_PROVIDERS)} found")
    check("Provider list", all(p in providers for p in ["openai", "anthropic", "gemini", "groq"]))
    check("5 default agents", len(agents) >= 5, str(agents))
    check("Agent pipeline", len(config.agent_pipeline) >= 3)

    # Test ModelConfig serialization
    mc = ModelConfig(name="test", provider="openai", model_id="gpt-4o", api_key="sk-test")
    d = mc.to_dict()
    check("ModelConfig.to_dict()", "provider" in d and d["provider"] == "openai")

    # Test AgentConfig
    ac = config.agents.get("coder")
    check("Coder agent exists", ac is not None)
    check("Coder has system_prompt", len(ac.system_prompt) > 50 if ac else False)

    # v3.0: Task-specific system prompts
    check("Task prompts exist", len(TASK_SYSTEM_PROMPTS) >= 6, f"{len(TASK_SYSTEM_PROMPTS)} prompts")
    check("Planning prompt", "planning" in TASK_SYSTEM_PROMPTS and len(TASK_SYSTEM_PROMPTS["planning"]) > 100)
    check("Coding prompt", "coding" in TASK_SYSTEM_PROMPTS and "File:" in TASK_SYSTEM_PROMPTS["coding"])
    check("Debugging prompt", "debugging" in TASK_SYSTEM_PROMPTS)
    check("Editing prompt", "editing" in TASK_SYSTEM_PROMPTS)
    check("Explaining prompt", "explaining" in TASK_SYSTEM_PROMPTS)
    check("Reviewing prompt", "reviewing" in TASK_SYSTEM_PROMPTS)
    check("Default prompt", "default" in TASK_SYSTEM_PROMPTS)

    # v3.0: Task type detection
    check("Detect planning", detect_task_type("build a todo app") == "planning")
    check("Detect planning (create)", detect_task_type("create a REST API") == "planning")
    check("Detect debugging", detect_task_type("fix this bug in my code") == "debugging")
    check("Detect debugging (error)", detect_task_type("I'm getting an error") == "debugging")
    check("Detect editing", detect_task_type("edit the login page") == "editing")
    check("Detect explaining", detect_task_type("explain how async works") == "explaining")
    check("Detect reviewing", detect_task_type("review this code") == "reviewing")
    check("Detect default", detect_task_type("hello there") == "default")
    check("Detect Hindi/Urdu", detect_task_type("ek calculator banao") == "planning")

    # v3.0: Gemini thinking models
    gemini_info = DEFAULT_PROVIDERS.get("gemini", {})
    thinking_models = gemini_info.get("thinking_models", [])
    check("Thinking models defined", len(thinking_models) >= 2, str(thinking_models))
    check("2.5-flash in thinking", any("2.5-flash" in m for m in thinking_models))

    # ==================================================================
    # TEST 2: AI ENGINE (core)
    # ==================================================================
    print("\n=== Test 2: AI Engine ===")
    from nexacode.core.engine import (
        AIEngine, Message, Conversation,
        AIEngineError, ProviderAuthError, ProviderRateLimit, ProviderAPIError,
    )

    engine = AIEngine(config)

    # Test Message creation and serialization
    msg = Message(role="user", content="Hello world")
    check("Message creation", msg.role == "user")

    # OpenAI format
    d = msg.to_api_dict("openai")
    check("OpenAI format", d["role"] == "user" and d["content"] == "Hello world")

    # Anthropic format
    d = msg.to_api_dict("anthropic")
    check("Anthropic format", d is not None and d["role"] == "user")

    # Gemini format
    d = msg.to_api_dict("gemini")
    check("Gemini format", d["role"] == "user" and "parts" in d)

    # System message in Anthropic should return None
    sys_msg = Message(role="system", content="You are helpful")
    d = sys_msg.to_api_dict("anthropic")
    check("Anthropic system=None", d is None)

    # Test Conversation
    conv = engine.get_conversation()
    conv.add_message("user", "Hello")
    conv.add_message("assistant", "Hi!")
    check("Conversation messages", len(conv.messages) == 2)

    # Test context retrieval
    ctx = conv.get_context(max_messages=1)
    check("Context limiting", len(ctx) == 1)

    # Test retry buffer
    conv.save_retry_point()
    check("Retry buffer saved", conv._retry_buffer is not None)
    check("Retry buffer content", conv._retry_buffer.content == "Hello")

    # Test pop_last_failed
    conv.pop_last_failed()
    check("Pop last failed", len(conv.messages) == 1, "removed assistant msg")

    # Test conversation clear
    conv.clear()
    check("Clear conversation", len(conv.messages) == 0)

    # Test URL building
    openai_mc = ModelConfig(name="test", provider="openai", model_id="gpt-4o")
    url = engine._build_url(openai_mc)
    check("OpenAI URL", "/chat/completions" in url)

    anthropic_mc = ModelConfig(name="test", provider="anthropic", model_id="claude-sonnet-4-20250514")
    url = engine._build_url(anthropic_mc)
    check("Anthropic URL", "/messages" in url)

    gemini_mc = ModelConfig(name="test", provider="gemini", model_id="gemini-2.0-flash", api_key="test-key")
    url = engine._build_url(gemini_mc, stream=True)
    check("Gemini stream URL", "streamGenerateContent" in url and "alt=sse" in url)

    url_nostream = engine._build_url(gemini_mc, stream=False)
    check("Gemini non-stream URL", "generateContent" in url_nostream and "alt=sse" not in url_nostream)

    groq_mc = ModelConfig(name="test", provider="groq", model_id="llama-3.3-70b",
                          base_url="https://api.groq.com/openai/v1")
    url = engine._build_url(groq_mc)
    check("Groq URL", "groq.com" in url and "/chat/completions" in url)

    ollama_mc = ModelConfig(name="test", provider="ollama", model_id="llama3.2",
                            base_url="http://localhost:11434/v1")
    url = engine._build_url(ollama_mc)
    check("Ollama URL", "localhost:11434" in url)

    # Test payload building
    msgs = [Message(role="user", content="test")]
    payload = engine._build_payload(openai_mc, msgs, system_prompt="Be helpful")
    check("OpenAI payload", "messages" in payload and payload["model"] == "gpt-4o")
    check("OpenAI system in messages", any(m["role"] == "system" for m in payload["messages"]))

    payload = engine._build_payload(anthropic_mc, msgs, system_prompt="Be helpful")
    check("Anthropic payload", "system" in payload and payload["system"] == "Be helpful")

    payload = engine._build_payload(gemini_mc, msgs, system_prompt="Be helpful")
    check("Gemini payload", "contents" in payload and "systemInstruction" in payload)

    # Test stream text extraction
    # OpenAI chunk
    openai_chunk = {"choices": [{"delta": {"content": "Hello"}}]}
    text = engine._extract_stream_text(openai_chunk, "openai")
    check("Extract OpenAI stream", text == "Hello")

    # Anthropic chunk
    anthropic_chunk = {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "World"}}
    text = engine._extract_stream_text(anthropic_chunk, "anthropic")
    check("Extract Anthropic stream", text == "World")

    # Gemini chunk
    gemini_chunk = {"candidates": [{"content": {"parts": [{"text": "Gemini!"}]}}]}
    text = engine._extract_stream_text(gemini_chunk, "gemini")
    check("Extract Gemini stream", text == "Gemini!")

    # Empty/malformed chunks
    check("Empty OpenAI chunk", engine._extract_stream_text({}, "openai") == "")
    check("Empty Anthropic chunk", engine._extract_stream_text({}, "anthropic") == "")
    check("Empty Gemini chunk", engine._extract_stream_text({}, "gemini") == "")
    check("Malformed chunk", engine._extract_stream_text({"bad": "data"}, "openai") == "")

    # Test error types
    try:
        raise ProviderAuthError("openai", 401, "Invalid key")
    except ProviderAuthError as e:
        check("ProviderAuthError", e.provider == "openai" and e.status == 401)

    try:
        raise ProviderRateLimit("anthropic", 30.0)
    except ProviderRateLimit as e:
        check("ProviderRateLimit", e.retry_after == 30.0)

    try:
        raise ProviderAPIError("gemini", 500, "Server error")
    except ProviderAPIError as e:
        check("ProviderAPIError", e.status == 500)

    # Test usage stats
    stats = engine.get_usage_stats()
    check("Usage stats", "total_requests" in stats and "errors" in stats)

    # v3.0: Test thinking mode detection
    gemini_thinking_mc = ModelConfig(name="test", provider="gemini", model_id="gemini-2.5-flash", api_key="test-key")
    check("Thinking model (2.5-flash)", engine._is_thinking_model(gemini_thinking_mc))
    
    gemini_old_mc = ModelConfig(name="test", provider="gemini", model_id="gemini-2.0-flash", api_key="test-key")
    check("Non-thinking model (2.0-flash)", not engine._is_thinking_model(gemini_old_mc))
    
    deepseek_reasoner_mc = ModelConfig(name="test", provider="deepseek", model_id="deepseek-reasoner", api_key="test-key")
    check("DeepSeek reasoner thinking", engine._is_thinking_model(deepseek_reasoner_mc))
    
    openai_mc_think = ModelConfig(name="test", provider="openai", model_id="gpt-4o", api_key="test-key")
    check("OpenAI not thinking", not engine._is_thinking_model(openai_mc_think))

    # v3.0: Test thinking model payload has thinkingConfig
    gemini_payload = engine._build_payload(gemini_thinking_mc, [Message(role="user", content="test")], system_prompt="test")
    check("Thinking payload has config", "thinkingConfig" in gemini_payload.get("generationConfig", {}))
    
    gemini_old_payload = engine._build_payload(gemini_old_mc, [Message(role="user", content="test")], system_prompt="test")
    check("Non-thinking no config", "thinkingConfig" not in gemini_old_payload.get("generationConfig", {}))

    # v3.0: Test thought part filtering in stream extraction
    thought_chunk = {"candidates": [{"content": {"parts": [{"thought": True, "text": "thinking..."}, {"text": "answer"}]}}]}
    text = engine._extract_stream_text(thought_chunk, "gemini")
    check("Filters thought parts", text == "answer", f"got: {text}")

    # Test connection error formatting
    error_msg = engine._format_connection_error(ollama_mc)
    check("Ollama error hint", "ollama" in error_msg.lower())

    # ==================================================================
    # TEST 3: AGENT ORCHESTRATOR
    # ==================================================================
    print("\n=== Test 3: Agent Orchestrator ===")
    from nexacode.agents.orchestrator import AgentOrchestrator, Agent, AgentStatus, AgentResult

    orchestrator = AgentOrchestrator(config, engine)
    agent_names = list(orchestrator.agents.keys())

    check("Orchestrator init", len(orchestrator.agents) >= 5, f"{len(orchestrator.agents)} agents")
    check("All agents idle", all(a.status == AgentStatus.IDLE for a in orchestrator.agents.values()))

    # Test get_agent
    coder = orchestrator.get_agent("coder")
    check("Get coder agent", coder is not None)
    check("Coder config", coder.config.name == "Coder")

    nonexistent = orchestrator.get_agent("nonexistent")
    check("Get nonexistent agent", nonexistent is None)

    # Test agent prompt building
    prev_results = [AgentResult(
        agent_name="Architect", role="architect",
        content="Build a REST API with Flask",
        status=AgentStatus.DONE,
    )]
    prompt = coder._build_prompt("Implement the API", "workspace: /test", prev_results)
    check("Agent prompt building", "Architect" in prompt and "REST API" in prompt)

    # Test reset
    orchestrator.reset_all()
    check("Reset all agents", all(a.status == AgentStatus.IDLE for a in orchestrator.agents.values()))

    # ==================================================================
    # TEST 4: FILE MANAGER
    # ==================================================================
    print("\n=== Test 4: File Manager ===")
    from nexacode.tools.file_manager import FileManager

    proj_dir = os.path.dirname(os.path.abspath(__file__))
    fm = FileManager(proj_dir)

    # Read file
    result = fm.read_file("requirements.txt")
    check("Read file", result["success"], f"{result.get('total_lines', 0)} lines")

    # Tree
    tree = fm.list_dir(recursive=True, max_depth=2)
    check("List dir tree", tree["success"], f"{len(tree.get('tree', []))} items")

    # Glob
    glob_res = fm.glob_search("*.py")
    check("Glob *.py", len(glob_res) > 0, f"{len(glob_res)} files")

    # Grep
    grep_res = fm.grep_search("import", include="*.py")
    check("Grep 'import'", len(grep_res) > 0, f"{len(grep_res)} matches")

    # Write + Edit + Read cycle
    test_file = os.path.join(tempfile.gettempdir(), "nexacode_test_file.txt")
    w = fm.write_file(test_file, "hello world\nfoo bar\n")
    check("Write file", w["success"])

    e = fm.edit_file(test_file, "foo bar", "baz qux")
    check("Edit file", e["success"])

    r = fm.read_file(test_file)
    check("Read after edit", "baz qux" in r.get("content", ""))

    # Multi-edit
    fm.write_file(test_file, "line1\nline2\nline3\n")
    me = fm.multi_edit(test_file, [("line1", "LINE_ONE"), ("line3", "LINE_THREE")])
    check("Multi-edit", me["success"])
    r = fm.read_file(test_file)
    check("Multi-edit content", "LINE_ONE" in r["content"] and "LINE_THREE" in r["content"])

    # Project stats
    stats = fm.get_project_stats()
    check("Project stats", stats["total_files"] > 0, f"{stats['total_files']} files")

    # Path resolution
    resolved = fm._resolve_path("test.py")
    check("Path resolution", str(resolved).endswith("test.py"))

    # ==================================================================
    # TEST 5: CODE EXECUTOR
    # ==================================================================
    print("\n=== Test 5: Code Executor ===")
    from nexacode.tools.executor import CodeExecutor, ExecutionResult

    executor = CodeExecutor(".")
    check("Language support", len(executor.LANGUAGE_MAP) >= 12, f"{len(executor.LANGUAGE_MAP)} languages")

    async def test_exec():
        # Shell command
        r = await executor.execute_command('echo "hello nexacode"')
        check("Shell command", r.success and "hello nexacode" in r.stdout)

        # Python code
        r2 = await executor.execute_code('print("NexaCode rocks!")', "python")
        check("Python execution", r2.success and "NexaCode rocks!" in r2.stdout)

        # Failing command
        r3 = await executor.execute_command("false")
        check("Failing command", not r3.success and r3.exit_code != 0)

        # Timeout
        r4 = await executor.execute_command("sleep 10", timeout=1)
        check("Command timeout", r4.killed or not r4.success)

        # Framework detection
        framework = executor._detect_test_framework()
        check("Framework detection", framework in ["pytest", "jest", "vitest", "cargo", "go"])

        return True

    asyncio.run(test_exec())

    # ==================================================================
    # TEST 6: DATABASE
    # ==================================================================
    print("\n=== Test 6: Database ===")
    from nexacode.db.database import Database

    async def test_db():
        db_path = os.path.join(tempfile.gettempdir(), "nexacode_test_v21.db")
        db = Database(db_path)
        await db.connect()

        # Sessions
        await db.create_session("test-1", "Test Session", "/tmp", "gpt-4o", "coder")
        session = await db.get_session("test-1")
        check("Create session", session is not None)

        sessions = await db.list_sessions()
        check("List sessions", len(sessions) >= 1)

        # Messages
        await db.save_message("test-1", "user", "Hello")
        await db.save_message("test-1", "assistant", "Hi there!", agent_name="Coder", model="gpt-4o")
        messages = await db.get_messages("test-1")
        check("Save/get messages", len(messages) >= 2)

        # Search
        search = await db.search_messages("Hello")
        check("Search messages", len(search) > 0)

        # File operations
        await db.log_file_operation("test-1", "write", "/tmp/test.py", content_after="print('hi')")
        file_hist = await db.get_file_history(session_id="test-1")
        check("File operation logging", len(file_hist) > 0)

        # Snippets
        sid = await db.save_snippet("test", 'print("hello")', "python", ["test"])
        snippets = await db.get_snippets()
        check("Snippets", len(snippets) > 0)

        # Cache
        await db.cache_set("test_key", {"value": 42}, ttl=3600)
        cached = await db.cache_get("test_key")
        check("Cache set/get", cached is not None and cached.get("value") == 42)

        # Usage stats
        await db.log_usage("test-1", "gpt-4o", "openai", 100, 200, 0.01, 1.5)
        usage = await db.get_usage_summary()
        check("Usage stats", "by_model" in usage and "total" in usage)

        # Session update
        await db.update_session("test-1", name="Updated Session")
        updated = await db.get_session("test-1")
        check("Session update", updated["name"] == "Updated Session")

        # Cleanup
        await db.delete_session("test-1")
        deleted = await db.get_session("test-1")
        check("Delete session", deleted is None)

        await db.close()
        # Cleanup test db
        try:
            os.unlink(db_path)
        except Exception:
            pass
        return True

    asyncio.run(test_db())

    # ==================================================================
    # TEST 7: UI COMPONENTS
    # ==================================================================
    print("\n=== Test 7: UI Components ===")
    from nexacode.ui import terminal as ui_mod

    # These should not crash
    try:
        ui_mod.show_banner()
        check("Banner render", True)
    except Exception as e:
        check("Banner render", False, str(e))

    try:
        ui_mod.show_welcome("/tmp/test", "gpt-4o", "test-session")
        check("Welcome render", True)
    except Exception as e:
        check("Welcome render", False, str(e))

    try:
        ui_mod.show_help()
        check("Help render", True)
    except Exception as e:
        check("Help render", False, str(e))

    try:
        ui_mod.show_success("Test success")
        ui_mod.show_warning("Test warning")
        ui_mod.show_info("Test info")
        ui_mod.show_error("Test error")
        check("Status messages", True)
    except Exception as e:
        check("Status messages", False, str(e))

    try:
        ui_mod.show_code('print("hello")', "python", "test.py")
        check("Code display", True)
    except Exception as e:
        check("Code display", False, str(e))

    try:
        ui_mod.show_models_table({
            "test-model": ModelConfig(name="test", provider="openai", model_id="gpt-4o")
        }, "test-model")
        check("Models table", True)
    except Exception as e:
        check("Models table", False, str(e))

    try:
        ui_mod.show_providers_table()
        check("Providers table", True)
    except Exception as e:
        check("Providers table", False, str(e))

    try:
        ui_mod.show_agent_status({
            "coder": {"role": "coder", "icon": ">>", "status": "idle", "model": "gpt-4o", "tokens": 0}
        })
        check("Agent status display", True)
    except Exception as e:
        check("Agent status display", False, str(e))

    # ==================================================================
    # TEST 8: UTILITIES
    # ==================================================================
    print("\n=== Test 8: Utilities ===")
    from nexacode.utils.helpers import (
        format_size, format_duration, format_tokens,
        extract_code_blocks, extract_file_actions, detect_language,
        count_tokens_estimate, is_binary_file, sanitize_filename,
        get_system_info, Timer, truncate_string, hash_content,
    )

    check("format_size(1MB)", format_size(1048576) == "1.0MB")
    check("format_size(0)", format_size(0) == "0.0B")
    check("format_duration(0.5s)", "ms" in format_duration(0.5))
    check("format_duration(125s)", "2m" in format_duration(125.5))
    check("format_duration(7200s)", "2h" in format_duration(7200))
    check("format_tokens(15K)", format_tokens(15000) == "15.0K")
    check("format_tokens(100)", format_tokens(100) == "100")
    check("detect_language(.py)", detect_language("app.py") == "python")
    check("detect_language(.ts)", detect_language("index.ts") == "typescript")
    check("detect_language(.rs)", detect_language("main.rs") == "rust")
    check("detect_language(.go)", detect_language("main.go") == "go")

    # Code block extraction
    md_text = '```python\nprint("hello")\n```\n\nSome text\n\n```javascript\nconsole.log("hi")\n```'
    blocks = extract_code_blocks(md_text)
    check("Extract code blocks", len(blocks) == 2)
    check("Code block languages", blocks[0]["language"] == "python" and blocks[1]["language"] == "javascript")

    # File action extraction
    action_text = '```action\nACTION: create\nFILE: src/app.py\nCONTENT:\nprint("hello")\n```'
    actions = extract_file_actions(action_text)
    check("Extract file actions", len(actions) >= 1)

    # Other utilities
    check("truncate_string", len(truncate_string("a" * 200, 50)) == 50)
    check("hash_content", len(hash_content("test")) == 12)
    check("count_tokens", count_tokens_estimate("hello world") == 2)

    info = get_system_info()
    check("System info", "os" in info and "python" in info)

    safe = sanitize_filename('my<file>:test?.txt')
    check("sanitize_filename", "<" not in safe and "?" not in safe)

    with Timer() as t:
        pass
    check("Timer", t.elapsed >= 0)

    # ==================================================================
    # TEST 9: COMMAND HANDLER
    # ==================================================================
    print("\n=== Test 9: Command Handler ===")
    from nexacode.core.commands import CommandHandler

    async def test_handler():
        db = Database(os.path.join(tempfile.gettempdir(), "nexacode_test_handler.db"))
        await db.connect()
        handler = CommandHandler(
            config=config,
            engine=engine,
            orchestrator=orchestrator,
            file_manager=fm,
            executor=CodeExecutor("."),
            database=db,
        )
        check("Handler session ID", len(handler.session_id) == 8)

        # Test exit
        result = await handler.handle("/quit")
        check("/quit returns False", result == False)

        # Test help
        result = await handler.handle("/help")
        check("/help returns True", result == True)

        # Test version
        result = await handler.handle("/version")
        check("/version works", result == True)

        # Test tree
        result = await handler.handle("/tree")
        check("/tree works", result == True)

        # Test stats
        result = await handler.handle("/stats")
        check("/stats works", result == True)

        # Test config
        result = await handler.handle("/config")
        check("/config works", result == True)

        # Test agents
        result = await handler.handle("/agents")
        check("/agents works", result == True)

        # Test providers
        result = await handler.handle("/providers")
        check("/providers works", result == True)

        # Test model list
        result = await handler.handle("/model list")
        check("/model list works", result == True)

        # Test unknown command
        result = await handler.handle("/unknowncmd")
        check("Unknown command", result == True)

        # Test empty input
        result = await handler.handle("")
        check("Empty input", result == True)

        # Test /save with no pending
        result = await handler.handle("/save")
        check("/save no pending", result == True)

        # Test file detection
        test_response = '```python\n# File: test_output.py\nprint("auto-saved!")\n```'
        handler._detect_and_offer_save(test_response)
        check("File detection", len(handler._pending_files) == 1)
        check("Detected path", handler._pending_files[0]["path"] == "test_output.py")

        # Test _build_enhanced_system_prompt
        prompt = handler._build_enhanced_system_prompt("base prompt")
        check("Enhanced prompt", "WORKSPACE" in prompt and "base prompt" in prompt)
        check("Enhanced has file format", "File:" in prompt)
        check("Enhanced has project folder rule", "PROJECT FOLDER" in prompt.upper() or "project folder" in prompt.lower() or "FOLDER" in prompt)
        check("Enhanced has commands format", "commands" in prompt)

        # v3.0: Test state machine
        check("Initial state idle", handler._state == handler.STATE_IDLE)
        
        # v3.0: Test file detection
        test_response_files = '```python\n# File: my-app/main.py\nprint("hello world")\n```\n\n```javascript\n// File: my-app/index.js\nconsole.log("hi")\n```'
        files = handler._detect_files_in_response(test_response_files)
        check("Detect multiple files", len(files) == 2, f"found {len(files)}")
        check("File 1 path", files[0]["path"] == "my-app/main.py" if files else False)
        check("File 2 path", files[1]["path"] == "my-app/index.js" if len(files) > 1 else False)

        # v3.0: Test HTML file detection
        html_response = '```html\n<!-- File: my-app/index.html -->\n<html><body>Hello</body></html>\n```'
        html_files = handler._detect_files_in_response(html_response)
        check("Detect HTML file", len(html_files) == 1 and "index.html" in html_files[0]["path"])

        # v3.0: Test command detection
        cmd_response = 'Here is the code:\n```commands\ncd my-app\npip install flask\npython app.py\n```'
        cmds = handler._detect_commands_in_response(cmd_response)
        check("Detect commands", len(cmds) == 3, f"found {len(cmds)}")
        check("Command 1", cmds[0] == "cd my-app" if cmds else False)

        # v3.0: Test bash block detection
        bash_response = '```bash\nnpm install\nnpm start\n```'
        bash_cmds = handler._detect_commands_in_response(bash_response)
        check("Detect bash commands", len(bash_cmds) == 2)

        await db.close()
        # Cleanup
        try:
            os.unlink(os.path.join(tempfile.gettempdir(), "nexacode_test_handler.db"))
        except Exception:
            pass

    asyncio.run(test_handler())

    # ==================================================================
    # TEST 10: INTEGRATION - Multi-provider payload validation
    # ==================================================================
    print("\n=== Test 10: Multi-Provider Integration ===")

    test_providers = [
        ("openai", "gpt-4o", "https://api.openai.com/v1"),
        ("anthropic", "claude-sonnet-4-20250514", "https://api.anthropic.com/v1"),
        ("gemini", "gemini-2.0-flash", "https://generativelanguage.googleapis.com/v1beta"),
        ("groq", "llama-3.3-70b-versatile", "https://api.groq.com/openai/v1"),
        ("deepseek", "deepseek-chat", "https://api.deepseek.com/v1"),
        ("openrouter", "openai/gpt-4o", "https://openrouter.ai/api/v1"),
        ("together", "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "https://api.together.xyz/v1"),
        ("ollama", "llama3.2", "http://localhost:11434/v1"),
        ("lmstudio", "local-model", "http://localhost:1234/v1"),
        ("custom", "my-model", "http://my-api.com/v1"),
    ]

    for provider, model_id, base_url in test_providers:
        mc = ModelConfig(
            name=f"test-{provider}", provider=provider,
            model_id=model_id, api_key="test-key", base_url=base_url,
        )

        # Test URL building
        url = engine._build_url(mc, stream=True)
        check(f"{provider} URL", len(url) > 10, url[:60])

        # Test payload building
        msgs = [Message(role="user", content="test")]
        payload = engine._build_payload(mc, msgs, system_prompt="Be helpful", stream=True)
        if provider == "gemini":
            check(f"{provider} payload", "contents" in payload)
        elif provider == "anthropic":
            check(f"{provider} payload", "messages" in payload and "system" in payload)
        else:
            check(f"{provider} payload", "messages" in payload and "model" in payload)

    # ==================================================================
    # SUMMARY
    # ==================================================================
    print("\n" + "=" * 60)
    total = PASS + FAIL
    if FAIL == 0:
        print(f"  ALL {total} TESTS PASSED!")
        print(f"  NexaCode v{APP_VERSION} '{APP_CODENAME}' is fully operational!")
    else:
        print(f"  {PASS}/{total} passed, {FAIL} FAILED")
    print("=" * 60)

    return FAIL == 0


if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
