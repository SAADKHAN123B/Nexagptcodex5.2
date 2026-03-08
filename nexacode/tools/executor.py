"""
╔══════════════════════════════════════════════════════════════════╗
║                NEXACODE CODE EXECUTOR                           ║
║        Sandboxed Code Execution & Test Runner                    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import signal
import subprocess
import tempfile
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ExecutionResult:
    """Result from code execution."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time: float = 0.0
    command: str = ""
    language: str = ""
    success: bool = True
    killed: bool = False
    error: str = ""


class CodeExecutor:
    """Execute code in multiple languages with sandboxing."""

    LANGUAGE_MAP = {
        ".py": {"cmd": "python3", "name": "Python"},
        ".js": {"cmd": "node", "name": "JavaScript"},
        ".ts": {"cmd": "npx tsx", "name": "TypeScript"},
        ".sh": {"cmd": "bash", "name": "Shell"},
        ".bash": {"cmd": "bash", "name": "Bash"},
        ".rb": {"cmd": "ruby", "name": "Ruby"},
        ".go": {"cmd": "go run", "name": "Go"},
        ".rs": {"cmd": "rustc", "name": "Rust"},
        ".java": {"cmd": "java", "name": "Java"},
        ".php": {"cmd": "php", "name": "PHP"},
        ".pl": {"cmd": "perl", "name": "Perl"},
        ".r": {"cmd": "Rscript", "name": "R"},
        ".lua": {"cmd": "lua", "name": "Lua"},
    }

    def __init__(self, workspace: str = ".", timeout: int = 60):
        self.workspace = Path(workspace).resolve()
        self.timeout = timeout
        self.history: List[ExecutionResult] = []
        self.running_processes: Dict[str, subprocess.Popen] = {}

    async def execute_command(
        self,
        command: str,
        cwd: str = None,
        timeout: int = None,
        env: Dict[str, str] = None,
    ) -> ExecutionResult:
        """Execute a shell command."""
        timeout = timeout or self.timeout
        work_dir = cwd or str(self.workspace)
        start_time = time.time()

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
                env=merged_env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ExecutionResult(
                    command=command,
                    exit_code=-1,
                    killed=True,
                    success=False,
                    error=f"Command timed out after {timeout}s",
                    execution_time=time.time() - start_time,
                )

            result = ExecutionResult(
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=process.returncode,
                command=command,
                success=process.returncode == 0,
                execution_time=time.time() - start_time,
            )
            self.history.append(result)
            return result

        except Exception as e:
            return ExecutionResult(
                command=command,
                exit_code=-1,
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
            )

    async def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: int = None,
    ) -> ExecutionResult:
        """Execute code in a specific language."""
        ext_map = {
            "python": ".py", "javascript": ".js", "js": ".js",
            "typescript": ".ts", "ts": ".ts", "shell": ".sh",
            "bash": ".sh", "ruby": ".rb", "go": ".go",
            "rust": ".rs", "java": ".java", "php": ".php",
            "perl": ".pl", "r": ".r", "lua": ".lua",
        }

        ext = ext_map.get(language.lower(), f".{language}")
        lang_config = self.LANGUAGE_MAP.get(ext)

        if not lang_config:
            return ExecutionResult(
                success=False,
                error=f"Unsupported language: {language}",
                language=language,
            )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=ext, dir=str(self.workspace),
            delete=False, prefix="nexacode_",
        ) as f:
            f.write(code)
            temp_path = f.name

        try:
            cmd = f"{lang_config['cmd']} {temp_path}"
            result = await self.execute_command(cmd, timeout=timeout)
            result.language = lang_config["name"]
            return result
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    async def run_tests(
        self,
        test_path: str = None,
        framework: str = "auto",
        verbose: bool = True,
    ) -> ExecutionResult:
        """Run test suite."""
        if framework == "auto":
            framework = self._detect_test_framework()

        commands = {
            "pytest": f"python3 -m pytest {test_path or '.'} -v --tb=short --color=yes",
            "unittest": f"python3 -m unittest discover {test_path or '.'} -v",
            "jest": f"npx jest {test_path or ''} --verbose --colors",
            "mocha": f"npx mocha {test_path or '.'} --recursive",
            "vitest": f"npx vitest run {test_path or ''} --reporter=verbose",
            "go": f"go test {test_path or './...'} -v",
            "cargo": f"cargo test {test_path or ''} -- --nocapture",
            "phpunit": f"./vendor/bin/phpunit {test_path or ''}",
            "rspec": f"bundle exec rspec {test_path or '.'} --format documentation",
        }

        cmd = commands.get(framework)
        if not cmd:
            return ExecutionResult(
                success=False,
                error=f"Unknown test framework: {framework}. Available: {', '.join(commands.keys())}",
            )

        result = await self.execute_command(cmd, timeout=120)
        result.language = framework
        return result

    def _detect_test_framework(self) -> str:
        """Auto-detect the test framework."""
        indicators = {
            "pytest.ini": "pytest",
            "setup.cfg": "pytest",  
            "pyproject.toml": "pytest",
            "jest.config.js": "jest",
            "jest.config.ts": "jest",
            "vitest.config.ts": "vitest",
            "vitest.config.js": "vitest",
            ".mocharc.yml": "mocha",
            "Cargo.toml": "cargo",
            "go.mod": "go",
            "phpunit.xml": "phpunit",
            "Gemfile": "rspec",
        }

        for filename, framework in indicators.items():
            if (self.workspace / filename).exists():
                return framework

        # Check for test files
        py_tests = list(self.workspace.rglob("test_*.py")) + list(self.workspace.rglob("*_test.py"))
        if py_tests:
            return "pytest"

        js_tests = list(self.workspace.rglob("*.test.js")) + list(self.workspace.rglob("*.spec.js"))
        if js_tests:
            return "jest"

        return "pytest"  # Default

    async def install_dependencies(self, package_manager: str = "auto") -> ExecutionResult:
        """Install project dependencies."""
        if package_manager == "auto":
            if (self.workspace / "requirements.txt").exists():
                return await self.execute_command("pip install -r requirements.txt", timeout=120)
            elif (self.workspace / "pyproject.toml").exists():
                return await self.execute_command("pip install -e .", timeout=120)
            elif (self.workspace / "package.json").exists():
                return await self.execute_command("npm install", timeout=120)
            elif (self.workspace / "Cargo.toml").exists():
                return await self.execute_command("cargo build", timeout=120)
            elif (self.workspace / "go.mod").exists():
                return await self.execute_command("go mod download", timeout=120)
            elif (self.workspace / "Gemfile").exists():
                return await self.execute_command("bundle install", timeout=120)
            else:
                return ExecutionResult(success=False, error="No dependency file found")

        cmd_map = {
            "pip": "pip install -r requirements.txt",
            "npm": "npm install",
            "yarn": "yarn install",
            "pnpm": "pnpm install",
            "cargo": "cargo build",
            "go": "go mod download",
            "bundle": "bundle install",
            "composer": "composer install",
        }

        cmd = cmd_map.get(package_manager)
        if not cmd:
            return ExecutionResult(success=False, error=f"Unknown package manager: {package_manager}")
        return await self.execute_command(cmd, timeout=120)

    async def lint_code(self, path: str = None, linter: str = "auto") -> ExecutionResult:
        """Run code linting."""
        target = path or "."
        if linter == "auto":
            if (self.workspace / "pyproject.toml").exists() or list(self.workspace.rglob("*.py")):
                linter = "ruff"
            elif list(self.workspace.rglob("*.js")) or list(self.workspace.rglob("*.ts")):
                linter = "eslint"

        commands = {
            "ruff": f"python3 -m ruff check {target}",
            "flake8": f"python3 -m flake8 {target}",
            "pylint": f"python3 -m pylint {target}",
            "mypy": f"python3 -m mypy {target}",
            "eslint": f"npx eslint {target}",
            "prettier": f"npx prettier --check {target}",
        }

        cmd = commands.get(linter)
        if not cmd:
            return ExecutionResult(success=False, error=f"Unknown linter: {linter}")
        return await self.execute_command(cmd, timeout=60)

    def kill_process(self, pid: str):
        """Kill a running process."""
        proc = self.running_processes.get(pid)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            del self.running_processes[pid]

    def get_execution_history(self, limit: int = 20) -> List[Dict]:
        """Get recent execution history."""
        return [
            {
                "command": r.command,
                "exit_code": r.exit_code,
                "success": r.success,
                "time": f"{r.execution_time:.2f}s",
                "language": r.language,
            }
            for r in self.history[-limit:]
        ]
