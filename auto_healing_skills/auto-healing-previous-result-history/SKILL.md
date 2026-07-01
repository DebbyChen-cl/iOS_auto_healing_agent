---
name: auto-healing-previous-result-history
description: "Use when: querying or updating PHD iOS Auto-Healing Previous Result History, last 5 results, flaky signal, regression candidate, repeated failure, last trusted status, or lightweight history records."
argument-hint: "Stable Case ID, Run ID, current result, or history store path."
user-invocable: true
---

# Auto-Healing Previous Result History Gate

Source SPEC: `Self-healing/SPEC/auto_healing_gate_io_spec/previous_result_history_spec.md`

## Purpose

Use a Stable Case ID to query or update the last 5 lightweight case results. This informs flaky/regression/scheduling decisions without storing large artifacts.

## Required Inputs

- Stable Case ID.
- Run ID.
- Timestamp, branch, commit, app version/build, environment.
- Original status and final status.
- Failure type/root cause/action/healing/reviewer fields when applicable.

## Procedure

1. If Stable Case ID is missing, return `history_unavailable`.
2. Query the most recent 5 records for the Stable Case ID.
3. Summarize status pattern, recent failure count, flaky signal, last trusted status, last failure type, and last root cause.
4. On final reconciliation, write a new lightweight history record and trim to 5.

## Forbidden

- Do not store screenshots, traces, logs, reports, PR links, or artifact links in history.
- Do not label flaky from one failure without retry/history pattern support.

## Completion Output

Return:

```text
Gate: previous_result_history
History available: <true/false>
Last 5 pattern: <pattern>
Flaky signal: <true/false>
Regression candidate: <true/false>
Next gate: pass_baseline_retention
```