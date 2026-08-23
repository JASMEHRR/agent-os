"""Panic Protocol participation hook (21A §5.2 item 8).

Every Gateway registers a halt callback; PanicProtocol.trigger() invokes all
registered callbacks and must complete within the constitutionally mandated
5-second bound (verified end-to-end at Stage S8, exercised here only at the
single-process participation-hook level).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

PANIC_BOUND_SECONDS = 5.0


class PanicBoundExceededError(Exception):
    pass


@dataclass
class PanicProtocol:
    _callbacks: list[Callable[[], None]] = field(default_factory=list, init=False)
    _tripped: bool = field(default=False, init=False)

    def register(self, callback: Callable[[], None]) -> None:
        self._callbacks.append(callback)

    def trigger(self) -> float:
        started = time.monotonic()
        for callback in self._callbacks:
            callback()
        elapsed = time.monotonic() - started
        self._tripped = True
        if elapsed > PANIC_BOUND_SECONDS:
            raise PanicBoundExceededError(f"panic halt took {elapsed:.2f}s, exceeds {PANIC_BOUND_SECONDS}s bound")
        return elapsed

    @property
    def tripped(self) -> bool:
        return self._tripped
