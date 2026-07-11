"""Persona harness — replaces AgentField's router.harness() with direct CLI/API invocation.

Supports two backends:
- claude: spawns `claude` CLI with tools (for coding, planning, failure diagnosis)
- ollama: calls Ollama HTTP API (for review, QA — free compute)
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel

from .personas import Persona, get_persona

logger = logging.getLogger(__name__)

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://10.0.0.2:11434")


@dataclass
class HarnessResult:
    """Mirrors the interface expected by SWE-AF reasoners."""
    parsed: BaseModel | None = None
    raw: str = ""
    is_error: bool = False
    error_message: str = ""


async def invoke_persona(
    role: str,
    prompt: str,
    schema: type[BaseModel] | None = None,
    system_prompt: str = "",
    model: str | None = None,
    tools: list[str] | None = None,
    cwd: str | None = None,
    issue: dict | None = None,
    timeout: int = 600,
    **kwargs,
) -> HarnessResult:
    """Invoke a persona for a given role.

    Routes to Claude CLI or Ollama based on the persona's backend.
    Falls back to Claude CLI with no persona prefix for mechanical roles.
    """
    persona = get_persona(role, issue=issue)

    if persona and persona.backend == "ollama":
        return await _invoke_ollama(persona, prompt, schema, system_prompt,
                                     timeout=timeout)
    else:
        return await _invoke_claude_cli(persona, prompt, schema, system_prompt,
                                        model=model, tools=tools, cwd=cwd,
                                        timeout=timeout)


async def _invoke_claude_cli(
    persona: Persona | None,
    prompt: str,
    schema: type[BaseModel] | None,
    system_prompt: str,
    model: str | None = None,
    tools: list[str] | None = None,
    cwd: str | None = None,
    timeout: int = 600,
) -> HarnessResult:
    """Invoke Claude CLI (claude -p) with optional persona prefix."""

    # Build system prompt with persona prefix
    full_system = ""
    if persona and persona.system_prefix:
        full_system = persona.system_prefix + "\n\n"
    full_system += system_prompt

    # Build the full prompt with schema instructions
    full_prompt = prompt
    if schema:
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        full_prompt += (
            f"\n\nRespond with ONLY a JSON object matching this schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"Do not include any text outside the JSON object."
        )

    # Write prompt to temp file to avoid shell escaping issues
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(full_prompt)
        prompt_file = f.name

    try:
        cmd = ["claude", "-p", "--output-format", "text"]

        if model:
            cmd.extend(["--model", model])

        # Add system prompt via --system-prompt
        if full_system:
            cmd.extend(["--system-prompt", full_system])

        # Read prompt from stdin
        cmd.extend(["<", prompt_file])

        # Run in the specified working directory
        proc = await asyncio.create_subprocess_exec(
            *["claude", "-p", "--output-format", "text"] +
            (["--model", model] if model else []) +
            (["--system-prompt", full_system] if full_system else []) +
            ["--max-turns", "50"],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd or os.getcwd(),
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=full_prompt.encode()),
            timeout=timeout,
        )

        output = stdout.decode().strip()

        if proc.returncode != 0:
            return HarnessResult(
                is_error=True,
                error_message=f"Claude CLI failed (exit {proc.returncode}): {stderr.decode()[:500]}",
                raw=output,
            )

        if schema:
            parsed = _parse_schema(output, schema)
            if parsed:
                return HarnessResult(parsed=parsed, raw=output)
            else:
                return HarnessResult(
                    is_error=True,
                    error_message=f"Failed to parse output as {schema.__name__}",
                    raw=output,
                )

        return HarnessResult(raw=output)

    finally:
        os.unlink(prompt_file)


async def _invoke_ollama(
    persona: Persona,
    prompt: str,
    schema: type[BaseModel] | None,
    system_prompt: str,
    timeout: int = 600,
) -> HarnessResult:
    """Invoke Ollama API for review/QA personas (free compute)."""

    full_system = ""
    if persona.system_prefix:
        full_system = persona.system_prefix + "\n\n"
    full_system += system_prompt

    full_prompt = prompt
    if schema:
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        full_prompt += (
            f"\n\nRespond with ONLY a JSON object matching this schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"Do not include any text outside the JSON object."
        )

    model = persona.model or "qwen2.5:72b"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": full_system},
            {"role": "user", "content": full_prompt},
        ],
        "stream": False,
        "options": {"num_ctx": 32768},
    }

    # If schema provided, use Ollama's structured output
    if schema:
        payload["format"] = schema.model_json_schema()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
            resp.raise_for_status()

        data = resp.json()
        output = data.get("message", {}).get("content", "")

        if schema:
            parsed = _parse_schema(output, schema)
            if parsed:
                return HarnessResult(parsed=parsed, raw=output)
            else:
                return HarnessResult(
                    is_error=True,
                    error_message=f"Failed to parse Ollama output as {schema.__name__}",
                    raw=output,
                )

        return HarnessResult(raw=output)

    except Exception as e:
        return HarnessResult(
            is_error=True,
            error_message=f"Ollama error: {e}",
        )


def _parse_schema(text: str, schema: type[BaseModel]) -> BaseModel | None:
    """Extract and parse JSON from LLM output into a Pydantic model."""
    # Try direct parse
    try:
        return schema.model_validate_json(text)
    except Exception:
        pass

    # Try extracting from markdown code block
    import re
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_match:
        try:
            return schema.model_validate_json(json_match.group(1))
        except Exception:
            pass

    # Try finding first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return schema.model_validate_json(text[start:end + 1])
        except Exception:
            pass

    return None
