"""Decision Gateway — the constitutional checkpoint (realizes document 11, 21B §18).

`11.2.4`: "An agent proposes; the Decision subsystem evaluates... Agency is
capacity; Decision is permission."

Built at Stage S5 because no Class A-D commitment can be recorded, verified or
reversed until it exists — and 12 rule 2, 17 rule 2 and 18 rule 2 each require
a committed decision record before any external effect may occur.
"""

from decision_gateway.adapters import (
    CostManagerBudgetSource,
    KnowledgeGatewayEvidenceSource,
    SecurityGatewayDecisionAuthorizer,
)
from decision_gateway.decisions import (
    CLASS_COST_CEILING,
    DECISION_TRANSITIONS,
    JOURNAL_RETENTION,
    STANDING_ORDER_MAX_DURATION,
    ApprovalRequest,
    Decision,
    DecisionClass,
    DecisionRecord,
    DecisionState,
    EvidenceRef,
    EvidentiaryBurden,
    Option,
    Proposal,
    RiskAssessment,
    Scope,
    StandingOrder,
    Urgency,
)
from decision_gateway.gateway import (
    REVERSAL_WINDOW,
    AuthorityExceeded,
    BudgetSource,
    DecisionAuthorizer,
    DecisionGateway,
    KnowledgeSource,
    SelfApprovalError,
)
from decision_gateway.pipeline import (
    ApprovalOrchestrator,
    Classifier,
    CompensationVerifier,
    ConfidenceEngine,
    EvaluationEngine,
    EvidenceAssembler,
    OptionValidator,
    PortfolioCircuitBreaker,
    ProposalRejected,
    RiskAssessor,
    StandingOrderManager,
    StandingOrderViolation,
)

__all__ = [
    "DecisionGateway",
    "DecisionAuthorizer",
    "KnowledgeSource",
    "BudgetSource",
    "AuthorityExceeded",
    "SelfApprovalError",
    "REVERSAL_WINDOW",
    "Decision",
    "DecisionRecord",
    "DecisionClass",
    "DecisionState",
    "DECISION_TRANSITIONS",
    "Proposal",
    "Option",
    "EvidenceRef",
    "EvidentiaryBurden",
    "RiskAssessment",
    "Scope",
    "Urgency",
    "StandingOrder",
    "ApprovalRequest",
    "CLASS_COST_CEILING",
    "STANDING_ORDER_MAX_DURATION",
    "JOURNAL_RETENTION",
    "Classifier",
    "OptionValidator",
    "EvidenceAssembler",
    "EvaluationEngine",
    "ConfidenceEngine",
    "RiskAssessor",
    "ApprovalOrchestrator",
    "StandingOrderManager",
    "StandingOrderViolation",
    "CompensationVerifier",
    "PortfolioCircuitBreaker",
    "ProposalRejected",
    "SecurityGatewayDecisionAuthorizer",
    "KnowledgeGatewayEvidenceSource",
    "CostManagerBudgetSource",
]
