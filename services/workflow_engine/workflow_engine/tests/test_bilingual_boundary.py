"""Contract tests for the bilingual boundary (21A §9.4.5, 21B §14.4).

21B §14.4 names this the engine's highest-risk internal seam:

> "Neither language's type system observes both sides, so the boundary is the
> engine's highest-risk internal seam."

21A §9.4.5 prescribes single-source schema generation plus mandatory contract
tests. These are the Python half of those tests; `workflow_definitions/test/`
holds the TypeScript half. Both directions are needed — this one catches the
generated file drifting behind Python, that one catches a truncated
generation.

The critical test here is `test_the_generated_file_matches_the_generator`:
without it, someone edits `contracts.ts` by hand, the two sides diverge
silently, and the failure surfaces at runtime in a language neither type
checker was watching.
"""

from __future__ import annotations

import pathlib

import pytest

from workflow_engine.dag import ActivityKind, ActivityState, WorkflowState
from workflow_engine.schema import CONTRACTS, ENUMS, contract_names, render_typescript

GENERATED = pathlib.Path(__file__).resolve().parents[2] / "workflow_definitions" / "src" / "contracts.ts"


def test_the_generated_file_exists() -> None:
    assert GENERATED.exists(), "contracts.ts has not been generated; run the generator in workflow_engine.schema"


def test_the_generated_file_matches_the_generator() -> None:
    """The whole point of single-source generation.

    If this fails, the TypeScript side has drifted from Python — either
    because someone hand-edited the generated file, or because a contract
    changed and generation was not re-run. Either way the boundary is no
    longer single-source and the seam is unguarded.
    """
    on_disk = GENERATED.read_text(encoding="utf-8")
    expected = render_typescript()
    assert on_disk == expected, (
        "contracts.ts differs from what workflow_engine.schema would generate. "
        "Regenerate it rather than editing it by hand."
    )


def test_the_generated_file_warns_against_hand_editing() -> None:
    assert GENERATED.read_text(encoding="utf-8").startswith("// GENERATED FILE - DO NOT EDIT BY HAND.")


# ------------------------------------------------- enums agree across the seam


def test_workflow_states_agree_with_the_python_enum() -> None:
    """A TypeScript workflow must not branch on a state Python never produces."""
    assert set(ENUMS["WorkflowState"]) == {state.value for state in WorkflowState}


def test_activity_kinds_agree_with_the_python_enum() -> None:
    assert set(ENUMS["ActivityKind"]) == {kind.value for kind in ActivityKind}


def test_activity_states_agree_with_the_python_enum() -> None:
    assert set(ENUMS["ActivityState"]) == {state.value for state in ActivityState}


@pytest.mark.parametrize("name", list(ENUMS))
def test_every_enum_member_reaches_the_generated_file(name: str) -> None:
    generated = GENERATED.read_text(encoding="utf-8")
    for member in ENUMS[name]:
        assert f'"{member}"' in generated, f"{name} is missing '{member}' in the generated file"


# --------------------------------------------- contracts reach the other side


@pytest.mark.parametrize("contract", list(contract_names()))
def test_every_contract_is_declared_in_the_generated_file(contract: str) -> None:
    assert f"export interface {contract}" in GENERATED.read_text(encoding="utf-8")


def test_every_contract_field_reaches_the_generated_file() -> None:
    generated = GENERATED.read_text(encoding="utf-8")
    for contract in CONTRACTS:
        for field in contract.fields:
            assert f"{field.name}" in generated, f"{contract.name}.{field.name} did not reach the generated file"


def test_the_activity_outcome_contract_covers_what_python_returns() -> None:
    """The seam's most consequential contract.

    `ActivityOutcome` is what crosses back from a Python activity into
    TypeScript orchestration. A field Python returns but TypeScript cannot see
    is invisible to the orchestrator, which would make it unable to branch on
    something that actually happened.
    """
    outcome = next(c for c in CONTRACTS if c.name == "ActivityOutcome")
    declared = {f.name for f in outcome.fields}
    # The camelCase mirror of the Python `ActivityOutcome` fields the
    # orchestrator needs to make decisions.
    required = {
        "activityId",
        "agentId",
        "succeeded",
        "output",
        "cost",
        "toolCalls",
        "durationSeconds",
        "outputValid",
        "degraded",
    }
    assert required <= declared


def test_field_names_are_camel_case_on_the_typescript_side() -> None:
    """The boundary translates naming convention as well as type.

    Python is snake_case and TypeScript is camelCase. Emitting snake_case into
    TypeScript would work but read as foreign, and a convention violated
    inconsistently is worse than either convention held.
    """
    for contract in CONTRACTS:
        for field in contract.fields:
            assert "_" not in field.name, (
                f"{contract.name}.{field.name} is snake_case; the TypeScript side is camelCase"
            )


# --------------------------------------- the TypeScript definition is mirrored


def test_the_python_first_light_mirrors_the_typescript_definition() -> None:
    """Both sides declare the same DAG, and the mirror is checked.

    The TypeScript file is the authored definition per 03.3.2; the Python
    fixture mirrors it so the activity side can be exercised. A drifted mirror
    would mean the tested workflow is not the declared one.
    """
    definition_source = (GENERATED.parent / "firstLight.ts").read_text(encoding="utf-8")

    for activity_id in ("analyse", "checkpoint-analysed", "approve-publication", "publish"):
        assert f'activityId: "{activity_id}"' in definition_source

    # The ordering constraint that makes the gate meaningful: the mutating
    # activity depends on the human gate.
    publish_block = definition_source[definition_source.index('activityId: "publish"') :]
    assert 'dependsOn: ["approve-publication"]' in publish_block
    assert "mutating: true" in publish_block
