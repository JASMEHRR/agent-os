"""Deployment Gateway - specification-conformant, construction-blocked (21B 25).

`18.6.2`: "The Gateway is the sole constitutional path between operational
intent and environmental existence. No runtime instance may exist in an
environment without Gateway mediation."

While CIR-001 blocks construction there is no such path, which means every
runtime instance in this system runs in no registered environment. That is the
honest downstream consequence, and `unbacked_environments` states it.
"""

from deployment_gateway.gateway import (
    PROMOTION_GATES,
    PROMOTION_SEQUENCE,
    DeploymentGateway,
    unbacked_environments,
)

__all__ = [
    "DeploymentGateway",
    "PROMOTION_SEQUENCE",
    "PROMOTION_GATES",
    "unbacked_environments",
]
