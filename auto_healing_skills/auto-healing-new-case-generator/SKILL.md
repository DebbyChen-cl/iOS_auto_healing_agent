---
name: auto-healing-new-case-generator
description: "Use when: applying PHD iOS Auto-Healing new case generator boundary, deciding whether trusted/candidate knowledge can produce case_idea, draft_case, review_ready_case, approved_case, or rejecting raw event/product-bug/flaky/network sources."
argument-hint: "Target feature, knowledge ids, coverage gap, or proposed generated case."
user-invocable: true
---

# Auto-Healing New Case Generator Boundary Gate

Source SPEC: `Self-healing/SPEC/auto_healing_gate_io_spec/new_case_generator_boundary_spec.md`

## Purpose

Control how Auto-Healing outputs may be used to generate new test cases without turning unreviewed events into test intent.

## Required Inputs

- Target feature/module.
- App Usage Knowledge.
- Coverage Opportunity Knowledge.
- Test Identity template.
- Existing coverage map.
- Test Fragility Knowledge when relevant.
- Source references.

## Procedure

1. Confirm whether source knowledge is trusted, candidate, or invalid.
2. Generate formal test cases only from trusted App Usage or Coverage Opportunity knowledge.
3. Use candidate knowledge only for `case_idea` or `draft_case` with review notes.
4. Use Test Fragility Knowledge only to avoid flaky patterns, not to lower assertions.
5. Reject formal generation from raw event history, rejected healing, evidence gap, product bug, single flaky, network/server busy, generation fail, or AI guess.

## Completion Output

Return:

```text
Gate: new_case_generator_boundary
Generation allowed: <true/false>
Generated case status: <case_idea/draft_case/review_ready_case/approved_case/rejected_case>
Source knowledge: <trusted/candidate/invalid>
Risk notes: <list>
Next gate: metrics
```