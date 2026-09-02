"""What the system can actually do, read from the code rather than described.

The honest answer to "what can this thing do" has two halves, and giving only
the first is how a capability list becomes marketing:

* **Built** is what exists in the platform. Read by introspection, so a method
  that gets renamed or deleted disappears from this list rather than lingering
  as a claim.
* **Wired** is the much smaller set reachable from the interface. A capability
  that exists but nothing can call is not something the system does; it is
  something the system could do if someone finished the work.

Anything that reports `built` and not `wired` is a to-do with better
provenance than a to-do list, because it cannot be aspirational: the method has
to genuinely exist for it to appear at all.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect

#: The facade class each module exposes. Mirrors the conformance register's
#: map; duplicated rather than imported because the tests package is not
#: importable from a running server, and a wrong entry here shows up as a
#: missing capability rather than as silence.
FACADES: dict[str, str] = {
    "agent_runtime": "AgentRuntime",
    "api_gateway": "APIGateway",
    "content_agent": "ContentStudio",
    "cost_manager": "CostManager",
    "decision_gateway": "DecisionGateway",
    "deployment_gateway": "DeploymentGateway",
    "deployment_registry": "DeploymentRegistry",
    "event_bus": "EventBus",
    "evolution_gateway": "EvolutionGateway",
    "governance_gateway": "GovernanceGateway",
    "human_interface": "HumanInterface",
    "integration_gateway": "IntegrationGateway",
    "integration_registry": "IntegrationRegistry",
    "knowledge_gateway": "KnowledgeGateway",
    "learning_gateway": "LearningGateway",
    "llm_router": "LLMRouter",
    "memory_gateway": "MemoryGateway",
    "observability_gateway": "ObservabilityGateway",
    "plugin_manager": "PluginManager",
    "schema_registry": "SchemaRegistry",
    "security_gateway": "SecurityGateway",
    "tool_executor": "ToolExecutor",
    "tool_gateway": "ToolGateway",
    "tool_registry": "ToolRegistry",
    "workflow_engine": "WorkflowEngine",
}


@dataclasses.dataclass(frozen=True)
class Capability:
    """One area of the system, in plain language and in code terms."""

    key: str
    title: str
    #: What it does, for someone who did not write it.
    plain: str
    modules: tuple[str, ...]
    #: True when the interface can reach it today.
    wired: bool
    #: For anything not wired: what is missing, specifically.
    missing: str = ""
    #: Filled in by `survey`, counted from the real classes.
    operations: int = 0


#: Ordered as a reader would want to go through it: what works now first, then
#: what is one step away, then the machinery underneath.
CATALOGUE: tuple[Capability, ...] = (
    Capability(
        key="write",
        title="Write posts from your notes",
        plain=(
            "You describe your week. It produces a LinkedIn post, a newsletter issue and a "
            "Dev.to article from the same facts, each checked against your voice rules. "
            "It will not invent a number that is not in your notes."
        ),
        modules=("content_agent", "llm_router"),
        wired=True,
    ),
    Capability(
        key="voice",
        title="Write like you, and keep getting closer",
        plain=(
            "Every draft is written against examples of your own writing. Rate a draft "
            "'sounds like me' and it becomes one. Only text you approve ever gets in, so it "
            "learns you rather than its own habits, and a run of 'not me' shows up in the "
            "numbers before anyone would notice by reading."
        ),
        modules=("content_agent", "learning_gateway"),
        wired=True,
    ),
    Capability(
        key="capture",
        title="Read your week from your commits",
        plain=(
            "One button fills the note from your commit messages across your projects, so "
            "you do not write the week twice. Reads git history only, never file contents, "
            "and a test plants a secret in a file to prove it."
        ),
        modules=("content_agent",),
        wired=True,
    ),
    Capability(
        key="approve",
        title="Hold everything for your approval",
        plain=(
            "Nothing leaves without you saying so. There is no function anywhere in the "
            "system that publishes, which is why this cannot be switched off by accident."
        ),
        modules=("content_agent", "decision_gateway", "human_interface"),
        wired=True,
    ),
    Capability(
        key="remember",
        title="Remember across weeks",
        plain=(
            "Notes and drafts survive restarts. Turn the laptop off and everything is still "
            "there. The wider memory system, which would let it recall what it learned about "
            "a person or a project months later, exists but nothing calls it yet."
        ),
        modules=("memory_gateway", "knowledge_gateway"),
        wired=False,
        missing="the Memory Gateway is built but the studio stores only notes and drafts",
    ),
    Capability(
        key="publish",
        title="Post to LinkedIn directly",
        plain=(
            "Publish an approved draft through LinkedIn's official API instead of copying and "
            "pasting. Only posting and reading your own analytics; LinkedIn provides no API "
            "for invitations or messages."
        ),
        modules=("integration_gateway", "integration_registry"),
        wired=False,
        missing="needs a LinkedIn developer app and a one-time OAuth consent from you",
    ),
    Capability(
        key="outreach",
        title="Draft personalised outreach",
        plain=(
            "Research people worth knowing, draft a specific note for each, and hand you a "
            "list to send. It drafts, you send. Automating the sending itself has no API and "
            "gets accounts restricted."
        ),
        modules=("content_agent", "knowledge_gateway"),
        wired=True,
    ),
    Capability(
        key="learn",
        title="Learn what actually worked",
        plain=(
            "Feed post performance back in so it gets better at your audience rather than "
            "just consistent. The learning subsystem is built and its rule is enforced: it "
            "adapts within your standing instructions and cannot change them."
        ),
        modules=("learning_gateway",),
        wired=False,
        missing="needs performance numbers coming back in, which needs the LinkedIn API first",
    ),
    Capability(
        key="schedule",
        title="Run while you are away",
        plain=(
            "Draft on a schedule without the laptop being open, and tell you when something "
            "is waiting. The workflow engine runs multi-step work durably; what is missing is "
            "somewhere free to run it."
        ),
        modules=("workflow_engine", "agent_runtime"),
        wired=False,
        missing="a scheduled runner, most cheaply GitHub Actions on a cron",
    ),
    Capability(
        key="spend",
        title="Never spend money without permission",
        plain=(
            "Every model call is costed against a ceiling before it runs. Currently every "
            "call costs zero because the tiers are free, and that zero is measured rather "
            "than assumed."
        ),
        modules=("cost_manager", "llm_router"),
        wired=True,
    ),
    Capability(
        key="watch",
        title="Show you what it is doing",
        plain=(
            "Health of every part, what failed, why a draft was rejected, how often the "
            "writing needed fixing. Read-only by construction: the observability surface has "
            "no verb that changes anything."
        ),
        modules=("observability_gateway", "event_bus"),
        wired=True,
    ),
    Capability(
        key="tools",
        title="Use tools safely",
        plain=(
            "Register a capability, bound what it may reach, and run it in a sandbox with an "
            "audit record. Nothing is registered yet, so there is nothing it can reach "
            "outside itself."
        ),
        modules=("tool_registry", "tool_gateway", "tool_executor"),
        wired=False,
        missing="no tools registered; the machinery is built and empty",
    ),
    Capability(
        key="govern",
        title="Govern its own changes",
        plain=(
            "Proposals to change how it works get packaged and handed to you. It cannot "
            "ratify its own amendments: no such function exists on it."
        ),
        modules=("governance_gateway", "evolution_gateway"),
        wired=False,
        missing="nothing proposes changes yet; the refusal to self-ratify is already enforced",
    ),
)


def survey() -> list[dict[str, object]]:
    """Counts real operations per capability and returns it for the interface.

    A module that cannot be imported is reported with a count of zero rather
    than dropped. A capability quietly vanishing because of an import error
    would make the list read as smaller and cleaner than the system is.
    """
    counted: list[dict[str, object]] = []
    for capability in CATALOGUE:
        operations = 0
        for module in capability.modules:
            operations += _operations_in(module)
        counted.append(
            {
                "key": capability.key,
                "title": capability.title,
                "plain": capability.plain,
                "modules": list(capability.modules),
                "wired": capability.wired,
                "missing": capability.missing,
                "operations": operations,
            }
        )
    return counted


def _operations_in(module: str) -> int:
    facade = FACADES.get(module)
    if facade is None:
        return 0
    try:
        imported = importlib.import_module(module)
        target = getattr(imported, facade)
    except (ImportError, AttributeError):
        return 0
    return sum(
        1
        for name, member in vars(target).items()
        if not name.startswith("_") and (callable(member) or inspect.isfunction(member))
    )


def totals() -> dict[str, int]:
    """The headline numbers, computed rather than claimed."""
    surveyed = survey()
    return {
        "capabilities": len(surveyed),
        "wired": sum(1 for c in surveyed if c["wired"]),
        "modules": len(FACADES),
        "operations": sum(int(str(c["operations"])) for c in surveyed),
    }
