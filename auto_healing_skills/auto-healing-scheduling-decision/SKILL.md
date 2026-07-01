---
name: auto-healing-scheduling-decision
description: "Use when: deciding PHD iOS Auto-Healing immediate vs deferred lane, crash handling, retry/recovery, deferred healing queue, manual path, device availability, or immediate budget."
argument-hint: "Failure type, priority, blocking type, history summary, evidence completeness, and device budget."
user-invocable: true
---

# Auto-Healing Scheduling Decision Gate

Source SPEC: `Self-healing/SPEC/auto_healing_gate_io_spec/immediate_vs_deferred_policy_spec.md`

## Purpose

Route a failure to the correct lane while protecting the single iOS device from unnecessary immediate work.

## Required Inputs

- Failure type.
- Stable Case ID.
- Priority.
- Blocking type.
- Previous result history.
- Failure evidence.
- Device availability.
- Remaining immediate budget.

## Lanes

- Lane A: immediate crash / infrastructure handling.
- Lane B: immediate retry / recovery.
- Lane C: deferred healing after full AT run.
- Lane D: no healing / manual path.

## Procedure

1. Check crash/infra signals first.
2. Check retry/recovery eligibility for network/server busy, smoke, blocking, setup, or dependency root failure.
3. Route locator/page object/wait/micro-flow/compare analysis to deferred unless blocking policy says otherwise.
4. Route product bug, assertion logic change, major workflow change, insufficient evidence, or low-confidence unclassified failure to manual/no-healing.
5. Enforce immediate retry limit of once per case.

## Completion Output

Return:

```text
Gate: immediate_vs_deferred_policy
Lane: <A/B/C/D>
Action: <rerun/recovery/deferred_healing/manual_review/no_healing>
Rerun allowed: <yes/no>
Rerun count limit: <0/1>
Reason: <reason>
Next gate: <retry_policy/l3_healing_eligibility/final_reconciliation>
```