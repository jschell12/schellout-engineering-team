"""HITL (human-in-the-loop) primitives layered on the Hax SDK."""

from swe_af.hitl.ask_user import (
    AskUserForm,
    AskUserFormField,
    AskUserResponse,
    approval_webhook_url,
    build_form_builder,
    build_hax_client_from_env,
    format_prior_user_responses,
    request_user_input_and_pause,
)
from swe_af.hitl.credentials_store import (
    clear_scoped_credentials,
    get_scoped_credentials,
    inject_credentials_into_env,
    store_scoped_credentials,
)
from swe_af.hitl.scout_schema import ScoutResult
from swe_af.hitl.services import (
    KNOWN_SERVICES,
    ServiceCredentialSpec,
    detect_services_from_repo,
    known_service_summary_for_prompt,
)
from swe_af.hitl.wrapper import AskUserBudget, run_with_ask_user

__all__ = [
    "AskUserForm",
    "AskUserFormField",
    "AskUserResponse",
    "AskUserBudget",
    "KNOWN_SERVICES",
    "ScoutResult",
    "ServiceCredentialSpec",
    "approval_webhook_url",
    "build_form_builder",
    "build_hax_client_from_env",
    "clear_scoped_credentials",
    "detect_services_from_repo",
    "format_prior_user_responses",
    "get_scoped_credentials",
    "inject_credentials_into_env",
    "known_service_summary_for_prompt",
    "request_user_input_and_pause",
    "run_with_ask_user",
    "store_scoped_credentials",
]
