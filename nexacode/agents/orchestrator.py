"""
╔══════════════════════════════════════════════════════════════════╗
║                 NEXACODE MULTI-AGENT SYSTEM                     ║
║           Orchestrated AI Agent Pipeline Engine                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import time
import asyncio
from typing import AsyncGenerator, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from nexacode.config.settings import NexaCodeConfig, AgentConfig
from nexacode.core.engine import AIEngine, Conversation


class AgentStatus(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    WORKING = "working"
    REVIEWING = "reviewing"
    TESTING = "testing"
    DONE = "done"
    ERROR = "error"


@dataclass
class AgentResult:
    """Result from an agent execution."""
    agent_name: str
    role: str
    content: str
    status: AgentStatus
    tokens_used: int = 0
    execution_time: float = 0.0
    actions_taken: List[dict] = field(default_factory=list)
    issues_found: List[dict] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Combined result from agent pipeline execution."""
    results: List[AgentResult] = field(default_factory=list)
    total_time: float = 0.0
    total_tokens: int = 0
    status: str = "completed"
    final_output: str = ""


class Agent:
    """A single AI agent with its own personality and capabilities."""

    def __init__(self, config: AgentConfig, engine: AIEngine, app_config: NexaCodeConfig):
        self.config = config
        self.engine = engine
        self.app_config = app_config
        self.status = AgentStatus.IDLE
        self.conversation = Conversation(system_prompt=config.system_prompt)
        self.results_history: List[AgentResult] = []

    async def execute(
        self,
        task: str,
        context: str = "",
        previous_results: List[AgentResult] = None,
        on_token: Callable[[str], None] = None,
    ) -> AgentResult:
        """Execute a task with this agent."""
        start_time = time.time()
        self.status = AgentStatus.WORKING

        # Build the full prompt with context
        full_prompt = self._build_prompt(task, context, previous_results)

        # Get response from AI
        response_text = ""
        model_name = self.config.model or self.app_config.active_model

        try:
            async for chunk in self.engine.chat(
                prompt=full_prompt,
                model_name=model_name,
                system_prompt=self.config.system_prompt,
                conversation=f"agent_{self.config.name}",
                stream=True,
            ):
                response_text += chunk
                if on_token:
                    on_token(chunk)

            self.status = AgentStatus.DONE
        except Exception as e:
            response_text = f"Agent error: {str(e)}"
            self.status = AgentStatus.ERROR

        execution_time = time.time() - start_time
        result = AgentResult(
            agent_name=self.config.name,
            role=self.config.role,
            content=response_text,
            status=self.status,
            tokens_used=len(response_text) // 4,
            execution_time=execution_time,
        )

        # Parse actions from response
        result.actions_taken = self._parse_actions(response_text)
        result.files_modified = self._parse_files(response_text)
        result.issues_found = self._parse_issues(response_text)

        self.results_history.append(result)
        return result

    def _build_prompt(
        self,
        task: str,
        context: str,
        previous_results: List[AgentResult] = None,
    ) -> str:
        """Build comprehensive prompt with context from previous agents."""
        parts = []

        if context:
            parts.append(f"## PROJECT CONTEXT\n{context}\n")

        if previous_results:
            parts.append("## PREVIOUS AGENT RESULTS")
            for r in previous_results:
                parts.append(
                    f"\n### {r.agent_name} ({r.role}) — Status: {r.status.value}\n"
                    f"{r.content}\n"
                )

        parts.append(f"## YOUR TASK\n{task}")
        return "\n".join(parts)

    def _parse_actions(self, response: str) -> List[dict]:
        """Parse action blocks from agent response."""
        actions = []
        lines = response.split("\n")
        in_action_block = False
        current_action = {}

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("ACTION:"):
                in_action_block = True
                current_action = {"type": stripped.split(":", 1)[1].strip()}
            elif in_action_block and stripped.startswith("FILE:"):
                current_action["file"] = stripped.split(":", 1)[1].strip()
            elif in_action_block and stripped == "```":
                if current_action:
                    actions.append(current_action)
                    current_action = {}
                in_action_block = False

        return actions

    def _parse_files(self, response: str) -> List[str]:
        """Extract file paths mentioned in the response."""
        import re
        files = set()
        patterns = [
            r'FILE:\s*(.+?)(?:\n|$)',
            r'`([^`]+\.\w{1,10})`',
            r'path/to/(\S+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, response)
            files.update(matches)
        return list(files)

    def _parse_issues(self, response: str) -> List[dict]:
        """Parse issues from reviewer response."""
        issues = []
        lines = response.split("\n")
        for line in lines:
            stripped = line.strip()
            if "🔴 CRITICAL:" in stripped:
                issues.append({"level": "critical", "message": stripped})
            elif "🟡 WARNING:" in stripped:
                issues.append({"level": "warning", "message": stripped})
            elif "🔵 INFO:" in stripped:
                issues.append({"level": "info", "message": stripped})
        return issues

    def reset(self):
        """Reset agent state."""
        self.status = AgentStatus.IDLE
        self.conversation = Conversation(system_prompt=self.config.system_prompt)


class AgentOrchestrator:
    """
    Orchestrates multiple agents in a pipeline.
    Manages the flow: Architect → Coder → Reviewer → Tester → DevOps
    """

    def __init__(self, config: NexaCodeConfig, engine: AIEngine):
        self.config = config
        self.engine = engine
        self.agents: Dict[str, Agent] = {}
        self._init_agents()

    def _init_agents(self):
        """Initialize all configured agents."""
        for name, agent_config in self.config.agents.items():
            if agent_config.enabled:
                self.agents[name] = Agent(agent_config, self.engine, self.config)

    def get_agent(self, name: str) -> Optional[Agent]:
        return self.agents.get(name)

    async def run_single(
        self,
        agent_name: str,
        task: str,
        context: str = "",
        on_token: Callable[[str], None] = None,
    ) -> AgentResult:
        """Run a single agent."""
        agent = self.agents.get(agent_name)
        if not agent:
            return AgentResult(
                agent_name=agent_name,
                role="unknown",
                content=f"Agent '{agent_name}' not found",
                status=AgentStatus.ERROR,
            )
        return await agent.execute(task, context, on_token=on_token)

    async def run_pipeline(
        self,
        task: str,
        context: str = "",
        pipeline: List[str] = None,
        on_agent_start: Callable[[str, AgentConfig], None] = None,
        on_token: Callable[[str, str], None] = None,
        on_agent_done: Callable[[str, AgentResult], None] = None,
    ) -> PipelineResult:
        """Run the full agent pipeline sequentially."""
        pipeline = pipeline or self.config.agent_pipeline
        start_time = time.time()
        results: List[AgentResult] = []

        for agent_name in pipeline:
            agent = self.agents.get(agent_name)
            if not agent or not agent.config.enabled:
                continue

            if on_agent_start:
                on_agent_start(agent_name, agent.config)

            # Pass previous results as context
            result = await agent.execute(
                task=task,
                context=context,
                previous_results=results,
                on_token=lambda chunk, name=agent_name: on_token(name, chunk) if on_token else None,
            )

            results.append(result)

            if on_agent_done:
                on_agent_done(agent_name, result)

            # If reviewer found critical issues, re-run coder
            if agent_name == "reviewer" and result.issues_found:
                critical = [i for i in result.issues_found if i["level"] == "critical"]
                if critical and "coder" in self.agents:
                    fix_task = f"Fix these critical issues found by the reviewer:\n"
                    for issue in critical:
                        fix_task += f"- {issue['message']}\n"

                    if on_agent_start:
                        on_agent_start("coder", self.agents["coder"].config)

                    fix_result = await self.agents["coder"].execute(
                        task=fix_task,
                        context=context,
                        previous_results=results,
                        on_token=lambda chunk: on_token("coder", chunk) if on_token else None,
                    )
                    results.append(fix_result)

                    if on_agent_done:
                        on_agent_done("coder", fix_result)

        pipeline_result = PipelineResult(
            results=results,
            total_time=time.time() - start_time,
            total_tokens=sum(r.tokens_used for r in results),
            status="completed",
        )

        if results:
            pipeline_result.final_output = results[-1].content

        return pipeline_result

    async def run_parallel(
        self,
        tasks: Dict[str, str],
        context: str = "",
        on_token: Callable[[str, str], None] = None,
    ) -> Dict[str, AgentResult]:
        """Run multiple agents in parallel with different tasks."""
        async def _run_agent(name: str, task: str):
            agent = self.agents.get(name)
            if not agent:
                return name, AgentResult(
                    agent_name=name, role="unknown",
                    content=f"Agent '{name}' not found",
                    status=AgentStatus.ERROR,
                )
            result = await agent.execute(
                task=task, context=context,
                on_token=lambda chunk, n=name: on_token(n, chunk) if on_token else None,
            )
            return name, result

        tasks_coro = [_run_agent(name, task) for name, task in tasks.items()]
        completed = await asyncio.gather(*tasks_coro, return_exceptions=True)

        results = {}
        for item in completed:
            if isinstance(item, Exception):
                continue
            name, result = item
            results[name] = result

        return results

    def reset_all(self):
        """Reset all agents."""
        for agent in self.agents.values():
            agent.reset()
