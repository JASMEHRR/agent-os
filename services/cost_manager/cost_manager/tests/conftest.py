"""Fixtures for the Cost Manager suite."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from cost_manager import BudgetScope, CostManager, ScopeKind
from kernel.signals import Signal, SignalEmitter

TENANT = "tenant-alpha"
AGENT = "agent-writer"
AGENT_SCOPE = BudgetScope(kind=ScopeKind.AGENT, identifier=AGENT)


class Clock:
    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class EscalationSink:
    """The human-escalation path. At Stage S3 no Human Interface exists yet."""

    def __init__(self) -> None:
        self.escalations: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, kind: str, detail: dict[str, Any]) -> None:
        self.escalations.append((kind, detail))

    def of_kind(self, kind: str) -> list[dict[str, Any]]:
        return [detail for k, detail in self.escalations if k == kind]


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def signals() -> list[Signal]:
    return []


@pytest.fixture
def escalations() -> EscalationSink:
    return EscalationSink()


@pytest.fixture
def costs(clock: Clock, signals: list[Signal], escalations: EscalationSink) -> CostManager:
    return CostManager(
        signals=SignalEmitter(source_identity="cost_manager", sink=signals.append),
        escalate=escalations,
        now=clock,
    )


def names(signals: list[Signal]) -> list[str]:
    return [s.name for s in signals]
