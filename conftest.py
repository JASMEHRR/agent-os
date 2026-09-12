"""Adds the Layer 0 substrate libs to sys.path for the Synthetic Gateway
conformance suite, mirroring what `poetry install` (workspace deps) would
wire up once each lib has its own virtualenv."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
for lib in (
    "libs/kernel",
    "libs/core",
    "libs/persistence",
    "services/schema_registry",
    "services/security_gateway",
    "services/event_bus",
    "services/observability_gateway",
    "services/cost_manager",
    "services/memory_gateway",
    "services/knowledge_gateway",
    "services/decision_gateway",
    "services/tool_registry",
    "services/tool_gateway",
    "services/tool_executor",
    "services/llm_router",
    "services/integration_registry",
    "services/integration_gateway",
    "services/agent_runtime",
    "services/workflow_engine",
    "services/api_gateway",
    "services/human_interface",
    "services/learning_gateway",
    "services/governance_gateway",
    "services/deployment_registry",
    "services/deployment_gateway",
    "services/evolution_gateway",
    "services/plugin_manager",
    "services/content_agent",
    "services/inbox_agent",
):
    sys.path.insert(0, str(ROOT / lib))
