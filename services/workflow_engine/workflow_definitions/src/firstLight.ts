/**
 * The First Light workflow definition (Stage S7, Build Spec exit criterion).
 *
 * `03.3.2` puts workflow *definitions* in this language and `03.3.1` puts
 * activity *implementations* in Python. This file is orchestration only: it
 * declares the DAG and its ordering, and calls nothing. Every activity here is
 * fulfilled by the Python side through the Agent Runtime or the Tool Gateway.
 *
 * `07.13.1`: "The orchestrator does not perform work; it governs work." That
 * is why there is no business logic in this file and no import of anything
 * that could perform work.
 *
 * **Determinism** (07.13.5). This module derives nothing non-deterministic.
 * No `Date.now()`, no `Math.random()`, no I/O. Anything of that kind arrives
 * through `WorkflowContext.variables`, so the same trigger and context
 * reconstruct the same traversal on replay. `determinism.ts` makes that
 * checkable rather than merely intended - it lives in a separate module
 * because a checker must name the constructs it forbids.
 */

import type { ActivityKind, WorkflowContext } from "./contracts.ts";

/** One node in the declared DAG. Mirrors the Python `Activity` dataclass. */
export interface ActivityDefinition {
  readonly activityId: string;
  readonly kind: ActivityKind;
  readonly capability?: string;
  readonly toolId?: string;
  readonly dependsOn: readonly string[];
  /** Whether this activity changes the world. Compensation exists for these. */
  readonly mutating: boolean;
  readonly estimatedCost: number;
  readonly maxRetries: number;
  /** Set on a human gate: the decision class the approval carries. */
  readonly decisionClass?: string;
}

export interface WorkflowDefinition {
  readonly name: string;
  readonly version: string;
  readonly activities: readonly ActivityDefinition[];
}

/**
 * First Light, as the Build Specification's S7 exit criterion words it:
 *
 * > "One registered agent executes one task inside one durable workflow,
 * > invoking one tool through the full mediation chain, with one human
 * > approval gate, one saga compensation path, and complete lineage from
 * > human authority to external effect."
 *
 * The ordering is the point. The human gate precedes the mutating tool call,
 * because a mutating effect must not occur before the human authorizing it has
 * said yes — 11 rule 2 admits no Class C commitment without explicit human
 * approval, and putting the gate after the effect would make the approval
 * ceremonial.
 */
export const firstLight: WorkflowDefinition = {
  name: "first-light",
  version: "1.0.0",
  activities: [
    {
      activityId: "analyse",
      kind: "agent",
      capability: "business.analysis",
      dependsOn: [],
      mutating: false,
      estimatedCost: 0.05,
      maxRetries: 2,
    },
    {
      activityId: "checkpoint-analysed",
      kind: "checkpoint",
      dependsOn: ["analyse"],
      mutating: false,
      estimatedCost: 0,
      maxRetries: 0,
    },
    {
      activityId: "approve-publication",
      kind: "human_gate",
      dependsOn: ["checkpoint-analysed"],
      mutating: false,
      estimatedCost: 0,
      maxRetries: 0,
      decisionClass: "C",
    },
    {
      activityId: "publish",
      kind: "tool",
      toolId: "tool-publish",
      dependsOn: ["approve-publication"],
      mutating: true,
      estimatedCost: 0.1,
      maxRetries: 1,
    },
  ],
};

/**
 * Topological order of the declared DAG.
 *
 * Pure: it reads only the definition. Two calls with the same definition
 * return the same order, which is the determinism property replay depends on.
 */
export function traversalOrder(definition: WorkflowDefinition): string[] {
  const remaining = new Map<string, Set<string>>(
    definition.activities.map((a) => [a.activityId, new Set(a.dependsOn)]),
  );
  const order: string[] = [];

  while (remaining.size > 0) {
    // Sorted, so ties resolve identically on every run rather than by
    // insertion-order accident.
    const ready = [...remaining.entries()]
      .filter(([, deps]) => deps.size === 0)
      .map(([id]) => id)
      .sort();

    if (ready.length === 0) {
      throw new Error(
        `the declared DAG is cyclic; unresolved: ${[...remaining.keys()].sort().join(", ")}`,
      );
    }
    for (const id of ready) {
      order.push(id);
      remaining.delete(id);
      for (const deps of remaining.values()) {
        deps.delete(id);
      }
    }
  }
  return order;
}

/** Every activity a failure would require compensating, newest-first. */
export function compensationOrder(definition: WorkflowDefinition): string[] {
  return traversalOrder(definition)
    .filter((id) => definition.activities.find((a) => a.activityId === id)?.mutating)
    .reverse();
}

/**
 * Asserts the ordering constraint that makes the human gate meaningful.
 *
 * Every mutating activity must depend, transitively, on a human gate. A
 * mutating effect reachable without one would let the workflow change the
 * world before anyone approved it.
 */
export function assertGatedMutations(definition: WorkflowDefinition): void {
  const byId = new Map(definition.activities.map((a) => [a.activityId, a]));

  const reachesGate = (id: string, seen: Set<string>): boolean => {
    if (seen.has(id)) return false;
    seen.add(id);
    const activity = byId.get(id);
    if (activity === undefined) return false;
    if (activity.kind === "human_gate") return true;
    return activity.dependsOn.some((dep) => reachesGate(dep, seen));
  };

  for (const activity of definition.activities) {
    if (!activity.mutating) continue;
    if (!reachesGate(activity.activityId, new Set())) {
      throw new Error(
        `mutating activity '${activity.activityId}' is reachable without a human approval gate; ` +
          `a mutating effect must not precede the approval that authorizes it (11 rule 2)`,
      );
    }
  }
}

/** Reads the non-deterministic inputs a workflow was explicitly given. */
export function variable(context: WorkflowContext, name: string): string {
  const value = context.variables[name];
  if (value === undefined) {
    throw new Error(
      `workflow variable '${name}' was not supplied; non-deterministic inputs must be injected ` +
        `explicitly and never derived inside orchestration logic (07.13.5)`,
    );
  }
  return value;
}
