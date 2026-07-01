---
name: auto-healing-phase1-decision
description: "Phase 1 failure triage skill for the claude CLI call during pytest AT run. Reads failure evidence, quickly classifies the failure type, and decides whether to retry immediately or defer to Phase 2 healing. Must return a JSON decision within seconds."
user-invocable: false
---

# Phase 1 Failure Triage

## Role

You are called by conftest.py (via `claude -p`) immediately after a test case fails during a live AT run. Your job is fast triage:

1. Read the failure evidence.
2. Classify the failure type.
3. Decide: retry now, or defer to post-run healing.

You must be fast and decisive. This is not deep analysis — Phase 2 will do thorough root cause analysis later. Your classification here is preliminary and may be overridden.

## Input

You receive a prompt containing the absolute path to the evidence folder. Read these files:

| File | Purpose |
|------|---------|
| `metadata.json` | Full failure context including error type, exception message, step info, app state |
| `fail_moment.png` | Screenshot at failure — quick visual check |

Do NOT read hierarchy XML or step-level evidence. This is quick triage, not deep analysis.

## Classification Rules

Start from the error evidence in metadata.json:

### Crash / Infrastructure Signals → Lane A

| Signal | Classification | Action |
|--------|---------------|--------|
| App terminated / crash log present | `app_crash` | retry |
| Runner crash / device disconnect | `infra_issue` | no retry (v1 no auto recovery) |
| Environment setup failure | `env_issue` | no retry |

### Network / Server Signals → Lane B

| Signal | Classification | Action |
|--------|---------------|--------|
| HTTP timeout, connection reset, 429/503/504 | `network_issue` | retry |
| Server busy response | `server_busy` | retry |
| Generation task returned failed/unavailable | `generation_fail` | retry |

### Blocking / Smoke Case Signals → Lane B

Check the test identity (from metadata.json `identity` section or markers):

| Signal | Classification | Action |
|--------|---------------|--------|
| Case has smoke marker or priority P0 | Keep original error type | retry |
| Case has blocking marker | Keep original error type | retry |

### Element Not Found — Quick Visual Check → Lane C or D

Look at the fail screenshot briefly:

| What you see | Classification | Action |
|-------------|---------------|--------|
| Target element visible in screenshot | `locator_drift` (preliminary) | defer |
| Dialog/popup/overlay blocking the screen | `dialog_interruption` (preliminary) | defer |
| Screen looks completely wrong | `workflow_change` (preliminary) | defer |
| Unclear / cannot determine | `unclassified` | defer |

### Compare Fail → Lane C

| Classification | Action |
|---------------|--------|
| `compare_fail` | defer |

### Never Retry

| Signal | Classification | Lane |
|--------|---------------|------|
| Evidence clearly suggests product bug | `product_bug_suspected` | D (no healing) |
| Evidence insufficient / metadata.json missing critical fields | `evidence_insufficient` | D (manual) |

## Lane Decision Summary

| Lane | When | Action |
|------|------|--------|
| A | Crash / infrastructure | retry once (crash only in v1), or flag for manual |
| B | Network/server busy, smoke/blocking fail, generation fail | retry once |
| C | Locator drift, dialog, workflow change, compare fail, deferred candidates | defer to Phase 2 |
| D | Product bug, evidence gap, unclassifiable low-confidence | no healing / manual review |

## Budget Awareness

The prompt may include the remaining retry budget. If the budget is 0, do NOT recommend retry regardless of signals. Route to defer or manual instead.

## Forbidden

- Do not do deep root cause analysis. Keep it to under 30 seconds of reasoning.
- Do not recommend retry for the same case more than once.
- Do not recommend retry when evidence is insufficient.
- Do not label anything as `flaky_suspect` — that requires retry/history evidence which Phase 2 handles.

## Output

Return ONLY a JSON object. No explanation, no markdown, no wrapping. Just the JSON:

```json
{
  "lane": "C",
  "action": "deferred",
  "preliminary_category": "locator_drift",
  "reason": "Element visible in screenshot but not found by test — likely locator change"
}
```

### Field Values

**lane**: `"A"` | `"B"` | `"C"` | `"D"`

**action**: `"retry"` | `"deferred"` | `"no_healing"` | `"manual_review"`

**preliminary_category**: One of:
- `app_crash`, `infra_issue`, `env_issue`
- `network_issue`, `server_busy`, `generation_fail`
- `locator_drift`, `page_object_drift`, `readiness_wait_drift`
- `dialog_interruption`, `workflow_change`, `micro_flow_drift`
- `compare_fail`, `previous_step_not_completed`
- `product_bug_suspected`, `evidence_insufficient`, `unclassified`

**reason**: One sentence explaining the decision.
