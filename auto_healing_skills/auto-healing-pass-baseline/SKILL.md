---
name: auto-healing-pass-baseline
description: "Use when: deciding whether PHD iOS Auto-Healing needs trusted pass baseline, looking up step-level baseline, comparing fail step previous 5-step window, or marking missing/stale baseline."
argument-hint: "Stable Case ID, fail step id/order, failure reason candidate, or baseline path."
user-invocable: true
---

# Auto-Healing Pass Baseline Gate

Source SPEC: `Self-healing/SPEC/auto_healing_gate_io_spec/pass_baseline_retention_spec.md`

## Purpose

Load trusted step-level pass baseline only when needed to compare normal flow near a failure.

## Required Inputs

- Stable Case ID.
- Fail step id/key and step order.
- Failure reason candidate.
- Current app version/build, branch, device, and iOS version.

## Baseline Needed For

- Workflow / micro-flow change.
- Locator drift.
- Page object drift.
- Readiness / wait drift when state comparison is needed.
- Assertion failure symptom only when root cause points to workflow, locator, or wait.

## Procedure

1. Decide if the failure reason needs baseline.
2. Query by Stable Case ID + Step ID / Step Key.
3. Load at most the fail step inclusive previous 5-step window.
4. Prefer same app version/build trusted pass baseline.
5. Mark missing, stale, or incompatible baseline when no safe source exists.

## Forbidden

- Do not save full video or full raw logs as baseline.
- Do not use retry pass or unreviewed healing pass as trusted baseline.
- Do not use baseline to justify changing assertions or expected values.

## Completion Output

Return:

```text
Gate: pass_baseline_retention
Baseline needed: <true/false>
Baseline source: <path/run id or none>
Step window: <steps>
Baseline gap: <true/false>
Next gate: failure_taxonomy
```