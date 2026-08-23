"""Permission Graph Engine (21B §22.3, realizes 14.11 / 14.12).

The single most consequential rule in the subsystem lives here: 14.12.4 —
"When multiple permission sources apply to a principal, the effective
permission is the intersection, not the union, of all sources."

Permissions are dotted, hierarchical strings (14.11.1): `business.content`
is a parent of `business.content.generate.blog_post`. Intersecting a broad
grant with a narrow one yields the *narrow* one — that is what makes a
standing order incapable of expanding past its role, and a role incapable of
expanding past its capability signature.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from core.exceptions import ValidationError

#: Names of the permission-graph inputs enumerated in 14.12.2.
GRAPH_INPUTS = ("capabilities", "roles", "delegations", "standing_orders", "workspace_grants")


def covers(grant: str, requested: str) -> bool:
    """True when `grant` authorizes `requested` under the 14.11.1 hierarchy."""
    return requested == grant or requested.startswith(f"{grant}.")


def intersect(left: Iterable[str], right: Iterable[str]) -> frozenset[str]:
    """Hierarchy-aware intersection of two permission sets (14.12.4).

    For each pair where one side covers the other, the *more specific* side
    survives. Nothing survives that is not covered by both sides, so the
    result can never exceed either input.
    """
    left_set, right_set = set(left), set(right)
    result: set[str] = set()
    for a in left_set:
        for b in right_set:
            if covers(a, b):
                result.add(b)
            elif covers(b, a):
                result.add(a)
    return frozenset(result)


def intersect_all(sources: Iterable[Iterable[str]]) -> frozenset[str]:
    """Folds `intersect` across every applicable source.

    An empty source list means no source applies, which is *no permission* —
    never "all permissions". Deny-by-default is the isolation guarantee of
    21B §22.15 item 4 rendered in code.
    """
    materialized = [frozenset(s) for s in sources]
    if not materialized:
        return frozenset()
    effective = materialized[0]
    for source in materialized[1:]:
        effective = intersect(effective, source)
    return effective


@dataclass(frozen=True)
class PermissionGraph:
    """A principal's effective permissions plus the inputs they derive from.

    Archived rather than mutated on change, so 14.12.5's forensic
    reconstruction — "what was this principal permitted to do at time T" —
    is answerable from the journal.
    """

    principal_id: str
    effective: frozenset[str]
    sources: Mapping[str, frozenset[str]]
    computed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    revision: int = 0

    def permits(self, requested: str) -> bool:
        return any(covers(grant, requested) for grant in self.effective)


class PermissionGraphEngine:
    """Precomputes permission graphs on input change (21B §22.4 Implementation Decision).

    Graphs are recomputed when an input changes rather than derived per
    authorization request, because the Tool Gateway's p50 20ms authorization
    budget cannot accommodate derivation per request. Intersection semantics
    are identical either way; only the timing differs.
    """

    def __init__(self) -> None:
        self._inputs: dict[str, dict[str, frozenset[str]]] = {}
        self._graphs: dict[str, PermissionGraph] = {}
        self._history: dict[str, list[PermissionGraph]] = {}

    def set_source(self, principal_id: str, source: str, permissions: Iterable[str]) -> PermissionGraph:
        """Registers or replaces one graph input, then recomputes (14.12.2)."""
        if source not in GRAPH_INPUTS:
            raise ValidationError(f"'{source}' is not a permission graph input; 14.12.2 names {list(GRAPH_INPUTS)}")
        self._inputs.setdefault(principal_id, {})[source] = frozenset(permissions)
        return self._recompute(principal_id)

    def clear_source(self, principal_id: str, source: str) -> PermissionGraph:
        """Removes an input entirely — e.g. on delegation expiry or role removal."""
        self._inputs.setdefault(principal_id, {}).pop(source, None)
        return self._recompute(principal_id)

    def _recompute(self, principal_id: str) -> PermissionGraph:
        sources = self._inputs.get(principal_id, {})
        previous = self._graphs.get(principal_id)
        graph = PermissionGraph(
            principal_id=principal_id,
            effective=intersect_all(sources.values()),
            sources=dict(sources),
            revision=0 if previous is None else previous.revision + 1,
        )
        if previous is not None:
            self._history.setdefault(principal_id, []).append(previous)
        self._graphs[principal_id] = graph
        return graph

    def graph_for(self, principal_id: str) -> PermissionGraph:
        """The *live* graph — the Authorization Engine reads this, never a token snapshot (14.9.5)."""
        return self._graphs.get(
            principal_id,
            PermissionGraph(principal_id=principal_id, effective=frozenset(), sources={}),
        )

    def history_for(self, principal_id: str) -> tuple[PermissionGraph, ...]:
        """Archived graphs, oldest first (14.12.5)."""
        return tuple(self._history.get(principal_id, ()))

    def drop(self, principal_id: str) -> None:
        """Retires a principal's graph, archiving the live one first (14.8.4 on retirement)."""
        live = self._graphs.pop(principal_id, None)
        if live is not None:
            self._history.setdefault(principal_id, []).append(live)
        self._inputs.pop(principal_id, None)

    def inherit(self, parent_id: str, child_id: str, child_requirements: Iterable[str]) -> PermissionGraph:
        """Child-task permission inheritance (14.12.3).

        The child receives the intersection of the parent's effective
        permissions and its own requirements — never more than the parent
        holds, never more than it asked for.
        """
        parent = self.graph_for(parent_id)
        return self.set_source(child_id, "capabilities", intersect(parent.effective, child_requirements))
