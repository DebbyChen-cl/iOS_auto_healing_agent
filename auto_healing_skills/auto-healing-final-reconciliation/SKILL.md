---
name: auto-healing-final-reconciliation
description: "Use when: reconciling PHD iOS Auto-Healing final case/run status after original failure, retry, recovery, healing, replay, manual review, blocked_by_upstream, pass_with_healing, or pass_after statuses."
argument-hint: "Original result, retry result, healing/replay result, review decision, or run summary."
user-invocable: true
---

# Auto-Healing Final Reconciliation Gate

Source SPECs: `retry_policy_spec.md`, `previous_result_history_spec.md`, `metrics_spec.md`, `pr_generation_rule_spec.md`

## Purpose

Preserve the original result and assign the correct final status after retry, healing, replay, or manual routing.

## Required Inputs

- Original test runner result.
- Retry/recovery result when applicable.
- Healing/replay result when applicable.
- Failure type and root cause.
- Review status when available.
- Dependency/upstream impact when applicable.

## Procedure

1. Preserve original failure; do not overwrite it with healing or retry pass.
2. Assign final status using status counting rules.
3. Ensure `pass_with_healing` and `pass_after_*` are not counted as ordinary pass.
4. Mark product bug, infra issue, flaky signal, manual review, and evidence gaps as quality signals.
5. Prepare lightweight history record and run-level summary.

## Completion Output

Return:

```text
Gate: final_reconciliation
Original status: <status>
Final status: <status>
Quality signal preserved: <true/false>
History update required: <true/false>
Next gate: html_report_approval
```