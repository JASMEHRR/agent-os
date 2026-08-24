/**
 * Determinism checking for workflow definitions (07.13.5, 21B 14.4).
 *
 * This lives outside the workflow definitions it checks, and deliberately so:
 * the checker has to *name* the constructs it forbids, and a checker sitting
 * inside the orchestration source would trip its own rule. Keeping it separate
 * means the orchestration modules can be scanned honestly.
 *
 * 21B 14.4 calls determinism "the single most easily violated constraint in
 * the engine", which is why this is a mechanical check rather than a review
 * note: intent does not survive a busy afternoon.
 */

/** Constructs orchestration logic must never derive. */
export const FORBIDDEN_PATTERNS: readonly string[] = [
  "Date.now(",
  "Math.random(",
  "new Date(",
  "process.env",
  "fetch(",
];

/** Constructs that would mean the orchestrator is performing work (07.13.1). */
export const FORBIDDEN_IMPORTS: readonly string[] = [
  "require(",
  "child_process",
  "node:fs",
  "node:http",
];

/** Returns every forbidden construct found in the given source. */
export function scan(source: string, patterns: readonly string[]): string[] {
  return patterns.filter((pattern) => source.includes(pattern));
}
