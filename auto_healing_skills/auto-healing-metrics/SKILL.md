---
name: auto-healing-metrics
description: "Use when: calculating PHD iOS Auto-Healing metrics, run-level metrics, trend metrics, pass_with_healing counts, pass_after retry counts, healing success, report approval, false/rejected healing, infra/service rates, quality guardrails, or time saved estimate."
argument-hint: "Run summary, final statuses, healing/replay/review results, PR status, or trend window."
user-invocable: true
---

# Auto-Healing Metrics Gate

Source SPEC: `Self-healing/SPEC/auto_healing_gate_io_spec/metrics_spec.md`

## Purpose

Measure whether Auto-Healing saves maintenance time while preserving product bug, infra issue, flaky, and manual review quality signals.

## Required Inputs

- Total cases and final statuses.
- Failure mix.
- Eligible/attempted/successful healing counts.
- Replay attempt counts.
- Review decisions.
- PR states.
- Knowledge promotion states.
- Time estimates.
- Infra/service signals.

## Procedure

1. Count `pass`, `pass_with_healing`, `pass_after_retry`, `pass_after_network_retry`, and `pass_after_generation_retry` separately.
2. Calculate eligible rate, healing success rate, report approval rate, false/rejected healing rate, infra/service rates, and time saved estimate.
3. Preserve product bug suspected, manual review, rejected healing, and evidence gaps as quality signals.
4. Report run-level metrics and trend metrics separately.

## Forbidden

- Do not use total pass rate increase as the main KPI.
- Do not count `pass_with_healing` or `pass_after_*` as ordinary pass.
- Do not treat product bug suspected as healing failure.

## Completion Output

Return:

```text
Gate: metrics
Top-level metrics: <summary>
Quality guardrails: <summary>
Infra/service trend: <summary>
Time saved estimate: <value>
Open risks: <list>
```