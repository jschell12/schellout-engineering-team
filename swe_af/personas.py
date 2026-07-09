"""Persona routing — maps SWE-AF roles to Matrix bridge personas.

Each persona has a backend (claude or ollama), a model, and a system prompt
prefix that gets injected before the role-specific prompt.
"""

import re
from dataclasses import dataclass, field


@dataclass
class Persona:
    name: str
    alias: str
    backend: str  # "claude" or "ollama"
    model: str | None  # None = Claude default, else Ollama model name
    system_prefix: str = ""


# SWE personas — must match bridge config in schellout
PERSONAS = {
    # Planning (Claude API — strong reasoning required)
    "spec": Persona(
        name="spec", alias="sophia", backend="claude", model=None,
        system_prefix="You are Spec (@spec), also known as Sophia — the product manager "
        "and software architect. You scope goals into clear PRDs, design system "
        "architecture, and decompose work into dependency-ordered issue DAGs. "
        "Be precise and structured.",
    ),

    # Coding (Claude API — needs tool use)
    "lux": Persona(
        name="lux", alias="lucia", backend="claude", model=None,
        system_prefix="You are Lux (@lux), also known as Lucia — a senior frontend "
        "engineer. You specialize in React, Vue, Svelte, native apps, CSS/Tailwind, "
        "design systems, and accessibility. Show code, not prose.",
    ),
    "nexus": Persona(
        name="nexus", alias="nolan", backend="claude", model=None,
        system_prefix="You are Nexus (@nexus), also known as Nolan — a senior backend "
        "engineer. You specialize in API design, database schemas, CI/CD, "
        "authentication, and system architecture. Think in data models and contracts.",
    ),
    "terra": Persona(
        name="terra", alias="tara", backend="claude", model=None,
        system_prefix="You are Terra (@terra), also known as Tara — a senior "
        "infrastructure engineer. You specialize in Terraform, Docker, Kubernetes, "
        "networking, Ansible, and Linux. Think in infrastructure as code.",
    ),

    # Review/QA (Ollama — free, high-volume)
    "audit": Persona(
        name="audit", alias="audra", backend="ollama", model="qwen2.5:72b",
        system_prefix="You are Audit (@audit), also known as Audra — a code reviewer "
        "and tech lead. You review diffs for correctness, security, performance, "
        "and adherence to conventions. Be direct — cite line numbers, not vibes.",
    ),
    "test": Persona(
        name="test", alias="tessa", backend="ollama", model="qwen2.5:72b",
        system_prefix="You are Test (@test), also known as Tessa — a QA engineer. "
        "You write unit tests, integration tests, validate coverage, and identify "
        "edge cases. Be thorough and methodical.",
    ),

    # Failure diagnosis (Claude API — needs strong reasoning)
    "triage": Persona(
        name="triage", alias="trevor", backend="claude", model=None,
        system_prefix="You are Triage (@triage), also known as Trevor — an issue "
        "advisor and build verifier. You diagnose why tasks fail, decide whether to "
        "retry/split/escalate, and verify acceptance criteria. Be analytical.",
    ),
}

# Role → persona mapping
ROLE_PERSONA_MAP = {
    # Planning roles → Spec
    "product_manager": "spec",
    "architect": "spec",
    "tech_lead": "spec",
    "sprint_planner": "spec",

    # Coding roles → domain-routed (see route_coder_persona)
    "coder": None,  # determined dynamically

    # Review/QA → Ollama personas
    "code_reviewer": "audit",
    "qa": "test",
    "qa_synthesizer": "audit",
    "integration_tester": "test",

    # Failure handling → Triage
    "retry_advisor": "triage",
    "issue_advisor": "triage",
    "replanner": "triage",
    "verifier": "triage",

    # Mechanical roles → no persona (use default Claude)
    "issue_writer": None,
    "git_init": None,
    "merger": None,
    "workspace_setup": None,
    "workspace_cleanup": None,
    "repo_finalize": None,
    "github_pr": None,
    "ci_watcher": None,
    "ci_fixer": None,
    "pr_resolver": None,
    "fix_generator": None,
    "environment_scout": None,
}

# File patterns for domain classification
FRONTEND_PATTERNS = [
    r"\.(tsx|jsx|vue|svelte|css|scss|less|html)$",
    r"(components|pages|views|layouts|hooks|styles|public)/",
    r"(tailwind|postcss|vite|next|nuxt|webpack)\.config",
    r"package\.json$",
]

INFRA_PATTERNS = [
    r"(Dockerfile|docker-compose|\.dockerignore)",
    r"\.(tf|tfvars|hcl)$",
    r"(\.github/workflows|\.gitlab-ci|Jenkinsfile|Makefile)",
    r"(k8s|kubernetes|helm|charts|nomad|ansible|terraform)/",
    r"(nginx|caddy|traefik)\.conf",
    r"(plist|launchd|systemd)/",
]


def classify_domain(issue: dict) -> str:
    """Classify an issue into frontend/backend/infra based on files it touches."""
    files = []
    files.extend(issue.get("files_to_create", []))
    files.extend(issue.get("files_to_modify", []))

    # Also check description for hints
    desc = (issue.get("description", "") + " " + issue.get("title", "")).lower()

    frontend_score = 0
    infra_score = 0
    backend_score = 0

    for f in files:
        f_str = f if isinstance(f, str) else str(f)
        matched = False
        for pattern in FRONTEND_PATTERNS:
            if re.search(pattern, f_str, re.IGNORECASE):
                frontend_score += 1
                matched = True
                break
        if not matched:
            for pattern in INFRA_PATTERNS:
                if re.search(pattern, f_str, re.IGNORECASE):
                    infra_score += 1
                    matched = True
                    break
        if not matched:
            backend_score += 1

    # Description-based hints
    for kw in ["ui", "frontend", "component", "css", "tailwind", "react", "vue"]:
        if kw in desc:
            frontend_score += 2
    for kw in ["docker", "terraform", "deploy", "ci/cd", "infra", "k8s", "ansible"]:
        if kw in desc:
            infra_score += 2

    if frontend_score > max(backend_score, infra_score):
        return "frontend"
    if infra_score > max(frontend_score, backend_score):
        return "infra"
    return "backend"


def route_coder_persona(issue: dict) -> str:
    """Route a coding task to the appropriate persona based on domain."""
    domain = classify_domain(issue)
    return {"frontend": "lux", "backend": "nexus", "infra": "terra"}[domain]


def get_persona(role: str, issue: dict | None = None) -> Persona | None:
    """Get the persona for a given SWE-AF role, optionally with issue context for coder routing."""
    persona_name = ROLE_PERSONA_MAP.get(role)

    if role == "coder" and issue is not None:
        persona_name = route_coder_persona(issue)
    elif persona_name is None:
        return None

    return PERSONAS.get(persona_name)
