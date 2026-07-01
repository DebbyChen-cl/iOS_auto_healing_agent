---
name: auto-healing-failure-taxonomy
description: "Use when: classifying PHD iOS Auto-Healing failures by screenshot and error step, including element not found, compare fail, locator drift, page object drift, wait drift, workflow change, product bug, flaky, network, server busy, app crash, or evidence gap."
argument-hint: "Evidence folder, error step type, screenshot/hierarchy, history summary, or baseline window."
user-invocable: true
---

# Auto-Healing Failure Taxonomy Gate

Source SPEC: `Self-healing/SPEC/auto_healing_gate_io_spec/failure_taxonomy_priority_spec.md`

## Purpose

Classify the failure using the SPEC priority order. Assertion failure is a symptom, not the root cause.

## Required Inputs

- Failure evidence and fail screenshot.
- Error step type: element not found or compare fail.
- Fail hierarchy.
- Step evidence.
- History summary and baseline window when available.

## Procedure

1. Start from fail screenshot + error step.
2. For Element Not Found, decide whether target element is visible in screenshot.
3. If visible, evaluate locator drift, page object drift, and readiness/wait drift.
4. If not visible, evaluate dialog/overlay, previous step not completed, workflow change, product bug, and flaky last.
5. For Compare Fail, distinguish ground-truth compare from before/after compare.
6. Preserve uncertainty and list excluded causes.

## Forbidden

- Do not call a single failure flaky without retry/history support.
- Do not directly exclude healing just because the top-level exception is AssertionError.
- Do not patch code in this gate.

## Completion Output

Return:

```text
Gate: failure_taxonomy
Failure type: <type>
Root cause candidate: <summary>
Confidence: <low/medium/high>
Evidence used: <list>
Excluded causes: <list>
Next gate: immediate_vs_deferred_policy
```