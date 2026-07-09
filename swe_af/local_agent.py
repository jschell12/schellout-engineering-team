"""LocalAgent — replaces AgentField's Agent class for standalone execution.

Provides the same interface (call, note, reasoner decorator) without requiring
an AgentField control plane. Reasoners are just async functions dispatched locally.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Minimal execution context replacing app.ctx."""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class ReasonerFailed(Exception):
    """Replaces agentfield.ReasonerFailed."""
    pass


class LocalAgent:
    """Standalone agent that dispatches reasoners as local async function calls.

    Drop-in replacement for agentfield.Agent with the subset of API used by SWE-AF.
    """

    def __init__(self, node_id: str = "swe-planner", **kwargs):
        self.node_id = node_id
        self._reasoners: dict[str, Callable] = {}
        self._routers: list["LocalRouter"] = []
        self.ctx = ExecutionContext()
        self.harness = None  # Set externally if needed

    def reasoner(self, fn=None, **kwargs):
        """Register a reasoner function."""
        def decorator(f):
            name = f.__name__
            self._reasoners[name] = f
            return f
        if fn is not None:
            return decorator(fn)
        return decorator

    def include_router(self, router: "LocalRouter"):
        """Include a router's reasoners."""
        self._routers.append(router)

    async def call(self, target: str, **kwargs) -> Any:
        """Dispatch to a registered reasoner.

        target format: "node-id.reasoner_name" or just "reasoner_name"
        """
        # Strip node_id prefix
        name = target.split(".")[-1] if "." in target else target

        # Search local reasoners first, then routers
        fn = self._reasoners.get(name)
        if fn is None:
            for router in self._routers:
                fn = router._reasoners.get(name)
                if fn:
                    break

        if fn is None:
            raise ReasonerFailed(f"Unknown reasoner: {name} (target: {target})")

        logger.info(f"Dispatching: {target}")
        try:
            result = await fn(**kwargs)
            return result
        except Exception as e:
            logger.error(f"Reasoner {name} failed: {e}")
            raise

    def note(self, message: str, tags: list[str] | None = None, **kwargs):
        """Log a note (replaces app.note for observability)."""
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        logger.info(f"[NOTE{tag_str}] {message}")

    async def pause(self, *args, **kwargs):
        """No-op — HITL approval not used in standalone mode."""
        return {"approved": True}

    def run(self, host: str = "0.0.0.0", port: int = 8003, **kwargs):
        """Run the orchestrator. In standalone mode, this is a no-op.
        Use build() directly instead."""
        logger.info(f"LocalAgent {self.node_id} ready (standalone mode)")


class LocalRouter:
    """Replaces AgentField's AgentRouter for grouping related reasoners."""

    def __init__(self, tags: list[str] | None = None, **kwargs):
        self.tags = tags or []
        self._reasoners: dict[str, Callable] = {}
        self.harness = None  # Set externally
        self._ai = None  # Set externally

    def reasoner(self, fn=None, **kwargs):
        """Register a reasoner function."""
        def decorator(f):
            self._reasoners[f.__name__] = f
            return f
        if fn is not None:
            return decorator(fn)
        return decorator

    def note(self, message: str, tags: list[str] | None = None, **kwargs):
        """Log a note."""
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        logger.info(f"[NOTE{tag_str}] {message}")

    async def ai(self, prompt: str, system: str = "", schema=None, model=None, **kwargs):
        """Lightweight LLM call without tools (replaces router.ai()).
        Uses the harness with no tools."""
        from .harness import invoke_persona
        result = await invoke_persona(
            role="qa_synthesizer",
            prompt=prompt,
            schema=schema,
            system_prompt=system,
            model=model,
        )
        return result
