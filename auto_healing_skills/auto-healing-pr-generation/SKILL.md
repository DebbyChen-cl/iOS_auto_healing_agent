---
name: auto-healing-pr-generation
description: "Use when: creating or validating a PHD iOS run-level Auto-Healing PR, included/excluded healing cases, PR body, report link, merge gate status, replay-pass eligibility, or PR/report consistency."
argument-hint: "Run ID, eligible patches, excluded cases, report link, or PR draft."
user-invocable: true
---

# Auto-Healing PR Generation Gate

Source SPEC: `Self-healing/SPEC/auto_healing_gate_io_spec/pr_generation_rule_spec.md`

## Purpose

Create at most one run-level Auto-Healing PR per AT run, only after full run and healing replay are complete.

## Required Inputs

- Run ID, branch, commit.
- Replay-passed L3 low-risk patches.
- Failure/replay evidence completeness.
- HTML report link or report artifact.
- Included and excluded case summaries.

## Procedure

1. Collect eligible healing patches from the same run.
2. Exclude non-mergeable cases and record reasons.
3. Create one run-level PR only if at least one patch is eligible.
4. Keep PR merge blocked until HTML report decision is `approve_merge_allowed`.
5. Ensure PR diff and report patch summary match.

## Forbidden

- Do not create one PR per case.
- Do not include replay-failed, medium/high-risk, product bug, major workflow, evidence-gap, assertion-change, or manual-review patches.
- Do not allow merge without report approval.

## Completion Output

Return:

```text
Gate: pr_generation
PR created: <true/false>
Included cases: <list>
Excluded cases: <list with reasons>
Merge gate status: <waiting approval/merge allowed/rejected/need more evidence/manual review required>
Next gate: knowledge_promotion
```