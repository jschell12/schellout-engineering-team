"""Knowledge base of common third-party services + how to mint a scoped token.

Used by ``run_environment_scout`` to recognize signal files in a repo (e.g.
``railway.toml``, ``fly.toml``, ``sentry.properties``) and ask the user for
the matching scoped credential. The LLM inside the scout reasoner consumes
``KNOWN_SERVICES`` as a hint list; ``detect_services_from_repo`` provides a
deterministic pre-pass that the LLM can build on.
"""

from __future__ import annotations

import os
from typing import Iterable

from pydantic import BaseModel, Field


class ServiceCredentialSpec(BaseModel):
    """One row in the knowledge base; also returned by the scout."""

    service_name: str = Field(description="Human-readable service name shown to the user.")
    env_var_name: str = Field(
        description=(
            "Env var the build expects (becomes the ask_user_form field id). "
            "Match what the service's CLI / SDK looks for by default."
        )
    )
    mint_url: str = Field(
        description=(
            "URL where the user mints a scoped/temporary token. Surfaced in "
            "the form description so the user can click through and paste back."
        )
    )
    permissions_hint: str = Field(
        description=(
            "Short hint on what scope / TTL to request when minting. Shown to "
            "the user in the form so they don't over-grant access."
        )
    )
    signal_files: list[str] = Field(
        default_factory=list,
        description=(
            "Glob-ish filenames whose presence in the repo strongly implies "
            "this service is in use. Used by detect_services_from_repo."
        ),
    )
    evidence_template: str = Field(
        default="",
        description=(
            "Sentence template explaining WHY the build needs this credential, "
            "used in the form description. Use {{signal}} as the placeholder."
        ),
    )


KNOWN_SERVICES: list[ServiceCredentialSpec] = [
    ServiceCredentialSpec(
        service_name="Railway",
        env_var_name="RAILWAY_TOKEN",
        mint_url="https://railway.com/account/tokens",
        permissions_hint="Project token, read-only if possible, set expiry to 1 day.",
        signal_files=["railway.toml", "railway.json", ".railway/config.json"],
        evidence_template="Saw {signal} — build likely needs Railway access to deploy or query services.",
    ),
    ServiceCredentialSpec(
        service_name="Fly.io",
        env_var_name="FLY_API_TOKEN",
        mint_url="https://fly.io/user/personal_access_tokens",
        permissions_hint="Deploy token scoped to this app, 1-day expiry.",
        signal_files=["fly.toml", "fly.io.toml", ".fly/config.toml"],
        evidence_template="Saw {signal} — build may need Fly.io access for deploys.",
    ),
    ServiceCredentialSpec(
        service_name="Vercel",
        env_var_name="VERCEL_TOKEN",
        mint_url="https://vercel.com/account/tokens",
        permissions_hint="Scope to this team only, 1-day expiry.",
        signal_files=["vercel.json", ".vercel/project.json"],
        evidence_template="Saw {signal} — build may need Vercel access.",
    ),
    ServiceCredentialSpec(
        service_name="Supabase",
        env_var_name="SUPABASE_ACCESS_TOKEN",
        mint_url="https://supabase.com/dashboard/account/tokens",
        permissions_hint="Personal access token, 1-day expiry — required only if migrations or schema changes are part of the work.",
        signal_files=["supabase/config.toml", "supabase/.gitignore", "supabase/migrations"],
        evidence_template="Saw {signal} — Supabase project detected.",
    ),
    ServiceCredentialSpec(
        service_name="Sentry",
        env_var_name="SENTRY_AUTH_TOKEN",
        mint_url="https://sentry.io/settings/account/api/auth-tokens/",
        permissions_hint="Auth token scoped to project:read + project:releases, 1-day expiry.",
        signal_files=["sentry.properties", ".sentryclirc", "sentry.io.json"],
        evidence_template="Saw {signal} — Sentry integration detected.",
    ),
    ServiceCredentialSpec(
        service_name="Datadog",
        env_var_name="DATADOG_API_KEY",
        mint_url="https://app.datadoghq.com/organization-settings/api-keys",
        permissions_hint="Application API key (NOT a client token), restricted to read scopes if possible.",
        signal_files=["datadog.yaml", ".datadog/conf.yaml"],
        evidence_template="Saw {signal} — Datadog integration detected.",
    ),
    ServiceCredentialSpec(
        service_name="GitHub",
        env_var_name="GH_TOKEN",
        mint_url="https://github.com/settings/personal-access-tokens/new",
        permissions_hint="Fine-grained PAT scoped to THIS repo only, repo:contents+pull-requests, 1-day expiry.",
        signal_files=[".github/workflows", "CODEOWNERS"],
        evidence_template="Saw {signal} — work likely needs GitHub API beyond what gh CLI provides anonymously.",
    ),
    ServiceCredentialSpec(
        service_name="OpenAI",
        env_var_name="OPENAI_API_KEY",
        mint_url="https://platform.openai.com/api-keys",
        permissions_hint="Restricted API key with low usage cap; 1-day expiry.",
        signal_files=[],  # Detected via dependency manifests, not signal files.
        evidence_template="Project depends on the OpenAI SDK.",
    ),
    ServiceCredentialSpec(
        service_name="Anthropic",
        env_var_name="ANTHROPIC_API_KEY",
        mint_url="https://console.anthropic.com/settings/keys",
        permissions_hint="Restricted API key, set monthly spend limit, 1-day expiry.",
        signal_files=[],
        evidence_template="Project depends on the Anthropic SDK.",
    ),
]


def detect_services_from_repo(repo_path: str) -> list[ServiceCredentialSpec]:
    """Deterministic pre-pass: look for ``signal_files`` under ``repo_path``.

    Returns the subset of ``KNOWN_SERVICES`` whose signal files exist on disk.
    This is a hint to the LLM scout — the final decision on which credentials
    to ask for stays with the scout, which can incorporate PRD context the
    static scan can't see.

    Notes:
        * No recursive glob; checks each ``signal_file`` as a path under
          ``repo_path``. ``signal_file`` may be a file or a directory; both
          count as a hit.
        * Returns an empty list if ``repo_path`` doesn't exist (don't raise).
        * Order matches ``KNOWN_SERVICES`` so callers get stable output.
    """
    if not repo_path or not os.path.isdir(repo_path):
        return []
    hits: list[ServiceCredentialSpec] = []
    for spec in KNOWN_SERVICES:
        for signal in spec.signal_files:
            candidate = os.path.join(repo_path, signal)
            if os.path.exists(candidate):
                hits.append(spec)
                break
    return hits


def known_service_summary_for_prompt(specs: Iterable[ServiceCredentialSpec]) -> str:
    """Render a markdown bullet list of service specs for inclusion in a prompt."""
    lines: list[str] = []
    for spec in specs:
        signals = ", ".join(f"`{s}`" for s in spec.signal_files) or "(no static signal)"
        lines.append(
            f"- **{spec.service_name}** — env `{spec.env_var_name}`; "
            f"signals: {signals}; mint at {spec.mint_url}; "
            f"hint: {spec.permissions_hint}"
        )
    return "\n".join(lines)
