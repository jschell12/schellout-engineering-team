"""Regression tests for structured ``router.ai()`` result handling."""

from __future__ import annotations

from types import SimpleNamespace

from swe_af.execution.schemas import IssueComplexityGate
from swe_af.reasoners.execution_agents import _extract_ai_parsed


def test_extract_ai_parsed_accepts_wrapper_result():
    parsed = IssueComplexityGate(
        complexity="standard",
        needs_qa=True,
        confident=True,
    )

    assert _extract_ai_parsed(SimpleNamespace(parsed=parsed)) is parsed


def test_extract_ai_parsed_accepts_direct_model_result():
    parsed = IssueComplexityGate(
        complexity="standard",
        needs_qa=False,
        confident=False,
    )

    assert _extract_ai_parsed(parsed) is parsed


def test_extract_ai_parsed_preserves_none_from_wrapper():
    assert _extract_ai_parsed(SimpleNamespace(parsed=None)) is None
