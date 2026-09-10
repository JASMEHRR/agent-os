# Appendices A-E, G, H - the live registers

Generated from the code and the corpus by `tests/conformance/registers.py`.
Do not edit by hand: `test_registers.py` regenerates and compares.

Appendix F, the Non-Violable Rule traceability matrix, is published
separately in `appendix_f_traceability.md`.

Four of these registers are **derived** and cannot be wrong about the code,
only incomplete if the derivation is. Three (C, G, H) are **declarations**,
and each is checked against the code: a module claiming a journal it does
not hold, or a CIR claimed resolved while the modules it blocks still
refuse, fails the suite. A declaration nothing checks is a wish.

## Appendix A - Module Register

28 modules, 0 construction-blocked by CIR-001.

| Module | Layer | Stage | Status | Source files | Tests |
|---|---|---|---|---|---|
| `core` | libs | S0 | implemented to stage exit criteria | 3 | 3 |
| `kernel` | libs | S0 | implemented to stage exit criteria | 9 | 46 |
| `persistence` | libs | S0 | implemented to stage exit criteria | 4 | 16 |
| `agent_runtime` | services | S7 | implemented to stage exit criteria | 3 | 45 |
| `api_gateway` | services | S8 | implemented to stage exit criteria | 6 | 44 |
| `content_agent` | services | A1 | implemented to stage exit criteria | 13 | 181 |
| `cost_manager` | services | S3 | implemented to stage exit criteria | 3 | 28 |
| `decision_gateway` | services | S5 | implemented to stage exit criteria | 4 | 62 |
| `deployment_gateway` | services | S11 | implemented to stage exit criteria | 1 | 0 |
| `deployment_registry` | services | S11 | implemented to stage exit criteria | 2 | 34 |
| `event_bus` | services | S2 | implemented to stage exit criteria | 11 | 61 |
| `evolution_gateway` | services | S12 | implemented to stage exit criteria | 1 | 31 |
| `governance_gateway` | services | S10 | implemented to stage exit criteria | 3 | 57 |
| `human_interface` | services | S8 | implemented to stage exit criteria | 5 | 50 |
| `integration_gateway` | services | S6 | implemented to stage exit criteria | 1 | 0 |
| `integration_registry` | services | S6 | implemented to stage exit criteria | 1 | 30 |
| `knowledge_gateway` | services | S4 | implemented to stage exit criteria | 5 | 48 |
| `learning_gateway` | services | S9 | implemented to stage exit criteria | 4 | 68 |
| `llm_router` | services | S6 | implemented to stage exit criteria | 4 | 38 |
| `memory_gateway` | services | S4 | implemented to stage exit criteria | 4 | 44 |
| `observability_gateway` | services | S3 (ingestion) + S10 (interpretive) | implemented to stage exit criteria | 4 | 54 |
| `plugin_manager` | services | S12 | implemented to stage exit criteria | 1 | 34 |
| `schema_registry` | services | S0 | implemented to stage exit criteria | 1 | 6 |
| `security_gateway` | services | S1 | implemented to stage exit criteria | 15 | 109 |
| `tool_executor` | services | S6 | implemented to stage exit criteria | 2 | 0 |
| `tool_gateway` | services | S6 | implemented to stage exit criteria | 3 | 0 |
| `tool_registry` | services | S6 | implemented to stage exit criteria | 3 | 29 |
| `workflow_engine` | services | S7 | implemented to stage exit criteria | 4 | 46 |

## Appendix B - Interface Register

366 public methods across 24 Gateway facades,
read by introspection so a rename cannot go unrecorded.

| Module | Facade | Method |
|---|---|---|
| `agent_runtime` | `AgentRuntime` | `assess_drift(self, agent_id: 'str') -> 'Any'` |
| `agent_runtime` | `AgentRuntime` | `command(self, token: 'str', agent_id: 'str', target: 'AgentState', reason: 'str' = '') -> 'AgentRecord'` |
| `agent_runtime` | `AgentRuntime` | `decay_reputation(self) -> 'list[AgentRecord]'` |
| `agent_runtime` | `AgentRuntime` | `discover(self, token: 'str', capability: 'str | None' = None, min_reputation: 'float' = 0.0) -> 'list[AgentRecord]'` |
| `agent_runtime` | `AgentRuntime` | `execute(self, token: 'str', request: 'ActivityRequest') -> 'ActivityOutcome'` |
| `agent_runtime` | `AgentRuntime` | `get(self, agent_id: 'str') -> 'AgentRecord'` |
| `agent_runtime` | `AgentRuntime` | `health(self) -> 'Mapping[str, Any]'` |
| `agent_runtime` | `AgentRuntime` | `health_of(self, agent_id: 'str') -> 'Mapping[str, Any]'` |
| `agent_runtime` | `AgentRuntime` | `now()` |
| `agent_runtime` | `AgentRuntime` | `outcome_for(self, activity_id: 'str') -> 'ActivityOutcome'` |
| `agent_runtime` | `AgentRuntime` | `register(self, token: 'str', manifest: 'AgentManifest') -> 'AgentRecord'` |
| `api_gateway` | `APIGateway` | `handle(self, request: 'Request') -> 'Response'` |
| `api_gateway` | `APIGateway` | `health(self) -> 'Mapping[str, Any]'` |
| `api_gateway` | `APIGateway` | `now()` |
| `api_gateway` | `APIGateway` | `register_route(self, route: 'Route') -> 'Route'` |
| `api_gateway` | `APIGateway` | `request_ids()` |
| `content_agent` | `ContentStudio` | `add_prospect(self, prospect: 'Prospect') -> 'Prospect'` |
| `content_agent` | `ContentStudio` | `approve(self, draft_id: 'str', principal_id: 'str') -> 'PostDraft'` |
| `content_agent` | `ContentStudio` | `approve_note(self, draft_id: 'str', principal_id: 'str') -> 'OutreachDraft'` |
| `content_agent` | `ContentStudio` | `awaiting_approval(self) -> 'list[PostDraft]'` |
| `content_agent` | `ContentStudio` | `capture(self, body: 'str', angle: 'str' = '') -> 'WeeklyNote'` |
| `content_agent` | `ContentStudio` | `check_in(self, said: 'str') -> 'tuple[str, list[dict[str, str]]]'` |
| `content_agent` | `ContentStudio` | `discard(self, draft_id: 'str') -> 'PostDraft'` |
| `content_agent` | `ContentStudio` | `draft(self, note: 'WeeklyNote', channel: 'Channel' = <Channel.LINKEDIN: 'linkedin'>) -> 'PostDraft'` |
| `content_agent` | `ContentStudio` | `draft_everywhere(self, note: 'WeeklyNote') -> 'list[PostDraft]'` |
| `content_agent` | `ContentStudio` | `draft_note(self, prospect: 'Prospect', channel: 'OutreachChannel' = <OutreachChannel.LINKEDIN_NOTE: 'linkedin_note'>) -> 'OutreachDraft'` |
| `content_agent` | `ContentStudio` | `health(self) -> 'dict[str, Any]'` |
| `content_agent` | `ContentStudio` | `latest_note(self) -> 'WeeklyNote | None'` |
| `content_agent` | `ContentStudio` | `needs_attention(self) -> 'list[PostDraft]'` |
| `content_agent` | `ContentStudio` | `note(self, note_id: 'str') -> 'WeeklyNote'` |
| `content_agent` | `ContentStudio` | `outreach_drafts(self) -> 'list[OutreachDraft]'` |
| `content_agent` | `ContentStudio` | `prospects(self) -> 'list[Prospect]'` |
| `content_agent` | `ContentStudio` | `record_posted(self, draft_id: 'str', principal_id: 'str', url: 'str' = '') -> 'PostDraft'` |
| `cost_manager` | `CostManager` | `allocate(self, scope: 'BudgetScope', tenant_id: 'str', limit: 'float') -> 'None'` |
| `cost_manager` | `CostManager` | `attribution(self, scope: 'BudgetScope | None' = None, principal_id: 'str | None' = None, tenant_id: 'str | None' = None) -> 'Mapping[str, Any]'` |
| `cost_manager` | `CostManager` | `check(self, scope: 'BudgetScope', tenant_id: 'str', estimated_cost: 'float' = 0.0, dependency: 'str | None' = None) -> 'BudgetVerdict'` |
| `cost_manager` | `CostManager` | `correct(self, entry: 'LedgerEntry', amount: 'float', reason: 'str') -> 'LedgerEntry'` |
| `cost_manager` | `CostManager` | `enforce(self, scope: 'BudgetScope', tenant_id: 'str', estimated_cost: 'float' = 0.0, dependency: 'str | None' = None) -> 'BudgetVerdict'` |
| `cost_manager` | `CostManager` | `health(self) -> 'Mapping[str, Any]'` |
| `cost_manager` | `CostManager` | `now()` |
| `cost_manager` | `CostManager` | `record(self, scope: 'BudgetScope', tenant_id: 'str', actual_cost: 'float', operation: 'str', principal_id: 'str', dependency: 'str | None' = None, succeeded: 'bool' = True) -> 'BudgetVerdict'` |
| `cost_manager` | `CostManager` | `reset(self, dependency: 'str', tenant_id: 'str') -> 'None'` |
| `cost_manager` | `CostManager` | `trip(self, dependency: 'str', tenant_id: 'str', reason: 'str') -> 'None'` |
| `decision_gateway` | `DecisionGateway` | `commit(self, decision_id: 'str', committer_id: 'str') -> 'DecisionRecord'` |
| `decision_gateway` | `DecisionGateway` | `get(self, decision_id: 'str') -> 'DecisionRecord'` |
| `decision_gateway` | `DecisionGateway` | `health(self) -> 'Mapping[str, Any]'` |
| `decision_gateway` | `DecisionGateway` | `manage_standing_order(self, operation: 'str', order_id: 'str', actor_id: 'str', tenant_id: 'str | None' = None, scope: 'set[str] | None' = None, budget_ceiling: 'float' = 0.0, max_risk: 'RiskClass' = <RiskClass.MODERATE: 'moderate'>, duration: 'timedelta | None' = None) -> 'StandingOrder'` |
| `decision_gateway` | `DecisionGateway` | `mark_executing(self, decision_id: 'str') -> 'DecisionRecord'` |
| `decision_gateway` | `DecisionGateway` | `now()` |
| `decision_gateway` | `DecisionGateway` | `override(self, decision_id: 'str', human_id: 'str', target: 'DecisionState', reason: 'str') -> 'DecisionRecord'` |
| `decision_gateway` | `DecisionGateway` | `panic(self) -> 'list[DecisionRecord]'` |
| `decision_gateway` | `DecisionGateway` | `pending_approval(self) -> 'list[ApprovalRequest]'` |
| `decision_gateway` | `DecisionGateway` | `propose(self, token: 'str', proposal: 'Proposal') -> 'DecisionRecord'` |
| `decision_gateway` | `DecisionGateway` | `query_journal(self, decision_id: 'str | None' = None, tenant_id: 'str | None' = None, action: 'str | None' = None) -> 'list[Mapping[str, Any]]'` |
| `decision_gateway` | `DecisionGateway` | `report_outcome(self, decision_id: 'str', actual_outcome: 'str') -> 'DecisionRecord'` |
| `decision_gateway` | `DecisionGateway` | `respond(self, request_id: 'str', responder_id: 'str', response: 'str') -> 'DecisionRecord'` |
| `decision_gateway` | `DecisionGateway` | `resume(self, human_id: 'str') -> 'None'` |
| `decision_gateway` | `DecisionGateway` | `reverse(self, decision_id: 'str', requester_id: 'str', reason: 'str') -> 'DecisionRecord'` |
| `decision_gateway` | `DecisionGateway` | `route_to_human(_kind, _detail)` |
| `decision_gateway` | `DecisionGateway` | `supersede(self, decision_id: 'str', successor_id: 'str', authorized_by: 'str') -> 'DecisionRecord'` |
| `decision_gateway` | `DecisionGateway` | `sweep_timeouts(self) -> 'list[DecisionRecord]'` |
| `decision_gateway` | `DecisionGateway` | `verify(self, decision_id: 'str', required_class: 'DecisionClass') -> 'DecisionRecord'` |
| `deployment_gateway` | `DeploymentGateway` | `blocker(self) -> 'str'` |
| `deployment_gateway` | `DeploymentGateway` | `deployment_status(self, deployment_id: 'str') -> 'Mapping[str, Any]'` |
| `deployment_gateway` | `DeploymentGateway` | `gates_for(self, risk_tier: 'RiskTier') -> 'tuple[str, ...]'` |
| `deployment_gateway` | `DeploymentGateway` | `halt(self) -> 'int'` |
| `deployment_gateway` | `DeploymentGateway` | `health(self) -> 'Mapping[str, Any]'` |
| `deployment_gateway` | `DeploymentGateway` | `is_blocked(self) -> 'bool'` |
| `deployment_gateway` | `DeploymentGateway` | `mediate_access(self, runtime_id: 'str', deployment_id: 'str') -> 'str'` |
| `deployment_gateway` | `DeploymentGateway` | `mediated_runtimes(self) -> 'Mapping[str, str]'` |
| `deployment_gateway` | `DeploymentGateway` | `migrate(self, runtime_id: 'str', to_deployment_id: 'str', is_human: 'bool') -> 'str'` |
| `deployment_gateway` | `DeploymentGateway` | `now()` |
| `deployment_gateway` | `DeploymentGateway` | `promotion_sequence(self) -> 'tuple[str, ...]'` |
| `deployment_gateway` | `DeploymentGateway` | `request_promotion(self, deployment_id: 'str', to_tier: 'RiskTier', approver_id: 'str', is_human: 'bool', e_class: 'EClass', rollback_tested: 'bool') -> 'PromotionOutcome'` |
| `deployment_gateway` | `DeploymentGateway` | `required_authority_for(self, risk_tier: 'RiskTier') -> 'EClass'` |
| `deployment_gateway` | `DeploymentGateway` | `rollback(self, deployment_id: 'str', reason: 'str') -> 'EnvironmentRecord'` |
| `deployment_gateway` | `DeploymentGateway` | `rollback_precedes_authorization(self) -> 'bool'` |
| `deployment_gateway` | `DeploymentGateway` | `terminate(self, deployment_id: 'str', reason: 'str', is_human: 'bool') -> 'EnvironmentRecord'` |
| `deployment_gateway` | `DeploymentGateway` | `verify_rollback_readiness(self, deployment_id: 'str', rollback_tested: 'bool') -> 'EnvironmentRecord'` |
| `deployment_registry` | `DeploymentRegistry` | `activate(self, deployment_id: 'str') -> 'EnvironmentRecord'` |
| `deployment_registry` | `DeploymentRegistry` | `active(self, tenant_id: 'str | None' = None) -> 'list[EnvironmentRecord]'` |
| `deployment_registry` | `DeploymentRegistry` | `approve(self, deployment_id: 'str', approver_id: 'str', is_human: 'bool', e_class: 'EClass') -> 'EnvironmentRecord'` |
| `deployment_registry` | `DeploymentRegistry` | `blocker(self) -> 'str'` |
| `deployment_registry` | `DeploymentRegistry` | `class_policy(self, risk_tier: 'RiskTier') -> 'Any'` |
| `deployment_registry` | `DeploymentRegistry` | `declare(self, manifest: 'EnvironmentManifest', actor_id: 'str') -> 'EnvironmentRecord'` |
| `deployment_registry` | `DeploymentRegistry` | `decommission(self, deployment_id: 'str', actor_id: 'str') -> 'EnvironmentRecord'` |
| `deployment_registry` | `DeploymentRegistry` | `discover(self, tenant_id: 'str', min_tier: 'RiskTier | None' = None, locality: 'str | None' = None, fault_domain: 'str | None' = None) -> 'list[EnvironmentRecord]'` |
| `deployment_registry` | `DeploymentRegistry` | `get(self, deployment_id: 'str') -> 'EnvironmentRecord'` |
| `deployment_registry` | `DeploymentRegistry` | `health(self) -> 'Mapping[str, Any]'` |
| `deployment_registry` | `DeploymentRegistry` | `is_blocked(self) -> 'bool'` |
| `deployment_registry` | `DeploymentRegistry` | `now()` |
| `deployment_registry` | `DeploymentRegistry` | `pass_gate(self, deployment_id: 'str', gate: 'str') -> 'EnvironmentRecord'` |
| `deployment_registry` | `DeploymentRegistry` | `promote(self, deployment_id: 'str', to_tier: 'RiskTier', approver_id: 'str', is_human: 'bool', e_class: 'EClass') -> 'EnvironmentRecord'` |
| `deployment_registry` | `DeploymentRegistry` | `quarantine(self, deployment_id: 'str', reason: 'str') -> 'EnvironmentRecord'` |
| `deployment_registry` | `DeploymentRegistry` | `record_observation(self, deployment_id: 'str', incident: 'bool' = False) -> 'EnvironmentRecord'` |
| `deployment_registry` | `DeploymentRegistry` | `validate(self, manifest: 'EnvironmentManifest') -> 'None'` |
| `deployment_registry` | `DeploymentRegistry` | `validate_environment(self, deployment_id: 'str') -> 'EnvironmentRecord'` |
| `event_bus` | `EventBus` | `acknowledge(self, group_id: 'str', event_id: 'str') -> 'DeliveryState'` |
| `event_bus` | `EventBus` | `consume(self, group_id: 'str', limit: 'int | None' = None) -> 'list[DeliveryState]'` |
| `event_bus` | `EventBus` | `emit(self, token: 'str', event_type: 'str', payload: 'dict[str, Any]', tenant_id: 'str', source: 'str', trace_id: 'str', causation_id: 'str | None' = None, schema_version: 'str' = '1.0.0', occurred_at: 'datetime | None' = None, business_context: 'dict[str, str] | None' = None) -> 'PublishedEvent'` |
| `event_bus` | `EventBus` | `health(self) -> 'Mapping[str, Any]'` |
| `event_bus` | `EventBus` | `lag_for(self, group_id: 'str') -> 'int'` |
| `event_bus` | `EventBus` | `now()` |
| `event_bus` | `EventBus` | `observe_backpressure(self) -> 'None'` |
| `event_bus` | `EventBus` | `query_dead_letters(self, group_id: 'str | None' = None, event_type: 'str | None' = None) -> 'list[DeadLetter]'` |
| `event_bus` | `EventBus` | `register_consumer_group(self, token: 'str', group_id: 'str', tenant_id: 'str', patterns: 'tuple[str, ...]', members: 'tuple[str, ...]', retry_policy: 'RetryPolicy | None' = None, critical: 'bool' = False) -> 'ConsumerGroup'` |
| `event_bus` | `EventBus` | `request_replay(self, token: 'str', mode: 'ReplayMode', requested_by: 'str', tenant_id: 'str', stream: 'str | None' = None, correlation_id: 'str | None' = None, limit: 'int | None' = None) -> 'ReplaySandbox'` |
| `event_bus` | `EventBus` | `signal_failure(self, group_id: 'str', event_id: 'str', reason: 'str') -> 'DeliveryState | DeadLetter'` |
| `evolution_gateway` | `EvolutionGateway` | `alert_human(detail)` |
| `evolution_gateway` | `EvolutionGateway` | `analyse_impact(self, proposal_id: 'str', assessment: 'ImpactAssessment') -> 'Proposal'` |
| `evolution_gateway` | `EvolutionGateway` | `blocker(self) -> 'str'` |
| `evolution_gateway` | `EvolutionGateway` | `check_recursion(self, proposal_id: 'str') -> 'Proposal'` |
| `evolution_gateway` | `EvolutionGateway` | `compensation_precedes_packaging(self) -> 'bool'` |
| `evolution_gateway` | `EvolutionGateway` | `consumes_learning_state(self, state: 'str') -> 'bool'` |
| `evolution_gateway` | `EvolutionGateway` | `draft(self, proposal_id: 'str', tenant_id: 'str', artifact_class: 'ArtifactClass', target_subsystem: 'str', statement: 'str', rationale: 'str', evidence: 'Sequence[LearningEvidence]', drafted_by: 'str') -> 'Proposal'` |
| `evolution_gateway` | `EvolutionGateway` | `escalate(trigger, detail)` |
| `evolution_gateway` | `EvolutionGateway` | `frame_compensation(self, proposal_id: 'str', plan: 'CompensationPlan') -> 'Proposal'` |
| `evolution_gateway` | `EvolutionGateway` | `get(self, proposal_id: 'str') -> 'Proposal'` |
| `evolution_gateway` | `EvolutionGateway` | `hand_off(self, proposal_id: 'str') -> 'str'` |
| `evolution_gateway` | `EvolutionGateway` | `health(self) -> 'Mapping[str, Any]'` |
| `evolution_gateway` | `EvolutionGateway` | `is_blocked(self) -> 'bool'` |
| `evolution_gateway` | `EvolutionGateway` | `monitor_signals(self, entries: 'Sequence[LearningEvidence]') -> 'list[LearningEvidence]'` |
| `evolution_gateway` | `EvolutionGateway` | `now()` |
| `evolution_gateway` | `EvolutionGateway` | `package(self, proposal_id: 'str') -> 'Mapping[str, Any]'` |
| `evolution_gateway` | `EvolutionGateway` | `pipeline(self) -> 'tuple[str, ...]'` |
| `evolution_gateway` | `EvolutionGateway` | `proposals(self, state: 'ProposalState | None' = None) -> 'list[Proposal]'` |
| `evolution_gateway` | `EvolutionGateway` | `record_outcome(self, proposal_id: 'str', outcome: 'str', justification: 'str' = '') -> 'Proposal'` |
| `evolution_gateway` | `EvolutionGateway` | `recursion_guard_precedes_packaging(self) -> 'bool'` |
| `evolution_gateway` | `EvolutionGateway` | `register_governance(self, intake: 'GovernanceIntake') -> 'None'` |
| `governance_gateway` | `GovernanceGateway` | `accountability_chain(self, scope: 'str') -> 'list[Stewardship]'` |
| `governance_gateway` | `GovernanceGateway` | `activate(self, artifact_id: 'str') -> 'ArtifactRecord'` |
| `governance_gateway` | `GovernanceGateway` | `activate_policy(self, policy_id: 'str') -> 'Policy'` |
| `governance_gateway` | `GovernanceGateway` | `active_exceptions(self) -> 'list[Exception_]'` |
| `governance_gateway` | `GovernanceGateway` | `alert_human(detail)` |
| `governance_gateway` | `GovernanceGateway` | `applicable_policies(self, tenant_id: 'str', scope: 'str') -> 'list[Policy]'` |
| `governance_gateway` | `GovernanceGateway` | `artifacts(self, state: 'ArtifactState | None' = None) -> 'list[ArtifactRecord]'` |
| `governance_gateway` | `GovernanceGateway` | `assemble_evidence(self, scope: 'str', subsystems: 'Sequence[str]') -> 'EvidencePackage'` |
| `governance_gateway` | `GovernanceGateway` | `assess(self, token: 'str', artifact_id: 'str', compliance: 'ComplianceState', confidence: 'float', detail: 'str' = '') -> 'ArtifactRecord'` |
| `governance_gateway` | `GovernanceGateway` | `assign_stewardship(self, token: 'str', stewardship: 'Stewardship') -> 'Stewardship'` |
| `governance_gateway` | `GovernanceGateway` | `compliance_of(self, scope: 'str') -> 'ComplianceState'` |
| `governance_gateway` | `GovernanceGateway` | `conduct_review(self, token: 'str', finding_id: 'str', scope: 'str', kind: 'ReviewKind', compliance: 'ComplianceState', detail: 'str', evidence: 'EvidencePackage', recommendation: 'str' = '') -> 'Finding'` |
| `governance_gateway` | `GovernanceGateway` | `detect_contradictions(self) -> 'list[Policy]'` |
| `governance_gateway` | `GovernanceGateway` | `drift_velocity(self, scope: 'str') -> 'float'` |
| `governance_gateway` | `GovernanceGateway` | `emergency_suspend_policy(self, policy_id: 'str', reason: 'str') -> 'Policy'` |
| `governance_gateway` | `GovernanceGateway` | `escalate(trigger, detail)` |
| `governance_gateway` | `GovernanceGateway` | `expire_reviews(self) -> 'list[ArtifactRecord]'` |
| `governance_gateway` | `GovernanceGateway` | `findings(self, scope: 'str | None' = None) -> 'list[Finding]'` |
| `governance_gateway` | `GovernanceGateway` | `form(self, token: 'str', artifact: 'GovernanceArtifact') -> 'ArtifactRecord'` |
| `governance_gateway` | `GovernanceGateway` | `form_policy(self, token: 'str', policy: 'Policy') -> 'Policy'` |
| `governance_gateway` | `GovernanceGateway` | `get(self, artifact_id: 'str') -> 'ArtifactRecord'` |
| `governance_gateway` | `GovernanceGateway` | `grant_exception(self, token: 'str', exception: 'Exception_') -> 'Exception_'` |
| `governance_gateway` | `GovernanceGateway` | `health(self) -> 'Mapping[str, Any]'` |
| `governance_gateway` | `GovernanceGateway` | `interpret(self, token: 'str', interpretation: 'Interpretation') -> 'Interpretation'` |
| `governance_gateway` | `GovernanceGateway` | `interpretations_for(self, provision: 'str') -> 'list[Interpretation]'` |
| `governance_gateway` | `GovernanceGateway` | `now()` |
| `governance_gateway` | `GovernanceGateway` | `overdue_emergency_reviews(self) -> 'list[Policy]'` |
| `governance_gateway` | `GovernanceGateway` | `overdue_exception_reviews(self) -> 'list[Exception_]'` |
| `governance_gateway` | `GovernanceGateway` | `overhead_ratio(self) -> 'float'` |
| `governance_gateway` | `GovernanceGateway` | `policy(self, policy_id: 'str') -> 'Policy'` |
| `governance_gateway` | `GovernanceGateway` | `query_journal(self, artifact_id: 'str | None' = None) -> 'list[Mapping[str, Any]]'` |
| `governance_gateway` | `GovernanceGateway` | `ratify(self, token: 'str', artifact_id: 'str', note: 'str' = '') -> 'ArtifactRecord'` |
| `governance_gateway` | `GovernanceGateway` | `record_cost(self, governance: 'float' = 0.0, operational: 'float' = 0.0) -> 'None'` |
| `governance_gateway` | `GovernanceGateway` | `record_drift(self, scope: 'str', divergence: 'float') -> 'float'` |
| `governance_gateway` | `GovernanceGateway` | `register_journal(self, subsystem: 'str', source: 'JournalSource') -> 'None'` |
| `governance_gateway` | `GovernanceGateway` | `request_review(self, artifact_id: 'str', deadline: 'timedelta') -> 'ArtifactRecord'` |
| `governance_gateway` | `GovernanceGateway` | `review_exception(self, token: 'str', exception_id: 'str') -> 'Exception_'` |
| `governance_gateway` | `GovernanceGateway` | `revoke_stewardship(self, stewardship_id: 'str', successor_id: 'str | None' = None) -> 'Stewardship'` |
| `governance_gateway` | `GovernanceGateway` | `stewardship_vacuums(self, scopes: 'Sequence[str]') -> 'list[str]'` |
| `governance_gateway` | `GovernanceGateway` | `supersede_policy(self, policy_id: 'str', successor_id: 'str') -> 'Policy'` |
| `human_interface` | `HumanInterface` | `approve(self, request_id: 'str', principal_id: 'str', note: 'str' = '') -> 'ApprovalRecord'` |
| `human_interface` | `HumanInterface` | `assert_not_halted(self, operation: 'str') -> 'None'` |
| `human_interface` | `HumanInterface` | `batch_approvals(self, batch_id: 'str', tenant_id: 'str', request_ids: 'Sequence[str]', reason: 'str') -> 'Batch'` |
| `human_interface` | `HumanInterface` | `delegate(self, order_id: 'str', tenant_id: 'str', issued_by: 'str', scope: 'frozenset[str]', directive: 'str', ttl: 'timedelta | None' = None) -> 'StandingOrder'` |
| `human_interface` | `HumanInterface` | `deliver_digest(self, tenant_id: 'str', digest_id: 'str') -> 'Digest'` |
| `human_interface` | `HumanInterface` | `demand_modification(self, request_id: 'str', principal_id: 'str', note: 'str') -> 'ApprovalRecord'` |
| `human_interface` | `HumanInterface` | `digest_due(self, tenant_id: 'str') -> 'bool'` |
| `human_interface` | `HumanInterface` | `escalate(trigger, detail)` |
| `human_interface` | `HumanInterface` | `expire_approvals(self) -> 'list[ApprovalRecord]'` |
| `human_interface` | `HumanInterface` | `health(self) -> 'Mapping[str, Any]'` |
| `human_interface` | `HumanInterface` | `invoke_panic(self, principal_id: 'str', reason: 'str') -> 'PanicReport'` |
| `human_interface` | `HumanInterface` | `notify(notification)` |
| `human_interface` | `HumanInterface` | `now()` |
| `human_interface` | `HumanInterface` | `override(self, override_id: 'str', tenant_id: 'str', scope: 'OverrideScope', target_id: 'str', directive: 'str', reason: 'str', issued_by: 'str') -> 'Override'` |
| `human_interface` | `HumanInterface` | `pending_approvals(self, tenant_id: 'str | None' = None) -> 'list[ApprovalRecord]'` |
| `human_interface` | `HumanInterface` | `raise_notification(self, notification: 'Notification') -> 'str'` |
| `human_interface` | `HumanInterface` | `register_panic_participant(self, participant: 'Participant') -> 'Participant'` |
| `human_interface` | `HumanInterface` | `reject(self, request_id: 'str', principal_id: 'str', note: 'str' = '') -> 'ApprovalRecord'` |
| `human_interface` | `HumanInterface` | `resume(self, principal_id: 'str', note: 'str' = '') -> 'None'` |
| `human_interface` | `HumanInterface` | `submit_approval(self, request: 'ApprovalRequest') -> 'ApprovalRecord'` |
| `integration_gateway` | `IntegrationGateway` | `alternatives(self, abstraction: 'str', tenant_id: 'str') -> 'list[str]'` |
| `integration_gateway` | `IntegrationGateway` | `blocker(self) -> 'str'` |
| `integration_gateway` | `IntegrationGateway` | `check_approval(self, manifest: 'IntegrationManifest', approved_instances: 'set[str] | None' = None) -> 'None'` |
| `integration_gateway` | `IntegrationGateway` | `check_classification(self, manifest: 'IntegrationManifest', classification: 'DataClassification') -> 'None'` |
| `integration_gateway` | `IntegrationGateway` | `consume(self, abstraction: 'str', tenant_id: 'str', payload: 'Mapping[str, Any]', classification: 'DataClassification', call: 'ProviderCall', cost: 'float' = 0.0) -> 'ConsumptionResult'` |
| `integration_gateway` | `IntegrationGateway` | `halt(self) -> 'int'` |
| `integration_gateway` | `IntegrationGateway` | `health(self) -> 'Mapping[str, Any]'` |
| `integration_gateway` | `IntegrationGateway` | `is_blocked(self) -> 'bool'` |
| `integration_gateway` | `IntegrationGateway` | `now()` |
| `integration_gateway` | `IntegrationGateway` | `provider_health(self, integration_id: 'str') -> 'Mapping[str, Any]'` |
| `integration_gateway` | `IntegrationGateway` | `record_instance_approval(self, integration_id: 'str', approver_id: 'str', is_human: 'bool') -> 'None'` |
| `integration_gateway` | `IntegrationGateway` | `resolve_abstraction(self, abstraction: 'str', tenant_id: 'str') -> 'IntegrationRecord'` |
| `integration_gateway` | `IntegrationGateway` | `terminate(self, integration_id: 'str', reason: 'str', is_human: 'bool') -> 'IntegrationRecord'` |
| `integration_registry` | `IntegrationRegistry` | `abstractions(self) -> 'list[CapabilityAbstraction]'` |
| `integration_registry` | `IntegrationRegistry` | `activate(self, integration_id: 'str') -> 'IntegrationRecord'` |
| `integration_registry` | `IntegrationRegistry` | `active(self, tenant_id: 'str | None' = None) -> 'list[IntegrationRecord]'` |
| `integration_registry` | `IntegrationRegistry` | `alternatives_for(self, abstraction: 'str') -> 'list[str]'` |
| `integration_registry` | `IntegrationRegistry` | `approve(self, integration_id: 'str', approver_id: 'str', is_human: 'bool', decision_class: 'str') -> 'IntegrationRecord'` |
| `integration_registry` | `IntegrationRegistry` | `blocker(self) -> 'str'` |
| `integration_registry` | `IntegrationRegistry` | `concentration(self) -> 'dict[str, float]'` |
| `integration_registry` | `IntegrationRegistry` | `deprecate(self, integration_id: 'str', successor_id: 'str | None' = None) -> 'IntegrationRecord'` |
| `integration_registry` | `IntegrationRegistry` | `get(self, integration_id: 'str') -> 'IntegrationRecord'` |
| `integration_registry` | `IntegrationRegistry` | `health(self) -> 'Mapping[str, Any]'` |
| `integration_registry` | `IntegrationRegistry` | `is_blocked(self) -> 'bool'` |
| `integration_registry` | `IntegrationRegistry` | `journal_entries(self) -> 'list[Mapping[str, Any]]'` |
| `integration_registry` | `IntegrationRegistry` | `now()` |
| `integration_registry` | `IntegrationRegistry` | `record_health(self, integration_id: 'str', healthy: 'bool', latency_seconds: 'float' = 0.0) -> 'IntegrationRecord'` |
| `integration_registry` | `IntegrationRegistry` | `register(self, manifest: 'IntegrationManifest', actor_id: 'str') -> 'IntegrationRecord'` |
| `integration_registry` | `IntegrationRegistry` | `reinstate(self, integration_id: 'str', actor_id: 'str') -> 'IntegrationRecord'` |
| `integration_registry` | `IntegrationRegistry` | `resolve(self, abstraction: 'str', tenant_id: 'str') -> 'list[IntegrationRecord]'` |
| `integration_registry` | `IntegrationRegistry` | `retire(self, integration_id: 'str') -> 'IntegrationRecord'` |
| `integration_registry` | `IntegrationRegistry` | `specified(self) -> 'list[IntegrationManifest]'` |
| `integration_registry` | `IntegrationRegistry` | `specify(self, manifest: 'IntegrationManifest') -> 'IntegrationManifest'` |
| `integration_registry` | `IntegrationRegistry` | `specify_abstraction(self, abstraction: 'CapabilityAbstraction') -> 'CapabilityAbstraction'` |
| `integration_registry` | `IntegrationRegistry` | `suspend(self, integration_id: 'str', reason: 'str') -> 'IntegrationRecord'` |
| `integration_registry` | `IntegrationRegistry` | `validate(self, integration_id: 'str') -> 'IntegrationRecord'` |
| `knowledge_gateway` | `KnowledgeGateway` | `arbitrate(self, contradiction_id: 'str', arbiter_id: 'str', upheld_belief_id: 'str') -> 'Contradiction'` |
| `knowledge_gateway` | `KnowledgeGateway` | `contradictions_for(self, belief_id: 'str') -> 'list[Contradiction]'` |
| `knowledge_gateway` | `KnowledgeGateway` | `deprecate(self, belief_id: 'str', justification: 'str') -> 'BeliefRecord'` |
| `knowledge_gateway` | `KnowledgeGateway` | `detect_contradiction(self, left_id: 'str', right_id: 'str', detail: 'str') -> 'Contradiction'` |
| `knowledge_gateway` | `KnowledgeGateway` | `due_for_revalidation(self, domain: 'str' = 'operational') -> 'list[BeliefRecord]'` |
| `knowledge_gateway` | `KnowledgeGateway` | `get(self, belief_id: 'str') -> 'BeliefRecord'` |
| `knowledge_gateway` | `KnowledgeGateway` | `health(self) -> 'Mapping[str, Any]'` |
| `knowledge_gateway` | `KnowledgeGateway` | `integrate(self, belief_id: 'str', relations: 'list[tuple[str, RelationType]]') -> 'BeliefRecord'` |
| `knowledge_gateway` | `KnowledgeGateway` | `now()` |
| `knowledge_gateway` | `KnowledgeGateway` | `promote(self, belief_id: 'str', approved_by: 'str | None' = None) -> 'BeliefRecord'` |
| `knowledge_gateway` | `KnowledgeGateway` | `propose_ontology_change(self, proposal_id: 'str', kind: 'str', name: 'str', proposed_by: 'str', rationale: 'str') -> 'OntologyProposal'` |
| `knowledge_gateway` | `KnowledgeGateway` | `query(self, token: 'str', tenant_id: 'str', belief_type: 'str | None' = None, min_confidence: 'float' = 0.6, max_sensitivity: 'BeliefSensitivity' = <BeliefSensitivity.TENANT_SCOPED: 'tenant_scoped'>, limit: 'int | None' = None) -> 'list[BeliefAnswer]'` |
| `knowledge_gateway` | `KnowledgeGateway` | `query_ontology(self) -> 'Mapping[str, Any]'` |
| `knowledge_gateway` | `KnowledgeGateway` | `ratify_ontology_change(self, proposal_id: 'str', ratified_by: 'str') -> 'OntologyProposal'` |
| `knowledge_gateway` | `KnowledgeGateway` | `reconcile(self, contradiction_id: 'str', resolved_by: 'str', cross_business: 'bool' = False) -> 'tuple[Contradiction, ReconciliationStrategy]'` |
| `knowledge_gateway` | `KnowledgeGateway` | `reinstate_extractor(self, extractor: 'str', reinstated_by: 'str') -> 'None'` |
| `knowledge_gateway` | `KnowledgeGateway` | `revalidate(self, belief_id: 'str', confidence: 'float', domain: 'str' = 'operational') -> 'BeliefRecord'` |
| `knowledge_gateway` | `KnowledgeGateway` | `submit(self, token: 'str', belief: 'Belief') -> 'BeliefRecord'` |
| `knowledge_gateway` | `KnowledgeGateway` | `traverse(self, token: 'str', belief_id: 'str', depth: 'int' = 3) -> 'list[str]'` |
| `knowledge_gateway` | `KnowledgeGateway` | `validate(self, belief_id: 'str', confidence: 'float') -> 'BeliefRecord'` |
| `learning_gateway` | `LearningGateway` | `alert_human(detail)` |
| `learning_gateway` | `LearningGateway` | `consolidate(self, package_id: 'str', tenant_id: 'str', target_subsystem: 'str') -> 'ConsolidationPackage'` |
| `learning_gateway` | `LearningGateway` | `consult_failures(self, subject_id: 'str') -> 'FailureLibraryEntry | None'` |
| `learning_gateway` | `LearningGateway` | `decay(self) -> 'list[LearningEntry]'` |
| `learning_gateway` | `LearningGateway` | `entries(self, state: 'LearningState | None' = None) -> 'list[LearningEntry]'` |
| `learning_gateway` | `LearningGateway` | `escalate(trigger, detail)` |
| `learning_gateway` | `LearningGateway` | `failure_library(self) -> 'list[FailureLibraryEntry]'` |
| `learning_gateway` | `LearningGateway` | `get(self, entry_id: 'str') -> 'LearningEntry'` |
| `learning_gateway` | `LearningGateway` | `health(self) -> 'Mapping[str, Any]'` |
| `learning_gateway` | `LearningGateway` | `hypothesize(self, token: 'str', hypothesis: 'Hypothesis') -> 'LearningEntry'` |
| `learning_gateway` | `LearningGateway` | `now()` |
| `learning_gateway` | `LearningGateway` | `observe(self, token: 'str', observation: 'Observation') -> 'Observation'` |
| `learning_gateway` | `LearningGateway` | `overdue(self) -> 'list[LearningEntry]'` |
| `learning_gateway` | `LearningGateway` | `prioritize(self, tenant_id: 'str') -> 'list[LearningEntry]'` |
| `learning_gateway` | `LearningGateway` | `propagate(self, package_id: 'str') -> 'list[str]'` |
| `learning_gateway` | `LearningGateway` | `query_journal(self, entry_id: 'str | None' = None) -> 'list[Mapping[str, Any]]'` |
| `learning_gateway` | `LearningGateway` | `recognize(self, pattern: 'Pattern') -> 'Pattern'` |
| `learning_gateway` | `LearningGateway` | `record_measurement(self, entry_id: 'str', improved: 'bool') -> 'LearningEntry'` |
| `learning_gateway` | `LearningGateway` | `register_target(self, target_subsystem: 'str', sink: 'ProposalSink') -> 'None'` |
| `learning_gateway` | `LearningGateway` | `report_adoption(self, entry_id: 'str', adopted: 'bool', justification: 'str' = '') -> 'LearningEntry'` |
| `learning_gateway` | `LearningGateway` | `submit_human_feedback(self, token: 'str', observation: 'Observation') -> 'Observation'` |
| `learning_gateway` | `LearningGateway` | `validate(self, entry_id: 'str') -> 'LearningEntry'` |
| `llm_router` | `LLMRouter` | `health(self) -> 'Mapping[str, Any]'` |
| `llm_router` | `LLMRouter` | `infer(self, request: 'InferenceRequest') -> 'InferenceResult'` |
| `llm_router` | `LLMRouter` | `now()` |
| `llm_router` | `LLMRouter` | `register_template(self, template: 'PromptTemplate') -> 'PromptTemplate'` |
| `memory_gateway` | `MemoryGateway` | `archive(self, memory_id: 'str') -> 'MemoryRecord'` |
| `memory_gateway` | `MemoryGateway` | `form(self, token: 'str', entry: 'MemoryEntry', edges: 'list[tuple[str, EdgeType]] | None' = None) -> 'MemoryRecord'` |
| `memory_gateway` | `MemoryGateway` | `get(self, memory_id: 'str') -> 'MemoryRecord'` |
| `memory_gateway` | `MemoryGateway` | `health(self) -> 'Mapping[str, Any]'` |
| `memory_gateway` | `MemoryGateway` | `integrate(self, token: 'str', memory_id: 'str', edges: 'list[tuple[str, EdgeType]]') -> 'MemoryRecord'` |
| `memory_gateway` | `MemoryGateway` | `lineage(self, token: 'str', memory_id: 'str') -> 'Mapping[str, Any]'` |
| `memory_gateway` | `MemoryGateway` | `now()` |
| `memory_gateway` | `MemoryGateway` | `purge(self, memory_id: 'str', approved_by: 'str | None', approver_is_human: 'bool') -> 'MemoryRecord'` |
| `memory_gateway` | `MemoryGateway` | `retrieve(self, token: 'str', tenant_id: 'str', role: 'SemanticRole | None' = None, memory_type: 'str | None' = None, business_id: 'str | None' = None, min_confidence: 'float' = 0.0, max_sensitivity: 'Sensitivity' = <Sensitivity.TENANT_SCOPED: 'tenant_scoped'>, limit: 'int | None' = None) -> 'list[RetrievalResult]'` |
| `memory_gateway` | `MemoryGateway` | `revalidate(self, memory_id: 'str', confidence: 'float') -> 'MemoryRecord'` |
| `memory_gateway` | `MemoryGateway` | `run_decay(self) -> 'list[MemoryRecord]'` |
| `memory_gateway` | `MemoryGateway` | `traverse(self, token: 'str', memory_id: 'str', depth: 'int' = 1) -> 'list[str]'` |
| `observability_gateway` | `ObservabilityGateway` | `confirm_halt(self, subsystem: 'str') -> 'HaltConfirmation'` |
| `observability_gateway` | `ObservabilityGateway` | `constitutional_health(self, tenant_id: 'str', approvals_required: 'int', approvals_obtained: 'int', subsystems_reporting: 'int', subsystems_total: 'int', escalations_raised: 'int', escalations_acknowledged: 'int') -> 'ConstitutionalHealth'` |
| `observability_gateway` | `ObservabilityGateway` | `correlate(self, token: 'str', tenant_id: 'str', key: 'str', value: 'str') -> 'IncidentTimeline'` |
| `observability_gateway` | `ObservabilityGateway` | `escalate(trigger, detail)` |
| `observability_gateway` | `ObservabilityGateway` | `health(self) -> 'Mapping[str, Any]'` |
| `observability_gateway` | `ObservabilityGateway` | `ingest(self, signal: 'Signal') -> 'EnrichedSignal | QualityAnomaly'` |
| `observability_gateway` | `ObservabilityGateway` | `meets_visibility_slo(self) -> 'Mapping[str, bool]'` |
| `observability_gateway` | `ObservabilityGateway` | `notify_governance(alert)` |
| `observability_gateway` | `ObservabilityGateway` | `now()` |
| `observability_gateway` | `ObservabilityGateway` | `on_slo_change(action, slo)` |
| `observability_gateway` | `ObservabilityGateway` | `panic_confirmation(self, expected: 'tuple[str, ...]') -> 'Mapping[str, Any]'` |
| `observability_gateway` | `ObservabilityGateway` | `panic_started(self) -> 'None'` |
| `observability_gateway` | `ObservabilityGateway` | `publish_slo(self, slo: 'SLO') -> 'SLO'` |
| `observability_gateway` | `ObservabilityGateway` | `query(self, token: 'str', tenant_id: 'str', source_identity: 'str | None' = None, signal_type: 'SignalType | None' = None, name: 'str | None' = None, since: 'datetime | None' = None, max_sensitivity: 'Sensitivity' = <Sensitivity.INTERNAL: 'internal'>) -> 'list[EnrichedSignal]'` |
| `observability_gateway` | `ObservabilityGateway` | `raise_alert(self, alert_id: 'str', tenant_id: 'str', severity: 'Severity', subsystem: 'str', summary: 'str', **detail: 'Any') -> 'Alert'` |
| `observability_gateway` | `ObservabilityGateway` | `record_sli(self, name: 'str', observed: 'float') -> 'SLIReading'` |
| `observability_gateway` | `ObservabilityGateway` | `register_journal(self, subsystem: 'str', journal: 'Any') -> 'None'` |
| `observability_gateway` | `ObservabilityGateway` | `sink_for(self, _source_identity: 'str') -> 'Callable[[Signal], None]'` |
| `plugin_manager` | `PluginManager` | `catalogue(self, state: 'PluginState | None' = None) -> 'list[PluginRecord]'` |
| `plugin_manager` | `PluginManager` | `disable(self, plugin_id: 'str', principal_id: 'str', reason: 'str' = '') -> 'PluginRecord'` |
| `plugin_manager` | `PluginManager` | `discover(self, manifest: 'PluginManifest') -> 'PluginRecord'` |
| `plugin_manager` | `PluginManager` | `enable(self, plugin_id: 'str', principal_id: 'str') -> 'PluginRecord'` |
| `plugin_manager` | `PluginManager` | `get(self, plugin_id: 'str') -> 'PluginRecord'` |
| `plugin_manager` | `PluginManager` | `grant(self, plugin_id: 'str', principal_id: 'str', permissions: 'frozenset[str]') -> 'PluginRecord'` |
| `plugin_manager` | `PluginManager` | `health(self) -> 'Mapping[str, Any]'` |
| `plugin_manager` | `PluginManager` | `install(self, plugin_id: 'str', principal_id: 'str') -> 'PluginRecord'` |
| `plugin_manager` | `PluginManager` | `now()` |
| `plugin_manager` | `PluginManager` | `permits(self, plugin_id: 'str', permission: 'str') -> 'bool'` |
| `plugin_manager` | `PluginManager` | `quarantine(self, plugin_id: 'str', reason: 'str') -> 'PluginRecord'` |
| `plugin_manager` | `PluginManager` | `record_invocation(self, plugin_id: 'str', succeeded: 'bool') -> 'PluginRecord'` |
| `plugin_manager` | `PluginManager` | `revoke(self, plugin_id: 'str', principal_id: 'str', permissions: 'frozenset[str]') -> 'PluginRecord'` |
| `plugin_manager` | `PluginManager` | `subscribed_events(self, plugin_id: 'str') -> 'frozenset[str]'` |
| `plugin_manager` | `PluginManager` | `uninstall(self, plugin_id: 'str', principal_id: 'str') -> 'PluginRecord'` |
| `security_gateway` | `SecurityGateway` | `authenticate(self, principal_id: 'str', credential_id: 'str', presented_hash: 'str', claiming_type: 'PrincipalType', ttl: 'timedelta | None' = None, workspace_ids: 'tuple[str, ...]' = (), task_timeout_seconds: 'int' = 300, max_retries: 'int' = 3) -> 'tuple[str, TokenClaims]'` |
| `security_gateway` | `SecurityGateway` | `authorize(self, token: 'str', request: 'AuthorizationRequest') -> 'AuthorizationResult'` |
| `security_gateway` | `SecurityGateway` | `bootstrap_human_sovereign(self, principal_id: 'str', name: 'str', tenant_id: 'str') -> 'Principal'` |
| `security_gateway` | `SecurityGateway` | `change_principal_status(self, principal_id: 'str', target: 'PrincipalStatus', actor_id: 'str') -> 'Principal'` |
| `security_gateway` | `SecurityGateway` | `create_security_context(self, claims: 'TokenClaims', trace_id: 'str', workspace_id: 'str | None' = None, action_id: 'str | None' = None) -> 'SecurityContext'` |
| `security_gateway` | `SecurityGateway` | `health(self) -> 'Mapping[str, Any]'` |
| `security_gateway` | `SecurityGateway` | `manage_delegation(self, operation: 'str', delegation_id: 'str', actor_id: 'str', delegation_type: 'DelegationType | None' = None, delegatee_id: 'str | None' = None, permissions: 'tuple[str, ...]' = (), duration: 'timedelta | None' = None, authorized_by: 'str | None' = None) -> 'Delegation'` |
| `security_gateway` | `SecurityGateway` | `now()` |
| `security_gateway` | `SecurityGateway` | `query_journal(self, principal_id: 'str | None' = None, tenant_id: 'str | None' = None, event_type: 'SecurityEventType | None' = None, since: 'datetime | None' = None) -> 'list[SecurityEvent]'` |
| `security_gateway` | `SecurityGateway` | `recompute_permissions(self, principal_id: 'str') -> 'None'` |
| `security_gateway` | `SecurityGateway` | `register_identity(self, request: 'RegistrationRequest') -> 'Principal'` |
| `security_gateway` | `SecurityGateway` | `report_constitutional_violation(self, error: 'ConstitutionalViolationError', tenant_id: 'str') -> 'Incident'` |
| `security_gateway` | `SecurityGateway` | `resolve_secret_reference(self, reference: 'str', sandbox_id: 'str', invocation_id: 'str', requester_id: 'str') -> 'InjectionGrant'` |
| `security_gateway` | `SecurityGateway` | `revoke(self, principal_id: 'str', revoker_id: 'str', trigger: 'RevocationTrigger', reason: 'str', scope: 'tuple[str, ...]' = ('permissions', 'roles', 'delegations', 'credentials', 'tokens')) -> 'RevocationRecord'` |
| `security_gateway` | `SecurityGateway` | `validate_delegation_chain(self, delegatee_id: 'str') -> 'frozenset[str]'` |
| `security_gateway` | `SecurityGateway` | `validate_security_context(self, context: 'SecurityContext | None', action: 'str') -> 'SecurityContext'` |
| `tool_executor` | `ToolExecutor` | `health(self) -> 'Mapping[str, Any]'` |
| `tool_executor` | `ToolExecutor` | `now()` |
| `tool_executor` | `ToolExecutor` | `result_for(self, invocation_id: 'str') -> 'ExecutionResult'` |
| `tool_executor` | `ToolExecutor` | `run(self, contract: 'InvocationContract', tool: 'Callable[[Sandbox, dict[str, Any]], dict[str, Any]]', cost_meter: 'Callable[[], float] | None' = None) -> 'ExecutionResult'` |
| `tool_gateway` | `ToolGateway` | `authorize(self, token: 'str', tool_id: 'str', decision_id: 'str', parameters: 'dict[str, Any]', cost_ceiling: 'float', idempotency_key: 'str', required_decision_class: 'str' = 'A', workflow_id: 'str | None' = None, upstream_invocation_id: 'str | None' = None, requested_tier: 'SandboxTier | None' = None) -> 'InvocationContract'` |
| `tool_gateway` | `ToolGateway` | `compensate(self, token: 'str', invocation_id: 'str', decision_id: 'str') -> 'InvocationContract'` |
| `tool_gateway` | `ToolGateway` | `complete(self, invocation_id: 'str', outcome: 'InvocationOutcome', output: 'dict[str, Any] | None', actual_cost: 'float', started_at: 'datetime', detail: 'str' = '') -> 'InvocationRecord'` |
| `tool_gateway` | `ToolGateway` | `compose_tier(self, tool_ids: 'tuple[str, ...]') -> 'SandboxTier'` |
| `tool_gateway` | `ToolGateway` | `contract_for(self, invocation_id: 'str') -> 'InvocationContract'` |
| `tool_gateway` | `ToolGateway` | `health(self) -> 'Mapping[str, Any]'` |
| `tool_gateway` | `ToolGateway` | `now()` |
| `tool_gateway` | `ToolGateway` | `query_records(self, tool_id: 'str | None' = None, consumer_id: 'str | None' = None, decision_id: 'str | None' = None) -> 'list[InvocationRecord]'` |
| `tool_registry` | `ToolRegistry` | `all_tools(self) -> 'list[ToolRecord]'` |
| `tool_registry` | `ToolRegistry` | `decay_trust(self) -> 'list[ToolRecord]'` |
| `tool_registry` | `ToolRegistry` | `deprecate(self, tool_id: 'str', successor_tool_id: 'str | None', notice: 'timedelta') -> 'ToolRecord'` |
| `tool_registry` | `ToolRegistry` | `discover(self, token: 'str', capability: 'str | None' = None, max_cost: 'float | None' = None, min_trust: 'float' = 0.0, include_unhealthy: 'bool' = False) -> 'list[ToolRecord]'` |
| `tool_registry` | `ToolRegistry` | `get(self, tool_id: 'str') -> 'ToolRecord'` |
| `tool_registry` | `ToolRegistry` | `health(self) -> 'Mapping[str, Any]'` |
| `tool_registry` | `ToolRegistry` | `health_of(self, tool_id: 'str') -> 'Mapping[str, Any]'` |
| `tool_registry` | `ToolRegistry` | `lineage(self, tool_id: 'str') -> 'list[str]'` |
| `tool_registry` | `ToolRegistry` | `now()` |
| `tool_registry` | `ToolRegistry` | `record_outcome(self, tool_id: 'str', succeeded: 'bool') -> 'ToolRecord'` |
| `tool_registry` | `ToolRegistry` | `register(self, token: 'str', manifest: 'ToolManifest') -> 'ToolRecord'` |
| `tool_registry` | `ToolRegistry` | `report_health(self, tool_id: 'str', availability: 'Availability') -> 'ToolRecord'` |
| `tool_registry` | `ToolRegistry` | `transition(self, tool_id: 'str', target: 'ToolState', reason: 'str' = '') -> 'ToolRecord'` |
| `workflow_engine` | `WorkflowEngine` | `advance(self, token: 'str') -> 'list[WorkflowRun]'` |
| `workflow_engine` | `WorkflowEngine` | `get(self, workflow_id: 'str') -> 'WorkflowRun'` |
| `workflow_engine` | `WorkflowEngine` | `health(self) -> 'Mapping[str, Any]'` |
| `workflow_engine` | `WorkflowEngine` | `now()` |
| `workflow_engine` | `WorkflowEngine` | `query(self, workflow_id: 'str') -> 'Mapping[str, Any]'` |
| `workflow_engine` | `WorkflowEngine` | `register_definition(self, definition: 'WorkflowDefinition') -> 'WorkflowDefinition'` |
| `workflow_engine` | `WorkflowEngine` | `replay(self, workflow_id: 'str') -> 'list[str]'` |
| `workflow_engine` | `WorkflowEngine` | `signal(self, token: 'str', workflow_id: 'str', kind: 'str') -> 'WorkflowRun'` |
| `workflow_engine` | `WorkflowEngine` | `trigger(self, token: 'str', name: 'str', version: 'str', context: 'WorkflowContext') -> 'WorkflowRun'` |

## Appendix C - Data Ownership Matrix

21A §10 allocates ownership exclusively. Two entries here are findings
rather than restatements; both are explained in the source.

| Module | Owns exclusively |
|---|---|
| `agent_runtime` | agent manifests, reputation, drift baselines, agent journal |
| `api_gateway` | routes, rate-limit buckets, idempotency keys, ingress journal |
| `content_agent` | weekly notes, post drafts |
| `cost_manager` | budgets, ledger entries, circuit breakers |
| `decision_gateway` | decision records, standing orders (11.19 pre-authorization), decision journal |
| `event_bus` | event streams, consumer groups, dead letters |
| `governance_gateway` | governance artifacts, policy hierarchy, stewardships, governance journal |
| `human_interface` | approvals, overrides, standing orders (05.18.5 delegation; duplicates Decision's, see note), digests, panic journal |
| `knowledge_gateway` | beliefs, ontology, contradictions, knowledge journal |
| `learning_gateway` | learning entries, patterns, failure library, learning journal |
| `llm_router` | prompt templates, response cache, router journal |
| `memory_gateway` | memory entries, provenance, memory journal |
| `observability_gateway` | telemetry store, SLI/SLO registry, observability journal |
| `plugin_manager` | plugin manifests, plugin grants, plugin journal |
| `security_gateway` | identities, credentials, tokens, roles, delegations, security journal |
| `tool_executor` | sandboxes, execution records, executor journal |
| `tool_gateway` | invocation contracts, invocation records, tool journal |
| `tool_registry` | tool manifests, trust scores, registry journal |
| `workflow_engine` | workflow definitions, runs, checkpoints, workflow journal |

## Appendix D - Journal Register

22 modules hold an `ImmutableJournal`, found by import rather than by claim.
The Event Bus deliberately holds none: 08.25.2 makes an event immutable
after publication, so the stream is already the append-only record and a
journal beside it would be a second copy of the same history.

| Module |
|---|
| `agent_runtime` |
| `api_gateway` |
| `decision_gateway` |
| `deployment_gateway` |
| `deployment_registry` |
| `evolution_gateway` |
| `governance_gateway` |
| `human_interface` |
| `integration_gateway` |
| `integration_registry` |
| `kernel` |
| `knowledge_gateway` |
| `learning_gateway` |
| `llm_router` |
| `memory_gateway` |
| `observability_gateway` |
| `plugin_manager` |
| `security_gateway` |
| `tool_executor` |
| `tool_gateway` |
| `tool_registry` |
| `workflow_engine` |

## Appendix E - Signal Contract Register

54 distinct signals, extracted from the emitting call sites.

| Module | Signal | Type |
|---|---|---|
| `agent_runtime` | `agent.drift.detected` | event |
| `agent_runtime` | `agent.execution.cost` | metric |
| `api_gateway` | `gateway.request_received` | event |
| `api_gateway` | `gateway.response_sent` | event |
| `cost_manager` | `cost.budget.allocated` | event |
| `cost_manager` | `cost.budget.threshold_breached` | event |
| `cost_manager` | `cost.budget.unallocated` | event |
| `cost_manager` | `cost.budget.utilization` | metric |
| `cost_manager` | `cost.circuit_breaker.reset` | event |
| `cost_manager` | `cost.circuit_breaker.tripped` | event |
| `cost_manager` | `cost.operation.spend` | metric |
| `decision_gateway` | `decision.approval.timeout` | event |
| `decision_gateway` | `decision.circuit_breaker.breach` | event |
| `decision_gateway` | `decision.committed` | metric |
| `decision_gateway` | `decision.outcome.diverged` | event |
| `decision_gateway` | `decision.proposal.rejected` | event |
| `decision_gateway` | `decision.standing_order.violation` | event |
| `deployment_gateway` | `deployment.promotion.authorized` | event |
| `evolution_gateway` | `evolution.proposal.handed_off` | event |
| `governance_gateway` | `governance.policy.suspended` | event |
| `governance_gateway` | `governance.ruling.issued` | event |
| `human_interface` | `human.approval.answered` | event |
| `human_interface` | `human.approval.expired` | event |
| `human_interface` | `human.digest.delivered` | event |
| `human_interface` | `human.override.issued` | event |
| `human_interface` | `human.panic.invoked` | event |
| `human_interface` | `human.panic.resumed` | event |
| `integration_gateway` | `integration.consumed` | event |
| `knowledge_gateway` | `knowledge.arbitration.required` | event |
| `knowledge_gateway` | `knowledge.belief.confidence` | metric |
| `knowledge_gateway` | `knowledge.contradiction.detected` | event |
| `knowledge_gateway` | `knowledge.hypothesis.quarantined` | event |
| `learning_gateway` | `learning.contradiction.quarantined` | event |
| `learning_gateway` | `learning.entry.confirmed` | metric |
| `learning_gateway` | `learning.entry.refuted` | event |
| `learning_gateway` | `learning.proposal.propagated` | event |
| `llm_router` | `llm.grounding.failed` | event |
| `llm_router` | `llm.inference.cost` | metric |
| `llm_router` | `llm.sanitization.finding` | event |
| `llm_router` | `llm.tier.failover` | event |
| `memory_gateway` | `memory.boundary.violation` | event |
| `memory_gateway` | `memory.decay.stale` | event |
| `memory_gateway` | `memory.formation.confidence` | metric |
| `memory_gateway` | `memory.formation.rejected` | event |
| `memory_gateway` | `memory.retrieval.hits` | metric |
| `memory_gateway` | `memory.validation.quarantined` | event |
| `tool_executor` | `tool.sandbox.violation` | event |
| `tool_gateway` | `tool.invocation.cost` | metric |
| `tool_registry` | `tool.registered` | event |
| `tool_registry` | `tool.trust.below_threshold` | event |
| `workflow_engine` | `workflow.compensation.stalled` | event |
| `workflow_engine` | `workflow.completed` | event |
| `workflow_engine` | `workflow.gate.awaiting` | event |
| `workflow_engine` | `workflow.planning.failed` | event |

## Appendix G - Constitutional Interpretation Register (live)

5 open, 4 resolved. Three were resolved **in
construction** rather than by ruling, which is a weaker thing and is said so:
a choice made in code is reversible by a later ruling.

| CIR | Severity | Status | Title | Disposition |
|---|---|---|---|---|
| CIR-001 | critical | **resolved** | Technology naming conflict between 03_TECH_STACK and 17, 18, 19 | Resolved 2026-08-24 by G4 human sovereign ruling, not in construction: the naming prohibition governs capability abstractions and governance artifacts, and 03's classification as an Implementation Specification distinguishes it from the constitutional documents the rule addresses. Released integration_registry, integration_gateway, deployment_registry, deployment_gateway, evolution_gateway for construction, all five now built. The abstraction-level prohibition is untouched and still enforced. See docs/rulings/CIR-001.md. |
| CIR-002 | high | **open** | Direct service call prohibition versus specified synchronous interfaces | Unresolved but not blocking here: this build is in-process, so no transport decision has been taken. It becomes binding the moment a transport is chosen. |
| CIR-003 | high | **open** | Data ownership allocation is incomplete | Appendix C below is this build's working allocation, not a ruling. |
| CIR-004 | high | **open** | Composite latency budget is unallocated | No latency budget has been validated against the per-subsystem tables; the SLO registry publishes the targets and nothing measures against them in production. |
| CIR-005 | medium | **resolved** | security/ and observability/ as shared libraries versus Gateways | Resolved in construction rather than by ruling: both are built as Gateways with no library import path, per 21A's 'No Gateway is a library'. Recorded as resolved-by-construction so the choice is visible if a ruling later disagrees. |
| CIR-006 | medium | **resolved** | Panic Protocol five-second bound lacks a specified scope of halt | Scoped in construction to every registered participant, measured end to end at S8. The residual gap is that nothing forces a subsystem to register. |
| CIR-007 | medium | **resolved** | Confidence derivation rules across four subsystems are unspecified | Resolved in construction by the shared calibration surface in kernel.authority, after the first derivation made two authority levels structurally unreachable. |
| CIR-008 | medium | **open** | Oversight and adaptation resource consumption versus the fifteen percent cap | Made answerable rather than answered: the Governance Gateway measures and reports its own overhead ratio against a 15% working ceiling. |
| CIR-009 | low | **open** | Documentation structure divergence | Not blocking; documents 09's missing rules section is the concrete instance. |

## Appendix H - Risk Register (live)

7 open, 2 realized.

| Risk | Severity | State | Title | Disposition |
|---|---|---|---|---|
| R1 | critical | **mitigated** | Technology naming conflict | CIR-001 resolved 2026-08-24 by G4 ruling; the five blocked modules are now built, and the abstraction-level naming prohibition the ruling preserved remains enforced by test |
| R2 | high | **open** | Direct service call prohibition | CIR-002; deferred by in-process build |
| R3 | high | **open** | Composite latency budget unallocated | CIR-004; the SLO registry publishes the per-subsystem targets and nothing measures against them |
| R4 | high | **open** | Data ownership allocation incomplete | CIR-003; Appendix C is a working allocation |
| R5 | high | **open** | Journal write amplification | every Gateway journals every action; no measurement of the aggregate write rate exists |
| R6 | medium | **mitigated** | Panic Protocol 5-second bound across a distributed system | measured end to end at S8 in-process; a distributed halt is untested |
| R7 | medium | **mitigated** | Bilingual workflow boundary | single-source generation plus contract tests in both directions, both gated in CI |
| R8 | medium | **realized** | Confidence semantics compound across four subsystems | the first derivation made two authority levels structurally unreachable; found by test and fixed |
| R9 | medium | **mitigated** | Oversight overhead versus the 15% cap | measured and reported rather than assumed; CIR-008 remains open |
| R10 | medium | **open** | Multi-tenancy designed-in, single-tenant deployed | tenant isolation is enforced throughout and exercised only against synthetic tenants |
| R11 | low | **open** | Local-first operability of the Premium tier | no external integration exists to test local-first degradation against |
| R12 | low | **open** | Documentation structure divergence | CIR-009; document 09's missing Non-Violable Rules section is the concrete instance |
| R13 | low | **realized** | Scope and completion risk | all 13 stages addressed; 4 modules construction-blocked and none at full Definition-of-Done |
