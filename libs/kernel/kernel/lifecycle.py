"""Lifecycle State Machine engine (21A §5.2 item 2).

A generic guarded state machine: every Gateway defines its own state set and
transition table, but the guard-enforcement engine — reject any transition
not explicitly allowed — is shared here so no Gateway reimplements it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class InvalidTransitionError(Exception):
    def __init__(self, current: str, target: str):
        super().__init__(f"Transition '{current}' -> '{target}' is not permitted")
        self.current = current
        self.target = target


@dataclass
class LifecycleStateMachine:
    """Guarded state machine over an explicit transition table.

    transitions: mapping of state -> set of states it may transition to.
    """

    transitions: dict[str, set[str]]
    state: str

    _history: list[str] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if self.state not in self.transitions:
            raise ValueError(f"Unknown initial state '{self.state}'")
        self._history.append(self.state)

    def can_transition(self, target: str) -> bool:
        return target in self.transitions.get(self.state, set())

    def transition(self, target: str) -> None:
        if not self.can_transition(target):
            raise InvalidTransitionError(self.state, target)
        self.state = target
        self._history.append(target)

    @property
    def history(self) -> tuple[str, ...]:
        return tuple(self._history)
