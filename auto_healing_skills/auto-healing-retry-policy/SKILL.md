---
name: auto-healing-retry-policy
description: "Use when: applying PHD iOS Auto-Healing retry policy, immediate retry, app crash retry, network/server busy retry, generation fail retry, smoke/blocking retry, setup recovery, retry evidence, or pass_after status."
argument-hint: "Retry reason, case status, remaining budget, or failed case command."
user-invocable: true
---

# Auto-Healing Retry Policy Gate

Source SPEC: `Self-healing/SPEC/auto_healing_gate_io_spec/retry_policy_spec.md`

## Purpose

Run at most one no-code-change retry when policy allows it, then preserve the retry result as a quality signal.

## Required Inputs

- Retry eligibility reason.
- Remaining retry budget.
- Original failure evidence.
- Case selection command or wrapper test name.

## Procedure

1. Confirm the failure type is retry eligible.
2. Confirm retry budget remains.
3. Retry the original case once without modifying code.
4. Save retry count, retry reason, retry result, status after retry, and evidence delta.
5. Route retry failure to taxonomy/healing/manual path according to failure type.

## Forbidden

- Do not change code, locator, assertion, expected value, or test data during retry.
- Do not mark retry pass as ordinary `pass`.
- Do not retry more than once for v1 immediate retry.

## Completion Output

Return:

```text
Gate: retry_policy
Retry executed: <true/false>
Retry count: <0/1>
Retry result: <pass/fail/crash/skipped>
Final retry status: <pass_after_* or failure type>
Evidence delta: <summary>
Next gate: <l3_healing_eligibility/final_reconciliation>
```