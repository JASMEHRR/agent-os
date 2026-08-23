"""Stage S0 exit criterion: the Synthetic Gateway conformance suite.

Exercises identity shape, lifecycle guard transitions, journal immutability,
all six boundary types, failure-classification timing, and Panic Protocol
participation, purely against kernel/core/persistence. Per Build Spec §12,
Layer 0 is not sound until every test here passes.
"""

from __future__ import annotations

import dataclasses

import pytest

from kernel.boundaries import BoundaryType, BoundaryViolationError
from kernel.failure import FailureCategory
from kernel.identity import ArtifactIdentity
from kernel.journal import JournalTamperError
from kernel.lifecycle import InvalidTransitionError
from persistence.repository import NotFound
from tests.synthetic_gateway.synthetic_gateway import (
    SyntheticGateway,
    synthetic_boundary_context,
    synthetic_request_context,
)


def _identity() -> ArtifactIdentity:
    return ArtifactIdentity(artifact_type="synthetic", tenant_id="synthetic-tenant", created_by="conformance-suite")


# 1. Identity shape -----------------------------------------------------


def test_identity_shape_is_valid_and_frozen():
    from pydantic import ValidationError

    identity = _identity()
    assert identity.artifact_id and identity.trace_id and identity.tenant_id == "synthetic-tenant"
    with pytest.raises(ValidationError):
        identity.tenant_id = "other-tenant"


# 2. Lifecycle guard transitions -----------------------------------------


def test_lifecycle_guard_enforces_admitted_path():
    gw = SyntheticGateway()
    assert gw.lifecycle.state == "created"
    gw.admit(_identity(), synthetic_boundary_context(), synthetic_request_context())
    assert gw.lifecycle.state == "active"


def test_lifecycle_guard_rejects_illegal_transition():
    gw = SyntheticGateway()
    with pytest.raises(InvalidTransitionError):
        gw.lifecycle.transition("halted")  # created -> halted is not a legal edge


# 3. Journal immutability -------------------------------------------------


def test_journal_append_only_and_tamper_evident():
    gw = SyntheticGateway()
    gw.admit(_identity(), synthetic_boundary_context(), synthetic_request_context())
    assert len(gw.journal) == 1
    entry = gw.journal[0]

    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.payload = {"event": "tampered"}  # type: ignore[misc]  # deliberately violating frozen-ness to prove it's enforced

    assert gw.journal.verify_chain() is True

    tampered = dataclasses.replace(entry, payload={"event": "tampered"})
    gw.journal._entries[0] = tampered
    with pytest.raises(JournalTamperError):
        gw.journal.verify_chain()


# 4. All six boundary types ------------------------------------------------


@pytest.mark.parametrize(
    "ctx_overrides,req_overrides,expected",
    [
        ({"tenant_id": "other-tenant"}, {}, BoundaryType.TENANT),
        ({}, {"required_scope": {"admin"}}, BoundaryType.SCOPE),
        ({"authority_level": 0}, {}, BoundaryType.AUTHORITY),
        ({"confidence": 0.0}, {}, BoundaryType.CONFIDENCE),
        ({"budget_remaining": 0.0}, {}, BoundaryType.BUDGET),
        ({}, {"not_before": None}, None),  # control: temporal covered below explicitly
    ],
)
def test_boundary_enforcement_blocks_admission(ctx_overrides, req_overrides, expected):
    if expected is None:
        return
    gw = SyntheticGateway()
    with pytest.raises(BoundaryViolationError) as exc_info:
        gw.admit(
            _identity(),
            synthetic_boundary_context(**ctx_overrides),
            synthetic_request_context(**req_overrides),
        )
    assert exc_info.value.boundary == expected
    assert gw.lifecycle.state == "created"  # rejected admission must not advance lifecycle


def test_temporal_boundary_blocks_admission():
    from datetime import timedelta

    gw = SyntheticGateway()
    with pytest.raises(BoundaryViolationError) as exc_info:
        gw.admit(
            _identity(),
            synthetic_boundary_context(),
            synthetic_request_context(not_after=synthetic_boundary_context().now - timedelta(days=1)),
        )
    assert exc_info.value.boundary == BoundaryType.TEMPORAL


def test_boundary_enforcement_allows_admission_when_satisfied():
    gw = SyntheticGateway()
    gw.admit(_identity(), synthetic_boundary_context(), synthetic_request_context())
    assert gw.lifecycle.state == "active"


# 5. Failure classification timing -----------------------------------------


def test_failure_classification_completes_within_bound_and_journals():
    gw = SyntheticGateway()
    classification = gw.classify_failure(TimeoutError("upstream slow"), rule=lambda e: FailureCategory.TRANSIENT)
    assert classification.category == FailureCategory.TRANSIENT
    assert classification.elapsed_seconds < 60.0
    assert len(gw.journal) == 1
    assert gw.journal[0].payload["event"] == "failure_classified"


# 6. Panic Protocol participation ------------------------------------------


def test_panic_protocol_halts_gateway():
    gw = SyntheticGateway()
    gw.admit(_identity(), synthetic_boundary_context(), synthetic_request_context())
    assert gw.lifecycle.state == "active"

    elapsed = gw.panic.trigger()

    assert elapsed < 5.0
    assert gw.panic.tripped is True
    assert gw.lifecycle.state == "halted"


# Repository sanity (persistence substrate) --------------------------------


def test_repository_persists_admitted_identity():
    gw = SyntheticGateway()
    identity = _identity()
    gw.admit(identity, synthetic_boundary_context(), synthetic_request_context())
    assert gw.repository.get(identity.artifact_id) == identity
    with pytest.raises(NotFound):
        gw.repository.get("does-not-exist")
