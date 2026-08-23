"""LLM Router - tier-routed inference (realizes 02.3.8 and 02.8.5, 21B 20).

The third module of the Integration Platform, and the only one of the three
that is **not** CIR-001 blocked: it is an internal abstraction over model
tiering, not a governed external relationship.

The ten-stage prompt pipeline of 02.8.5 is fixed in order, and the order is
enforced rather than documented: sanitization precedes rendering, the budget
check precedes invocation, and grounding validation precedes cache storage.
"""

from llm_router.adapters import CostManagerBudget, MemoryGatewayContext
from llm_router.pipeline import (
    INJECTION_PATTERNS,
    ContextItem,
    GroundingFailure,
    GroundingValidator,
    InferenceRequest,
    InferenceResult,
    ModelTier,
    PipelineOrderViolation,
    PipelineStage,
    PromptTemplate,
    ResponseCache,
    Sanitizer,
    TierUnavailable,
    TokenBudgetExceeded,
    estimate_tokens,
)
from llm_router.router import (
    FAILOVER_CHAIN,
    BudgetSource,
    ContextSource,
    LLMRouter,
    ModelBackend,
    PipelineTrace,
)

__all__ = [
    "LLMRouter",
    "ContextSource",
    "BudgetSource",
    "ModelBackend",
    "PipelineTrace",
    "FAILOVER_CHAIN",
    "ModelTier",
    "PipelineStage",
    "PipelineOrderViolation",
    "PromptTemplate",
    "ContextItem",
    "InferenceRequest",
    "InferenceResult",
    "Sanitizer",
    "INJECTION_PATTERNS",
    "GroundingValidator",
    "GroundingFailure",
    "ResponseCache",
    "TokenBudgetExceeded",
    "TierUnavailable",
    "estimate_tokens",
    "MemoryGatewayContext",
    "CostManagerBudget",
]
