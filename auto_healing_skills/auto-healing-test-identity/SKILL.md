---
name: auto-healing-test-identity
description: "Use when: defining, validating, or reporting gaps in PHD iOS Auto-Healing Test Identity, Stable Case ID, case metadata, feature/module, priority, blocking type, app area, owner, or dependency info."
argument-hint: "Case name, test file path, wrapper method, or existing identity record."
user-invocable: true
---

# Auto-Healing Test Identity Gate

Source SPEC: `Self-healing/SPEC/auto_healing_gate_io_spec/test_identity_spec.md`

## Purpose

Create or validate the stable identity record used to connect test results, failure evidence, healing records, reports, PRs, history, and knowledge.

## Required Inputs

- Stable Case ID, or an explicit reason it is unavailable.
- Case name.
- Test file path.
- Feature / product module.
- Priority.
- Blocking type.
- Recommended: app area / screen, primary test component, owner, dependency info, fixture profile.

## Procedure

1. Locate the wrapper test and implementation test when needed.
2. Verify Stable Case ID is stable and not merely the function name.
3. Verify required metadata is present and human-readable.
4. If any required field is missing, mark an identity gap instead of inventing data.
5. Output identity metadata for downstream history/evidence/healing gates.

## Forbidden

- Do not use a renamed function name as a stable id without registry confirmation.
- Do not store screenshots, logs, traces, or locator lists here.
- Do not infer priority or blocking type as fact unless explicitly marked as inferred.

## Completion Output

Return:

```text
Gate: test_identity
Stable Case ID: <id or missing>
Identity gap: <true/false>
Required metadata: <present/missing>
Downstream key: <stable case id or history_unavailable>
Next gate: failure_evidence_collection
```