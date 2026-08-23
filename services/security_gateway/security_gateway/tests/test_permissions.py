"""Permission Graph Engine — unit tests for the intersection rule (14.12.4).

14.12.4 is the single most consequential rule in the subsystem, so it gets
the densest coverage: intersection never unions, hierarchy narrows rather
than widens, and an absent source grants nothing.
"""

from __future__ import annotations

import pytest

from core.exceptions import ValidationError
from security_gateway.permissions import (
    PermissionGraphEngine,
    covers,
    intersect,
    intersect_all,
)


def test_covers_follows_the_dotted_hierarchy() -> None:
    assert covers("business.content", "business.content.generate")
    assert covers("business.content", "business.content")
    assert not covers("business.content.generate", "business.content")
    # A prefix that is not a segment boundary must not match.
    assert not covers("business.cont", "business.content")


def test_intersection_is_not_union() -> None:
    left = {"tool.invoke", "memory.read"}
    right = {"tool.invoke", "decision.commit"}
    assert intersect(left, right) == frozenset({"tool.invoke"})


def test_intersection_narrows_to_the_more_specific_grant() -> None:
    broad = {"business.content"}
    narrow = {"business.content.generate.blog_post"}
    assert intersect(broad, narrow) == frozenset({"business.content.generate.blog_post"})


def test_a_standing_order_cannot_expand_past_a_role() -> None:
    role = {"business.content.generate"}
    standing_order = {"business.content.publish", "business.content.generate"}
    assert intersect_all([role, standing_order]) == frozenset({"business.content.generate"})


def test_no_applicable_source_grants_nothing() -> None:
    assert intersect_all([]) == frozenset()


def test_graph_recomputes_on_every_input_change() -> None:
    engine = PermissionGraphEngine()
    engine.set_source("p", "capabilities", {"tool.invoke", "memory.read"})
    graph = engine.set_source("p", "roles", {"tool.invoke"})
    assert graph.effective == frozenset({"tool.invoke"})
    assert graph.revision == 1
    assert graph.permits("tool.invoke")
    assert not graph.permits("memory.read")


def test_historical_graphs_are_archived_for_forensic_reconstruction() -> None:
    engine = PermissionGraphEngine()
    engine.set_source("p", "capabilities", {"a", "b"})
    engine.set_source("p", "capabilities", {"a"})
    history = engine.history_for("p")
    assert len(history) == 1
    assert history[0].effective == frozenset({"a", "b"})


def test_unknown_graph_input_is_rejected() -> None:
    engine = PermissionGraphEngine()
    with pytest.raises(ValidationError, match="not a permission graph input"):
        engine.set_source("p", "vibes", {"a"})


def test_child_task_inherits_only_the_intersection(gateway_free_engine: PermissionGraphEngine) -> None:
    engine = gateway_free_engine
    engine.set_source("parent", "capabilities", {"tool.x", "tool.y", "tool.z"})
    child = engine.inherit("parent", "child", {"tool.x", "tool.w"})
    assert child.effective == frozenset({"tool.x"})


def test_child_cannot_hold_permissions_its_parent_lacks() -> None:
    engine = PermissionGraphEngine()
    engine.set_source("parent", "capabilities", {"tool.x"})
    child = engine.inherit("parent", "child", {"tool.x", "admin.everything"})
    assert "admin.everything" not in child.effective


def test_unknown_principal_has_an_empty_graph_not_a_permissive_one() -> None:
    engine = PermissionGraphEngine()
    graph = engine.graph_for("never-seen")
    assert graph.effective == frozenset()
    assert not graph.permits("anything")


@pytest.fixture
def gateway_free_engine() -> PermissionGraphEngine:
    return PermissionGraphEngine()
