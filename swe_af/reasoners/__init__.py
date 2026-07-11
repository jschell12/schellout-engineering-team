from swe_af.local_agent import LocalRouter
from swe_af.harness import invoke_persona

router = LocalRouter(tags=["swe-planner"])

# Make invoke_persona available as router.harness for compatibility
router.harness = invoke_persona

from . import execution_agents  # noqa: E402, F401 — registers execution reasoners
from . import pipeline  # noqa: E402, F401 — registers planning reasoners

__all__ = ["router"]
