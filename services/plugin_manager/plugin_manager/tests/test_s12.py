"""Stage S12 — Transformation & Extension (21B §26, 02.3.10, 01.18.2).

Two modules with different statuses, tested together because the pairing is
what the stage is about:

* **Evolution Gateway** is CIR-001 blocked. Per 21C §38.6 it carries
  specification-level tests only: the pipeline, the ordering constraints, the
  handoff direction, and that every construction verb raises.
* **Plugin Manager** is **not** blocked and is built for real.

The rule the Evolution tests are shaped around is `19.3`: Evolution "packages;
it does not ratify." The rule the Plugin tests are shaped around is `02.3.10`:
plugins run "never in core process space."
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.exceptions import NotFoundError, ValidationError
from evolution_gateway import (
    CONSUMABLE_LEARNING_STATES,
    EVOLUTION_PIPELINE,
    ArtifactClass,
    ConstructionBlocked,
    EvolutionGateway,
    ProposalState,
    ratification_verbs,
)
from plugin_manager import (
    PLUGIN_TRANSITIONS,
    QUARANTINE_MINIMUM_SAMPLE,
    PluginManager,
    PluginManifest,
    PluginRefused,
    PluginState,
    ResourceLimits,
    SandboxTier,
    in_process_execution_verbs,
    validate_manifest,
)

HUMAN = "human-sovereign"
AGENT = "agent-analyst"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


def is_human(principal_id: str) -> bool:
    return principal_id.startswith("human-")


# =============================================== Evolution Gateway (blocked)


@pytest.fixture
def evolution() -> EvolutionGateway:
    return EvolutionGateway()


@pytest.mark.parametrize(
    "operation",
    [
        "monitor_signals",
        "draft",
        "analyse_impact",
        "frame_compensation",
        "package",
        "hand_off",
        "record_outcome",
        "run_experiment",
    ],
)
def test_every_evolution_construction_verb_raises(evolution: EvolutionGateway, operation: str) -> None:
    """Build Spec Section 24 — never silently converted to Done."""
    with pytest.raises(ConstructionBlocked, match="not authorized"):
        getattr(evolution, operation)()


def test_evolution_has_no_ratification_verb() -> None:
    """19.3 — Evolution "packages; it does not ratify."

    Structural, and it is what resolves the Evolution/Governance circular
    dependency: the edge from Evolution back to ratification does not exist,
    so 19.16.2's handoff is unidirectional by construction rather than by
    agreement.
    """
    assert ratification_verbs() == ()
    forbidden = {"ratify", "approve", "amend", "enact", "adopt", "commit_amendment"}
    present = {name for name in dir(EvolutionGateway) if not name.startswith("_")}
    assert not (forbidden & present), f"Evolution acquired ratification authority: {forbidden & present}"


def test_evolution_consumes_only_confirmed_learning(evolution: EvolutionGateway) -> None:
    """19.5 / 21B §26.6 — never Proposed or Adopted-but-unconfirmed.

    An unconfirmed entry has not been measured. Amending a constitutional bound
    on the strength of something that might still be refuted is the failure
    this gate exists to prevent.
    """
    assert evolution.consumes_learning_state("confirmed")
    for state in ("propagated", "adopted", "validated", "refuted", "quarantined"):
        assert not evolution.consumes_learning_state(state)
    assert CONSUMABLE_LEARNING_STATES == frozenset({"confirmed"})


def test_the_recursion_guard_precedes_packaging(evolution: EvolutionGateway) -> None:
    """19.14 — mirroring 13's self-referential learning guard.

    A self-referential proposal that reached Governance would arrive carrying
    Evolution's own endorsement of a change to Evolution's own bounds.
    """
    assert evolution.recursion_guard_precedes_packaging()


def test_compensation_is_framed_before_packaging(evolution: EvolutionGateway) -> None:
    """19.13 — every proposal carries a rollback plan before it is packaged."""
    assert evolution.compensation_precedes_packaging()


def test_the_pipeline_matches_the_architecture(evolution: EvolutionGateway) -> None:
    """21B §26.4, in order."""
    assert evolution.pipeline() == (
        "signal_monitor",
        "proposal_drafter",
        "impact_analyzer",
        "compensation_framer",
        "recursion_guard",
        "packaging_and_handoff",
    )
    assert EVOLUTION_PIPELINE[-1] == "packaging_and_handoff", "the pipeline ends at handoff, not at adoption"


def test_a4_is_human_only() -> None:
    """19.36.2 — A4 authority is bound to human credentials and undelegable."""
    assert ArtifactClass.A4_CONSTITUTIONAL.is_human_only
    assert not ArtifactClass.A3_STRUCTURAL.is_human_only


def test_a_rejected_proposal_has_a_terminal_state_that_preserves_history() -> None:
    """21B §26.8 — the outcome is appended, not the record mutated or deleted."""
    assert ProposalState.REJECTED in set(ProposalState)
    assert ProposalState.ABANDONED in set(ProposalState)


def test_evolution_health_reports_the_block_rather_than_raising(evolution: EvolutionGateway) -> None:
    health = evolution.health()
    assert health["status"] == "specification-conformant, construction-blocked"
    assert health["construction_authorized"] is False
    assert health["ratification_authority"] == "governance_gateway"


def test_the_evolution_blocker_is_quoted(evolution: EvolutionGateway) -> None:
    assert "CIR-001" in evolution.blocker()
    assert "third of the three subsystems" in evolution.blocker()


# ============================================ Plugin Manager (not blocked)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def plugins(clock: Clock) -> PluginManager:
    return PluginManager(is_human=is_human, now=clock)


def limits(**overrides: Any) -> ResourceLimits:
    defaults: dict[str, Any] = {
        "max_memory_mb": 512,
        "max_cpu_millicores": 500,
        "max_wall_seconds": 30,
        "egress_allowlist": frozenset({"api.example-shop.test"}),
    }
    defaults.update(overrides)
    return ResourceLimits(**defaults)


def plugin_manifest(plugin_id: str = "plug-shop", **overrides: Any) -> PluginManifest:
    defaults: dict[str, Any] = {
        "plugin_id": plugin_id,
        "name": "Shop Integration",
        "version": "1.2.0",
        "publisher": "third-party-labs",
        "capabilities": frozenset({"catalogue.sync"}),
        "event_subscriptions": frozenset({"order.created"}),
        "requested_permissions": frozenset({"catalogue.read", "catalogue.write"}),
        "resource_limits": limits(),
        "sandbox_tier": SandboxTier.CONTAINER,
        "api_version": "v1",
        "description": "syncs a third-party catalogue",
    }
    defaults.update(overrides)
    return PluginManifest(**defaults)


def enabled(plugins: PluginManager, plugin_id: str = "plug-shop", **overrides: Any) -> Any:
    plugins.discover(plugin_manifest(plugin_id, **overrides))
    plugins.install(plugin_id, HUMAN)
    plugins.grant(plugin_id, HUMAN, frozenset({"catalogue.read"}))
    return plugins.enable(plugin_id, HUMAN)


# ------------------------------------------------- Isolation (02.3.10)


def test_no_sandbox_tier_runs_a_plugin_in_core_process_space() -> None:
    """02.3.10 — "never in core process space".

    An enum member no one can select is a stronger guarantee than a check
    someone can forget, so the value simply does not exist.
    """
    assert "IN_PROCESS" not in {member.name for member in SandboxTier}
    assert all("process" not in member.value for member in SandboxTier)


def test_the_manager_holds_no_verb_that_executes_plugin_code() -> None:
    """The structural half of the same rule.

    A Plugin Manager able to call a plugin directly would have made the
    isolation a convention that the next change could quietly drop.
    """
    assert in_process_execution_verbs() == ()
    forbidden = {"invoke", "call", "execute", "run", "dispatch", "load_module", "import_plugin"}
    present = {name for name in dir(PluginManager) if not name.startswith("_")}
    assert not (forbidden & present), f"the manager acquired a call path into plugin code: {forbidden & present}"
    assert plugins_health_reports_zero_in_process()


def plugins_health_reports_zero_in_process() -> bool:
    manager = PluginManager(is_human=is_human)
    return bool(manager.health()["in_process_plugins"] == 0)


# ------------------------------------------------------ Manifest validation


def test_a_conformant_manifest_is_discovered(plugins: PluginManager) -> None:
    record = plugins.discover(plugin_manifest())
    assert record.state == PluginState.DISCOVERED
    assert record.granted_permissions == frozenset()


def test_a_plugin_without_a_publisher_is_refused() -> None:
    """Third-party code with no attributable author cannot be reviewed."""
    with pytest.raises(ValidationError, match="publisher"):
        validate_manifest(plugin_manifest(publisher="  "))


def test_a_plugin_declaring_no_capabilities_is_refused() -> None:
    with pytest.raises(ValidationError, match="no capabilities"):
        validate_manifest(plugin_manifest(capabilities=frozenset()))


def test_a_plugin_without_an_api_version_is_refused() -> None:
    """01.18.1 — versioned interfaces so an upgrade does not strand it."""
    with pytest.raises(ValidationError, match="API version"):
        validate_manifest(plugin_manifest(api_version=""))


@pytest.mark.parametrize("override", [{"max_memory_mb": 0}, {"max_cpu_millicores": 0}, {"max_wall_seconds": -1}])
def test_an_unbounded_resource_limit_is_refused(override: dict[str, Any]) -> None:
    """01.18.2's sandboxing requirement, as a precondition.

    An unbounded third-party process is exactly the failure the requirement
    exists to prevent.
    """
    with pytest.raises(ValidationError, match="resource limit"):
        validate_manifest(plugin_manifest(resource_limits=limits(**override)))


def test_a_duplicate_plugin_id_is_refused(plugins: PluginManager) -> None:
    plugins.discover(plugin_manifest())
    with pytest.raises(Exception, match="already known"):
        plugins.discover(plugin_manifest())


# --------------------------------------------------------- Permissions


def test_a_plugin_receives_the_intersection_not_its_request(plugins: PluginManager) -> None:
    """14.12.4 at the extension boundary.

    A plugin that received what it asked for would be writing its own
    permissions, which is what the grant step exists to prevent.
    """
    plugins.discover(plugin_manifest())
    plugins.install("plug-shop", HUMAN)
    record = plugins.grant("plug-shop", HUMAN, frozenset({"catalogue.read"}))
    assert record.manifest.requested_permissions == {"catalogue.read", "catalogue.write"}
    assert record.effective_permissions == {"catalogue.read"}


def test_granting_an_undeclared_permission_is_refused(plugins: PluginManager) -> None:
    """The operator and the manifest disagree, and that is worth surfacing."""
    plugins.discover(plugin_manifest())
    plugins.install("plug-shop", HUMAN)
    with pytest.raises(PluginRefused, match="never requested"):
        plugins.grant("plug-shop", HUMAN, frozenset({"secrets.read"}))


def test_a_plugin_cannot_grant_itself_anything(plugins: PluginManager) -> None:
    plugins.discover(plugin_manifest())
    plugins.install("plug-shop", HUMAN)
    with pytest.raises(PluginRefused, match="cannot grant itself"):
        plugins.grant("plug-shop", AGENT, frozenset({"catalogue.read"}))


def test_installing_and_enabling_are_human_acts(plugins: PluginManager) -> None:
    plugins.discover(plugin_manifest())
    with pytest.raises(PluginRefused, match="human act"):
        plugins.install("plug-shop", AGENT)
    plugins.install("plug-shop", HUMAN)
    plugins.grant("plug-shop", HUMAN, frozenset({"catalogue.read"}))
    with pytest.raises(PluginRefused, match="human act"):
        plugins.enable("plug-shop", AGENT)


def test_a_revoked_permission_stops_permitting(plugins: PluginManager) -> None:
    enabled(plugins)
    assert plugins.permits("plug-shop", "catalogue.read")
    plugins.revoke("plug-shop", HUMAN, frozenset({"catalogue.read"}))
    assert not plugins.permits("plug-shop", "catalogue.read")


def test_a_permission_prefix_is_permitted_but_a_sibling_is_not(plugins: PluginManager) -> None:
    enabled(plugins)
    assert plugins.permits("plug-shop", "catalogue.read.items")
    assert not plugins.permits("plug-shop", "catalogue.write")


# ---------------------------------------------------------- Lifecycle


def test_installation_is_not_enablement(plugins: PluginManager) -> None:
    """Mirroring the Tool Registry's registration-is-not-authorization rule."""
    plugins.discover(plugin_manifest())
    record = plugins.install("plug-shop", HUMAN)
    assert record.state == PluginState.INSTALLED
    assert not record.is_active
    assert not plugins.permits("plug-shop", "catalogue.read")


def test_enabling_a_plugin_with_no_effective_permissions_is_refused(plugins: PluginManager) -> None:
    """Running third-party code for no declared purpose is not a useful state."""
    plugins.discover(plugin_manifest())
    plugins.install("plug-shop", HUMAN)
    with pytest.raises(PluginRefused, match="no declared purpose"):
        plugins.enable("plug-shop", HUMAN)


def test_a_disabled_plugin_permits_nothing_though_the_grant_survives(
    plugins: PluginManager,
) -> None:
    """The grant surviving is what makes re-enabling cheap; the state change is
    what makes disabling meaningful."""
    enabled(plugins)
    plugins.disable("plug-shop", HUMAN, reason="under review")
    record = plugins.get("plug-shop")
    assert record.granted_permissions == {"catalogue.read"}
    assert not plugins.permits("plug-shop", "catalogue.read")
    assert plugins.subscribed_events("plug-shop") == frozenset()


def test_an_uninstalled_plugin_loses_its_grants(plugins: PluginManager) -> None:
    enabled(plugins)
    plugins.disable("plug-shop", HUMAN)
    record = plugins.uninstall("plug-shop", HUMAN)
    assert record.granted_permissions == frozenset()
    assert record.state == PluginState.UNINSTALLED


def test_an_enabled_plugin_may_not_jump_straight_to_uninstalled(plugins: PluginManager) -> None:
    """A running extension is disabled before it is removed."""
    enabled(plugins)
    with pytest.raises(Exception):  # noqa: B017 - the kernel machine's own error
        plugins.uninstall("plug-shop", HUMAN)


def test_a_quarantined_plugin_does_not_resume_on_its_own() -> None:
    """It returns only through Disabled, which a human must lift."""
    assert PLUGIN_TRANSITIONS[PluginState.QUARANTINED] == {
        PluginState.DISABLED,
        PluginState.UNINSTALLED,
    }
    assert PluginState.ENABLED not in PLUGIN_TRANSITIONS[PluginState.QUARANTINED]


def test_repeated_failures_quarantine_the_plugin_automatically(plugins: PluginManager) -> None:
    """01.18.2 — plugin quality is outside core control, so the bound is here."""
    enabled(plugins)
    for _ in range(QUARANTINE_MINIMUM_SAMPLE):
        plugins.record_invocation("plug-shop", succeeded=False)
    record = plugins.get("plug-shop")
    assert record.state == PluginState.QUARANTINED
    assert "failure rate" in record.quarantine_reason
    assert not plugins.permits("plug-shop", "catalogue.read")


def test_a_reliable_plugin_is_not_quarantined(plugins: PluginManager) -> None:
    enabled(plugins)
    for succeeded in (True, True, True, False, True, True):
        plugins.record_invocation("plug-shop", succeeded=succeeded)
    assert plugins.get("plug-shop").state == PluginState.ENABLED


def test_a_short_run_of_failures_does_not_quarantine(plugins: PluginManager) -> None:
    """A sample too small to be evidence should not act like evidence."""
    enabled(plugins)
    for _ in range(QUARANTINE_MINIMUM_SAMPLE - 1):
        plugins.record_invocation("plug-shop", succeeded=False)
    assert plugins.get("plug-shop").state == PluginState.ENABLED


def test_an_unknown_plugin_is_a_not_found(plugins: PluginManager) -> None:
    with pytest.raises(NotFoundError):
        plugins.get("plug-nobody")


# ------------------------------------------------------------- Health


def test_health_reports_the_extension_surface(plugins: PluginManager) -> None:
    enabled(plugins)
    plugins.discover(plugin_manifest("plug-other"))
    plugins.record_invocation("plug-shop", succeeded=True)
    health = plugins.health()
    assert health["plugins"] == 2
    assert health["enabled"] == 1
    assert health["quarantined"] == 0
    assert health["in_process_plugins"] == 0
    assert health["failure_rate"] == 0.0
    assert health["journal_intact"]


def test_the_journal_records_the_plugin_lifecycle(plugins: PluginManager) -> None:
    enabled(plugins)
    payloads = [plugins.journal[i].payload for i in range(len(plugins.journal))]
    assert [str(p["action"]) for p in payloads] == ["discovered", "installed", "granted", "enabled"]
