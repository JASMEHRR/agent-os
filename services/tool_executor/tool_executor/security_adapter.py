"""Binds the Executor's `SecretAuthority` to the real Security Gateway.

The only module in `tool_executor` importing `security_gateway`, keeping the
permitted edge of 21B 19.6 visible in one file.

21B 19.10: "Secrets never reach tools as values through any path visible to a
consumer." The Security Gateway issues a single-use injection grant; this
adapter redeems it straight into the sandbox. No value crosses back.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from security_gateway import SecurityGateway


@dataclass
class SecurityGatewaySecretAuthority:
    """Implements `tool_executor.executor.SecretAuthority`."""

    gateway: SecurityGateway

    def resolve(self, reference: str, sandbox_id: str, invocation_id: str, requester_id: str) -> Any:
        return self.gateway.resolve_secret_reference(reference, sandbox_id, invocation_id, requester_id)

    def inject(self, grant: Any, injector: Callable[[str, str], None]) -> None:
        self.gateway.secrets.inject(grant, injector)
