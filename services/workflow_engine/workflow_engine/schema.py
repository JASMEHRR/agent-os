"""Single-source schema generation for the bilingual boundary (21A §9.4.5).

`03.3.1` and `03.3.2` split the Workflow Engine across two runtimes: workflow
definitions in the mandated workflow language, activity implementations in the
mandated service language. 21B §14.4 names the consequence plainly:

> "Neither language's type system observes both sides, so the boundary is the
> engine's highest-risk internal seam."

21A §9.4.5's answer is single-source schema generation plus mandatory contract
tests, and this module is the generator. Python is the source of truth: the
activity contracts are defined here, TypeScript types are emitted from them,
and a contract test asserts the emitted file matches what Python currently
declares. A drifting boundary therefore fails a test rather than failing in
production.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    """One field on an activity contract."""

    name: str
    ts_type: str
    optional: bool = False


@dataclass(frozen=True)
class ContractSpec:
    """One activity contract crossing the language boundary."""

    name: str
    fields: tuple[FieldSpec, ...]
    doc: str


#: The contracts the TypeScript orchestration side must honour. Adding a field
#: here and regenerating is the only supported way to change the boundary.
CONTRACTS: tuple[ContractSpec, ...] = (
    ContractSpec(
        name="WorkflowContext",
        doc="Everything the workflow was given, including its non-determinism (07.13.5).",
        fields=(
            FieldSpec("workflowId", "string"),
            FieldSpec("tenantId", "string"),
            FieldSpec("trigger", "string"),
            FieldSpec("triggeredBy", "string"),
            FieldSpec("variables", "Record<string, string>"),
            FieldSpec("version", "number"),
        ),
    ),
    ContractSpec(
        name="ActivityRequest",
        doc="One activity dispatched to the Agent Runtime (21B 13.5).",
        fields=(
            FieldSpec("activityId", "string"),
            FieldSpec("workflowId", "string"),
            FieldSpec("agentId", "string"),
            FieldSpec("tenantId", "string"),
            FieldSpec("idempotencyKey", "string"),
            FieldSpec("inputs", "Record<string, string>"),
            FieldSpec("decisionId", "string"),
            FieldSpec("costCeiling", "number"),
        ),
    ),
    ContractSpec(
        name="ActivityOutcome",
        doc="The structured result the Workflow Engine receives back.",
        fields=(
            FieldSpec("activityId", "string"),
            FieldSpec("agentId", "string"),
            FieldSpec("succeeded", "boolean"),
            FieldSpec("output", "Record<string, unknown> | null"),
            FieldSpec("cost", "number"),
            FieldSpec("toolCalls", "number"),
            FieldSpec("durationSeconds", "number"),
            FieldSpec("outputValid", "boolean"),
            FieldSpec("degraded", "boolean"),
        ),
    ),
)

#: Enumerations that must agree across the boundary. Drift here would let a
#: TypeScript workflow branch on a state Python never produces.
ENUMS: dict[str, tuple[str, ...]] = {
    "WorkflowState": (
        "triggered",
        "planning",
        "running",
        "paused",
        "compensating",
        "completed",
        "failed",
        "stalled",
        "cancelled",
    ),
    "ActivityKind": ("agent", "tool", "human_gate", "checkpoint"),
    "ActivityState": ("pending", "dispatched", "succeeded", "failed", "compensated", "skipped"),
}

HEADER = (
    "// GENERATED FILE - DO NOT EDIT BY HAND.\n"
    "//\n"
    "// Emitted from services/workflow_engine/workflow_engine/schema.py, which is\n"
    "// the single source of truth for the bilingual boundary (21A 9.4.5). Python\n"
    "// defines the activity contracts; this file is generated from them; and a\n"
    "// contract test asserts the two still agree. Editing this file by hand would\n"
    "// break that guarantee silently, which is exactly the failure 21B 14.4 warns\n"
    "// about.\n"
)


def render_typescript() -> str:
    """Emits the TypeScript declarations for every contract and enum."""
    parts: list[str] = [HEADER]

    for name, members in ENUMS.items():
        union = "\n  | ".join(f'"{member}"' for member in members)
        parts.append(f"export type {name} =\n  | {union};\n")

    for contract in CONTRACTS:
        lines = [f"/** {contract.doc} */", f"export interface {contract.name} {{"]
        for field in contract.fields:
            optional = "?" if field.optional else ""
            lines.append(f"  {field.name}{optional}: {field.ts_type};")
        lines.append("}\n")
        parts.append("\n".join(lines))

    return "\n".join(parts)


def contract_names() -> tuple[str, ...]:
    return tuple(contract.name for contract in CONTRACTS)


def enum_members(name: str) -> tuple[str, ...]:
    return ENUMS[name]
