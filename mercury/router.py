"""Dual-brain router for Mercury.

Each turn is classified by a tiny regex heuristic, then a brain is
picked using:

  1. The user's `/brain copilot|gemma|auto` override, if set on the
     session.
  2. Cortex's GPU state — if TRIBE is hot, Gemma is removed from the
     candidate set entirely (we won't load Gemma E4B while TRIBE owns
     the 5090's VRAM).
  3. Intent classification — quick/vision turns prefer Gemma, code/plan
     turns prefer Copilot, cortex turns route through the bridge.
  4. Default to GPT-5 mini for everything else.

The router doesn't make API calls itself; it just returns a
ModelDescriptor that the AIAgent can use to populate its provider
config.
"""
from __future__ import annotations

import enum
import logging
import re

from mercury import copilot_models as cm
from mercury import cortex_bridge

logger = logging.getLogger(__name__)


class Intent(enum.Enum):
    QUICK = "quick"        # short reply: timer, weather, fact lookup
    VISION = "vision"      # image / screenshot analysis
    CORTEX = "cortex"      # brain scan or narration request
    CODE = "code"          # write / edit / debug code
    PLAN = "plan"          # multi-step planning, research, long context


class BrainPreference(enum.Enum):
    AUTO = "auto"
    COPILOT = "copilot"
    GEMMA = "gemma"
    ESCALATE = "escalate"  # 1x premium tier


_VISION_PAT = re.compile(
    r"\b(image|photo|picture|screenshot|describe.*(this|that|the).*(image|video|photo))\b",
    re.IGNORECASE,
)
_CORTEX_PAT = re.compile(
    r"\b(brain[\s_-]?scan|cortex|tribe|fmri|narrat\w*|cortical|bold)\b",
    re.IGNORECASE,
)
_CODE_PAT = re.compile(
    r"```|\b(write|fix|debug|refactor|implement|test|build|deploy|"
    r"function|class|module|stack ?trace|bug|error)\b",
    re.IGNORECASE,
)
_PLAN_PAT = re.compile(
    r"\b(plan|design|architect|research|compare|spec|breakdown|"
    r"roadmap|milestone|investigate)\b",
    re.IGNORECASE,
)
_QUICK_PAT = re.compile(
    r"^\s*(timer|remind|weather|stock|joke|hi|hello|hey|thanks?|ok|yes|no|"
    r"what time|what'?s the date|wake me|set alarm)\b",
    re.IGNORECASE,
)


def classify_turn(message: str) -> Intent:
    msg = (message or "").strip()
    if _CORTEX_PAT.search(msg):
        return Intent.CORTEX
    if _VISION_PAT.search(msg):
        return Intent.VISION
    if _CODE_PAT.search(msg):
        return Intent.CODE
    if _PLAN_PAT.search(msg):
        return Intent.PLAN
    if _QUICK_PAT.search(msg) or len(msg) < 64:
        return Intent.QUICK
    return Intent.PLAN


def _gemma_eligible() -> bool:
    """Gemma E4B is unsafe to load while Cortex's TRIBE pipeline holds the GPU."""
    return not cortex_bridge.tribe_running()


def pick_brain(
    message: str,
    *,
    preference: BrainPreference = BrainPreference.AUTO,
    cortex_pure: bool = True,
) -> cm.ModelDescriptor:
    """Pick the model for this turn.

    `cortex_pure=True` (default) forces all Cortex-tagged turns to Gemma,
    matching the Cortex CLAUDE.md invariant that narration tier 0–2 must
    not touch a closed-source provider.  Set False if the user opts in to
    Copilot for Cortex turns at the Mercury level.
    """
    intent = classify_turn(message)

    if preference == BrainPreference.GEMMA and _gemma_eligible():
        return cm.GEMMA_E4B
    if preference == BrainPreference.COPILOT:
        return cm.DEFAULT_FULLTIME_BRAIN
    if preference == BrainPreference.ESCALATE:
        return cm.DEFAULT_REASONING_ESCALATION

    if intent == Intent.CORTEX:
        if cortex_pure and _gemma_eligible():
            return cm.GEMMA_E4B
        return cm.DEFAULT_FULLTIME_BRAIN

    if intent == Intent.VISION:
        if _gemma_eligible():
            return cm.GEMMA_E4B
        return cm.DEFAULT_VISION_BRAIN

    if intent == Intent.QUICK and _gemma_eligible():
        return cm.GEMMA_E4B

    if intent == Intent.CODE:
        return cm.DEFAULT_FULLTIME_BRAIN

    return cm.DEFAULT_FULLTIME_BRAIN


def explain(message: str, choice: cm.ModelDescriptor) -> str:
    """Human-readable rationale string for /brain status and the WebUI."""
    return (
        f"intent={classify_turn(message).value} "
        f"gpu={cortex_bridge.cortex_state()} "
        f"-> {choice.provider}/{choice.model_id} "
        f"(multiplier={choice.multiplier})"
    )
