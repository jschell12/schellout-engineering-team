"""Structured output schema for ``run_environment_scout``.

The scout is a two-pass reasoner driven by ``run_with_ask_user``:

* Pass 1 (no ``prior_user_responses``): scan the repo, populate
  ``detected_services`` and ``ask_user_form`` with one optional text field
  per service. ``scoped_credentials`` stays empty.
* Pass 2 (after the user submits): take the values from
  ``prior_user_responses[-1]['values']`` and surface them as
  ``scoped_credentials``. ``ask_user_form`` is cleared.

If no services are detected on pass 1, the scout returns
``ask_user_form=None`` immediately and the wrapper short-circuits — no pause,
no second pass.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from swe_af.hitl.ask_user import AskUserForm
from swe_af.hitl.services import ServiceCredentialSpec


class ScoutResult(BaseModel):
    """Structured output the scout LLM emits."""

    detected_services: list[ServiceCredentialSpec] = Field(
        default_factory=list,
        description=(
            "Third-party services the scout believes the PRD work touches. "
            "On pass 1 this matches the form's fields one-for-one."
        ),
    )
    scoped_credentials: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Populated on pass 2 ONLY. Keys are env var names (matching "
            "ServiceCredentialSpec.env_var_name); values are the secrets the "
            "user provided. Must NOT be logged or persisted."
        ),
    )
    skipped_services: list[str] = Field(
        default_factory=list,
        description=(
            "Env var names the user explicitly left blank (informed opt-out). "
            "Surfaced so downstream code can warn early if a critical "
            "credential is missing."
        ),
    )
    summary: str = Field(
        default="",
        description=(
            "One-line summary the scout writes — e.g. 'Negotiated 2 "
            "credentials: RAILWAY_TOKEN, SENTRY_AUTH_TOKEN. User skipped: "
            "DATADOG_API_KEY.' Safe to log; never includes secret values."
        ),
    )
    ask_user_form: AskUserForm | None = None
