---
name: auto-healing-failure-evidence
description: "Use when: collecting or validating raw PHD iOS Auto-Healing failure evidence, fail screenshot, fail hierarchy, step evidence, stack trace, metadata, network/app/device/dependency/retry evidence, or evidence gaps."
argument-hint: "Evidence folder path, failed case name, pytest report, or run context."
user-invocable: true
---

# Auto-Healing Failure Evidence Gate

Source SPEC: `Self-healing/SPEC/auto_healing_gate_io_spec/failure_evidence_collection_spec.md`

## Purpose

Save raw failure evidence at the moment a case fails. This gate supports later analysis and report review, but it must not perform root-cause analysis.

## Required Inputs

- Stable Case ID and Run ID, or explicit gaps.
- Branch, commit, app version, device, iOS version, environment.
- Fail step id/order/action, test line/function.
- Error message, stack trace, assertion message, exception type, timeout info.
- Fail screenshot and fail hierarchy.
- Step before/after screenshot and hierarchy.

## Conditional Inputs

- Network/server busy evidence when signaled.
- App/device crash evidence when signaled.
- Dependency/setup evidence when setup or upstream dependency fails.
- Retry evidence when retry has occurred.

## Procedure

1. Save evidence under `Self-healing/evidence/<timestamp>-<testcasename>/`.
2. Store `metadata.json`, stack trace, fail screenshot, fail hierarchy, and per-step artifacts.
3. Record collection errors and evidence gaps explicitly.
4. Do not classify the failure or suggest fixes in this gate.

## Forbidden

- Do not perform root-cause analysis.
- Do not patch test code.
- Do not hide missing evidence.

## Completion Output

Return:

```text
Gate: failure_evidence_collection
Evidence folder: <path>
Required evidence complete: <true/false>
Evidence gaps: <list>
Manual review required for evidence gap: <true/false>
Next gate: previous_result_history
```