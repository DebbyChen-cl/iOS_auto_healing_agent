---
name: auto-healing-l3-eligibility
description: "Use when: deciding PHD iOS Auto-Healing L3 eligibility, blocking impact, healing risk, immediate healing eligibility, low-risk locator/page object/wait/micro-flow repair boundary, or no-healing/manual decision."
argument-hint: "Failure type, root cause, evidence completeness, blocking impact, healing risk, and candidate patch boundary."
user-invocable: true
---

# Auto-Healing L3 Eligibility Gate

Source SPEC: `Self-healing/SPEC/auto_healing_gate_io_spec/l3_healing_eligibility_spec.md`

## Purpose

Decide whether AI may automatically patch, replay, and create a PR for this failure. L3 never means auto-merge.

## Required Inputs

- Failure type and root cause.
- Evidence completeness.
- Blocking impact.
- Healing risk.
- Baseline when needed.
- Proposed patch boundary.

## Procedure

1. Reject product bug, assertion logic change, major workflow change, and evidence-insufficient cases.
2. Determine blocking impact: high, medium, or low.
3. Determine healing risk: low, medium, or high.
4. Apply the L3 matrix.
5. Allow immediate healing only for high blocking impact + low healing risk + sufficient budget.
6. Define exactly what patch types are allowed.

## Forbidden

- Do not allow assertion, expected value, golden image, comparison rule, or test intent changes.
- Do not allow fixed sleep as healing.
- Do not allow skipping failed steps.

## Completion Output

Return:

```text
Gate: l3_healing_eligibility
L3 eligible: <true/false>
Immediate L3 eligible: <true/false>
Blocking impact: <high/medium/low>
Healing risk: <low/medium/high>
Allowed patch boundary: <summary>
Next gate: <patch_generation/final_reconciliation>
```