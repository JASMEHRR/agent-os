// GENERATED FILE - DO NOT EDIT BY HAND.
//
// Emitted from services/workflow_engine/workflow_engine/schema.py, which is
// the single source of truth for the bilingual boundary (21A 9.4.5). Python
// defines the activity contracts; this file is generated from them; and a
// contract test asserts the two still agree. Editing this file by hand would
// break that guarantee silently, which is exactly the failure 21B 14.4 warns
// about.

export type WorkflowState =
  | "triggered"
  | "planning"
  | "running"
  | "paused"
  | "compensating"
  | "completed"
  | "failed"
  | "stalled"
  | "cancelled";

export type ActivityKind =
  | "agent"
  | "tool"
  | "human_gate"
  | "checkpoint";

export type ActivityState =
  | "pending"
  | "dispatched"
  | "succeeded"
  | "failed"
  | "compensated"
  | "skipped";

/** Everything the workflow was given, including its non-determinism (07.13.5). */
export interface WorkflowContext {
  workflowId: string;
  tenantId: string;
  trigger: string;
  triggeredBy: string;
  variables: Record<string, string>;
  version: number;
}

/** One activity dispatched to the Agent Runtime (21B 13.5). */
export interface ActivityRequest {
  activityId: string;
  workflowId: string;
  agentId: string;
  tenantId: string;
  idempotencyKey: string;
  inputs: Record<string, string>;
  decisionId: string;
  costCeiling: number;
}

/** The structured result the Workflow Engine receives back. */
export interface ActivityOutcome {
  activityId: string;
  agentId: string;
  succeeded: boolean;
  output: Record<string, unknown> | null;
  cost: number;
  toolCalls: number;
  durationSeconds: number;
  outputValid: boolean;
  degraded: boolean;
}
