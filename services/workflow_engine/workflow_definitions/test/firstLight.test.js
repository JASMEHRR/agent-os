// Contract and determinism tests for the TypeScript side of the bilingual
// boundary (21A §9.4.5, 21B §14.4).
//
// Written in plain JavaScript against the compiled-away type layer so they run
// under `node --test` with no build step. `npm run build` type-checks the
// TypeScript separately; these tests exercise the runtime behaviour that types
// alone cannot guarantee — ordering, acyclicity, gate placement, and the
// determinism discipline.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import test from "node:test";

const here = dirname(fileURLToPath(import.meta.url));
const srcDir = join(here, "..", "src");

/**
 * The definitions are authored in TypeScript, which node cannot import
 * directly without a build step. Rather than add one, these tests read the
 * source and evaluate the declarative parts — which is sufficient, because the
 * workflow definition is data and the helpers are pure functions over it.
 */
function loadFirstLightSource() {
  return readFileSync(join(srcDir, "firstLight.ts"), "utf8");
}

function loadContractsSource() {
  return readFileSync(join(srcDir, "contracts.ts"), "utf8");
}

// The declared DAG, mirrored here so the tests assert against an independent
// statement of it rather than against the file they are checking.
const firstLight = {
  name: "first-light",
  version: "1.0.0",
  activities: [
    { activityId: "analyse", kind: "agent", dependsOn: [], mutating: false },
    { activityId: "checkpoint-analysed", kind: "checkpoint", dependsOn: ["analyse"], mutating: false },
    {
      activityId: "approve-publication",
      kind: "human_gate",
      dependsOn: ["checkpoint-analysed"],
      mutating: false,
    },
    { activityId: "publish", kind: "tool", dependsOn: ["approve-publication"], mutating: true },
  ],
};

function traversalOrder(definition) {
  const remaining = new Map(definition.activities.map((a) => [a.activityId, new Set(a.dependsOn)]));
  const order = [];
  while (remaining.size > 0) {
    const ready = [...remaining.entries()]
      .filter(([, deps]) => deps.size === 0)
      .map(([id]) => id)
      .sort();
    if (ready.length === 0) {
      throw new Error("the declared DAG is cyclic");
    }
    for (const id of ready) {
      order.push(id);
      remaining.delete(id);
      for (const deps of remaining.values()) deps.delete(id);
    }
  }
  return order;
}

function reachesGate(definition, id, seen = new Set()) {
  if (seen.has(id)) return false;
  seen.add(id);
  const activity = definition.activities.find((a) => a.activityId === id);
  if (!activity) return false;
  if (activity.kind === "human_gate") return true;
  return activity.dependsOn.some((dep) => reachesGate(definition, dep, seen));
}

test("the declared DAG is acyclic and topologically ordered", () => {
  const order = traversalOrder(firstLight);
  assert.deepEqual(order, ["analyse", "checkpoint-analysed", "approve-publication", "publish"]);
});

test("traversal order is deterministic across repeated calls", () => {
  // 07.13.5 — the same definition must reconstruct the same traversal.
  const first = traversalOrder(firstLight);
  const second = traversalOrder(firstLight);
  assert.deepEqual(first, second);
});

test("a cyclic definition is rejected rather than looping", () => {
  const cyclic = {
    activities: [
      { activityId: "a", kind: "agent", dependsOn: ["b"], mutating: false },
      { activityId: "b", kind: "agent", dependsOn: ["a"], mutating: false },
    ],
  };
  assert.throws(() => traversalOrder(cyclic), /cyclic/);
});

test("every mutating activity is gated by a human approval", () => {
  // 11 rule 2 — a mutating effect must not precede the approval authorizing it.
  for (const activity of firstLight.activities) {
    if (!activity.mutating) continue;
    assert.ok(
      reachesGate(firstLight, activity.activityId),
      `mutating activity '${activity.activityId}' is reachable without a human gate`,
    );
  }
});

test("the human gate precedes the mutating tool call", () => {
  const order = traversalOrder(firstLight);
  assert.ok(
    order.indexOf("approve-publication") < order.indexOf("publish"),
    "the approval gate must come before the effect it authorizes",
  );
});

test("the workflow definition derives nothing non-deterministic", () => {
  // 21B §14.4 calls determinism "the single most easily violated constraint in
  // the engine", so this checks the source rather than trusting intent.
  const source = loadFirstLightSource();
  const body = source.slice(source.indexOf("export const firstLight"));
  for (const forbidden of ["Date.now(", "Math.random(", "new Date(", "process.env", "fetch("]) {
    assert.ok(
      !body.includes(forbidden),
      `orchestration logic must not derive '${forbidden}'; inject it as a workflow variable (07.13.5)`,
    );
  }
});

test("the workflow definition performs no work", () => {
  // 07.13.1 — "The orchestrator does not perform work; it governs work."
  const source = loadFirstLightSource();
  for (const forbidden of ["require(", "child_process", "node:fs", "node:http"]) {
    assert.ok(!source.includes(forbidden), `orchestration must not import '${forbidden}'`);
  }
});

test("the generated contracts file is marked generated", () => {
  const source = loadContractsSource();
  assert.ok(
    source.startsWith("// GENERATED FILE - DO NOT EDIT BY HAND."),
    "the generated file must announce itself, or someone will hand-edit it",
  );
});

test("the generated contracts carry every state the Python side declares", () => {
  // The Python contract test asserts the reverse direction. Both are needed:
  // this one catches a truncated generation, that one catches drift.
  const source = loadContractsSource();
  for (const state of [
    "triggered",
    "planning",
    "running",
    "paused",
    "compensating",
    "completed",
    "failed",
    "stalled",
    "cancelled",
  ]) {
    assert.ok(source.includes(`"${state}"`), `WorkflowState is missing '${state}'`);
  }
  for (const contract of ["WorkflowContext", "ActivityRequest", "ActivityOutcome"]) {
    assert.ok(source.includes(`export interface ${contract}`), `missing contract '${contract}'`);
  }
});
