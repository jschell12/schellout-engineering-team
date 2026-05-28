"""Prompt builder for the Issue Advisor agent role.

The Issue Advisor is the MIDDLE loop: when the inner coding loop fails,
it analyzes why and decides how to adapt (modify ACs, change approach,
split, accept with debt, or escalate to the outer replanner).
"""

from __future__ import annotations

from swe_af.execution.schemas import WorkspaceManifest
from swe_af.hitl.ask_user import format_prior_user_responses
from swe_af.prompts._utils import workspace_context_block

SYSTEM_PROMPT = """\
You are a senior technical lead analyzing a failed coding attempt in an
autonomous software engineering pipeline. An inner coding loop (coder → QA →
reviewer → synthesizer) has exhausted its iterations and the issue is not yet
complete. Your job is to decide the best recovery action.

## Design Principle

**Never skip, never abort.** Always find a way forward — modify acceptance
criteria, change approach, split issues, accept with tracked debt. Every
compromise is recorded. The final output is a completed repo + debt register.

## Actions (ordered least → most disruptive)

1. **RETRY_APPROACH** — The ACs are achievable but the coder took the wrong
   path. Provide a concrete alternative strategy. Same acceptance criteria,
   different implementation.

2. **RETRY_MODIFIED** — Some ACs are too strict or impossible given the
   environment. Relax or drop specific criteria while preserving the issue's
   core intent. Dropped criteria become technical debt.

3. **ACCEPT_WITH_DEBT** — The code written so far is "good enough" — it
   implements the core functionality even if some criteria aren't met. Record
   exactly what's missing as debt items. Use when the gap is cosmetic, the
   remaining criteria are nice-to-have, or further iteration is unlikely to
   improve things.

4. **SPLIT** — The issue is too large or has conflicting concerns. Break it
   into smaller, independently testable sub-issues. Each sub-issue must be
   self-contained. **Never split an issue that has already been split (depth
   >= 2) — use ACCEPT_WITH_DEBT instead.**

5. **ESCALATE_TO_REPLAN** — The failure reveals a fundamental problem with the
   DAG structure (wrong dependencies, missing prerequisite, architectural
   issue). The outer replanner needs to restructure. Use sparingly — this is
   the most disruptive option.

## Decision Framework

For each failure, evaluate in order:

1. **Read the iteration history.** Was the coder making progress? If the last
   iteration was close to passing, RETRY_APPROACH with specific guidance.
2. **Read the error/rejection details.** Is the failure in the ACs or the code?
   - AC issue → RETRY_MODIFIED (relax the problematic criterion)
   - Code issue → RETRY_APPROACH (different strategy)
3. **Inspect the worktree.** Is there substantial useful code already written?
   If yes and only minor criteria fail, ACCEPT_WITH_DEBT.
4. **Check scope.** Is the issue trying to do too many things? SPLIT it.
5. **Check dependencies.** Is the failure caused by missing upstream work?
   ESCALATE_TO_REPLAN.

## Scarcity Awareness

You have a limited budget of advisor invocations per issue. Consider how many
remain — if this is the last invocation, prefer ACCEPT_WITH_DEBT over RETRY
to avoid an unrecoverable failure.

## Output

Return a JSON object conforming to the IssueAdvisorDecision schema. Be precise:
- For RETRY_MODIFIED: list the FULL modified acceptance criteria (not just changes)
- For RETRY_APPROACH: describe the alternative approach concretely
- For SPLIT: each sub-issue must have name, title, description, acceptance_criteria
- For ACCEPT_WITH_DEBT: list exactly what functionality is missing
- For ESCALATE_TO_REPLAN: explain the structural problem and suggest restructuring

## Tools Available

You have read-only access to the codebase:
- READ files to inspect source code and the worktree
- GLOB to find files by pattern
- GREP to search for patterns
- BASH for read-only commands (ls, git log, git diff, test runs, etc.)

## Asking the User for Clarification (`ask_user_form`)

When you genuinely cannot judge between two valid actions, emit
``ask_user_form`` alongside your best-guess action. The orchestrator pauses
the ENTIRE workflow on the control plane, shows the user a form, and
re-invokes you once they submit. Their answers arrive in
``prior_user_responses`` on the next call.

When to ask:
- Choosing between RETRY_MODIFIED and ACCEPT_WITH_DEBT and the trade-off
  hinges on the user's risk tolerance.
- Multiple acceptance criteria are failing and you don't know which ones the
  user considers acceptable as debt.
- Considering ESCALATE_TO_REPLAN but unsure whether the user wants to keep
  iterating at all.

When NOT to ask:
- The right action is obvious from the failure context.
- ``prior_user_responses`` already covers this question — USE the existing
  answer, do not re-ask.
- You're just looking for confirmation. Bias toward deciding.

Pausing stops the build until the human responds (potentially hours/days).
Be parsimonious. Each ask should genuinely change the decision.

Form construction (when used):
- ``title``: one-sentence question, plain English.
- ``description`` (optional): brief context for why you're asking.
- ``fields``: typically ONE radio or select field with 2-3 concrete options
  matching your candidate actions.
- Leave ``ask_user_form`` as ``null`` (default) when you can decide on your own.\
"""


def issue_advisor_task_prompt(
    issue: dict,
    original_issue: dict,
    failure_result: dict,
    iteration_history: list[dict],
    dag_state_summary: dict,
    advisor_invocation: int = 1,
    max_advisor_invocations: int = 2,
    previous_adaptations: list[dict] | None = None,
    worktree_path: str = "",
    workspace_manifest: WorkspaceManifest | None = None,
    prior_user_responses: list[dict] | None = None,
) -> str:
    """Build the task prompt for the Issue Advisor agent.

    Args:
        issue: Current issue dict (may have modified ACs from previous advisor round).
        original_issue: The original issue dict before any modifications.
        failure_result: The IssueResult dict from the failed coding loop.
        iteration_history: List of iteration summaries from the coding loop.
        dag_state_summary: Abbreviated DAG state for context.
        advisor_invocation: Which advisor invocation this is (1-based).
        max_advisor_invocations: Total budget.
        previous_adaptations: Any adaptations made in prior advisor rounds.
        worktree_path: Path to the issue's git worktree.
        workspace_manifest: Optional multi-repo workspace manifest.
    """
    sections: list[str] = []

    # Inject multi-repo workspace context if present
    ws_block = workspace_context_block(workspace_manifest)
    if ws_block:
        sections.append(ws_block)

    prior_block = format_prior_user_responses(prior_user_responses)
    if prior_block:
        sections.append(prior_block)

    # Budget awareness
    remaining = max_advisor_invocations - advisor_invocation
    sections.append(f"## Budget: Invocation {advisor_invocation}/{max_advisor_invocations} ({remaining} remaining)")
    if remaining == 0:
        sections.append(
            "**This is your LAST invocation.** If you choose RETRY, the coding loop "
            "will run once more. If it fails again, the issue becomes FAILED_UNRECOVERABLE "
            "with no further advisor help. Consider ACCEPT_WITH_DEBT if the code is close."
        )

    # Current issue
    sections.append("\n## Current Issue")
    sections.append(f"- **Name**: {issue.get('name', '?')}")
    sections.append(f"- **Title**: {issue.get('title', '?')}")
    sections.append(f"- **Description**: {issue.get('description', '(not available)')}")
    ac = issue.get("acceptance_criteria", [])
    if ac:
        sections.append("- **Acceptance Criteria**:")
        sections.extend(f"  - {c}" for c in ac)
    deps = issue.get("depends_on", [])
    if deps:
        sections.append(f"- **Dependencies**: {deps}")
    provides = issue.get("provides", [])
    if provides:
        sections.append(f"- **Provides**: {provides}")

    # Original issue (if different)
    orig_ac = original_issue.get("acceptance_criteria", [])
    if orig_ac != ac:
        sections.append("\n## Original Acceptance Criteria (before modifications)")
        sections.extend(f"  - {c}" for c in orig_ac)

    # Worktree path
    if worktree_path:
        sections.append(f"\n## Worktree Path\n`{worktree_path}`")
        sections.append("Inspect this directory to see the current state of the code.")

    # Failure details
    sections.append("\n## Failure Result")
    sections.append(f"- **Outcome**: {failure_result.get('outcome', '?')}")
    sections.append(f"- **Error**: {failure_result.get('error_message', '(none)')}")
    sections.append(f"- **Attempts**: {failure_result.get('attempts', '?')}")
    sections.append(f"- **Files changed**: {failure_result.get('files_changed', [])}")
    if failure_result.get("error_context"):
        sections.append(f"\n**Error context**:\n```\n{failure_result['error_context'][:2000]}\n```")

    # Iteration history
    if iteration_history:
        sections.append("\n## Iteration History")
        for entry in iteration_history:
            sections.append(
                f"- Iter {entry.get('iteration', '?')}: action={entry.get('action', '?')}, "
                f"QA={'PASS' if entry.get('qa_passed') else 'FAIL'}, "
                f"Review={'APPROVED' if entry.get('review_approved') else 'REJECTED'}"
                f"{' [BLOCKING]' if entry.get('review_blocking') else ''}"
                f" — {entry.get('summary', '')[:150]}"
            )

    # Previous adaptations
    if previous_adaptations:
        sections.append("\n## Previous Adaptations (DO NOT REPEAT)")
        for adapt in previous_adaptations:
            sections.append(
                f"- **{adapt.get('adaptation_type', '?')}**: {adapt.get('rationale', '')}"
            )
            if adapt.get("dropped_criteria"):
                sections.append(f"  Dropped: {adapt['dropped_criteria']}")

    # DAG context (abbreviated)
    if dag_state_summary:
        sections.append("\n## DAG Context")
        completed = dag_state_summary.get("completed_issues", [])
        if completed:
            sections.append(f"- Completed issues: {[c.get('issue_name', '?') for c in completed]}")
        failed = dag_state_summary.get("failed_issues", [])
        if failed:
            sections.append(f"- Failed issues: {[f.get('issue_name', '?') for f in failed]}")
        sections.append(f"- PRD summary: {dag_state_summary.get('prd_summary', '(not available)')[:300]}")

        # Reference paths
        if dag_state_summary.get("prd_path"):
            sections.append(f"- PRD: `{dag_state_summary['prd_path']}`")
        if dag_state_summary.get("architecture_path"):
            sections.append(f"- Architecture: `{dag_state_summary['architecture_path']}`")
        if dag_state_summary.get("issues_dir"):
            sections.append(f"- Issues: `{dag_state_summary['issues_dir']}`")

    # Split depth guard
    if issue.get("parent_issue_name"):
        sections.append(
            "\n## Split Depth Warning\n"
            f"This issue was already split from '{issue['parent_issue_name']}'. "
            "**Do NOT choose SPLIT again** — use ACCEPT_WITH_DEBT instead to prevent "
            "infinite recursion."
        )

    # Instructions
    sections.append(
        "\n## Your Task\n"
        "1. Read the iteration history and failure details above.\n"
        "2. Inspect the worktree to see the current state of the code.\n"
        "3. Diagnose why the coding loop failed.\n"
        "4. Choose the least disruptive action that moves the project forward.\n"
        "5. Return an IssueAdvisorDecision JSON object."
    )

    return "\n".join(sections)
