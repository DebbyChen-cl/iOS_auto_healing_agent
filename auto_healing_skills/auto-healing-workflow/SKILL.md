---
name: auto-healing-workflow
description: "Use when: deciding or executing the PHD iOS AI Auto-Healing workflow step, including failure evidence collection, previous result history, pass baseline, failure taxonomy, retry, scheduling, L3 healing eligibility, replay verification, HTML report approval, PR generation, knowledge promotion, new case generation, and metrics."
argument-hint: "Current run/case state, evidence folder path, failure type, or workflow gate."
user-invocable: true
---

# Auto-Healing Workflow Router

This skill routes to one gate skill of the PHD iOS AI Auto-Healing workflow at a time. The goal is controlled progress: collect evidence first, then classify, decide scheduling, determine healing eligibility, patch only when allowed, replay, report, and only then PR/review/knowledge/metrics.

## Source of Truth

Use these SPEC files as authoritative references:

- `Self-healing/SPEC/auto_healing_gate_io_spec/test_identity_spec.md`
- `Self-healing/SPEC/auto_healing_gate_io_spec/failure_evidence_collection_spec.md`
- `Self-healing/SPEC/auto_healing_gate_io_spec/previous_result_history_spec.md`
- `Self-healing/SPEC/auto_healing_gate_io_spec/pass_baseline_retention_spec.md`
- `Self-healing/SPEC/auto_healing_gate_io_spec/failure_taxonomy_priority_spec.md`
- `Self-healing/SPEC/auto_healing_gate_io_spec/immediate_vs_deferred_policy_spec.md`
- `Self-healing/SPEC/auto_healing_gate_io_spec/retry_policy_spec.md`
- `Self-healing/SPEC/auto_healing_gate_io_spec/l3_healing_eligibility_spec.md`
- `Self-healing/SPEC/auto_healing_gate_io_spec/replay_verification_spec.md`
- `Self-healing/SPEC/auto_healing_gate_io_spec/html_report_approval_rule_spec.md`
- `Self-healing/SPEC/auto_healing_gate_io_spec/pr_generation_rule_spec.md`
- `Self-healing/SPEC/auto_healing_gate_io_spec/knowledge_promotion_spec.md`
- `Self-healing/SPEC/auto_healing_gate_io_spec/new_case_generator_boundary_spec.md`
- `Self-healing/SPEC/auto_healing_gate_io_spec/metrics_spec.md`

## Core Workflow

```text
Test run / failed case
  -> Test Identity
  -> Failure Evidence Collection
  -> Previous Result History Lookup
  -> Pass Baseline Lookup when needed
  -> Failure Taxonomy
  -> Immediate vs Deferred Scheduling
  -> Retry Policy when eligible
  -> L3 Healing Eligibility
  -> Patch Generation when allowed
  -> Replay Verification
  -> Final Reconciliation
  -> HTML Report Approval
  -> Run-level PR Generation
  -> Knowledge Promotion
  -> Metrics
```

Always choose the earliest incomplete gate. Never skip from evidence directly to patching.

## Gate Skill Map

| Gate | Skill |
|---|---|
| Test Identity | `auto-healing-test-identity` |
| Failure Evidence Collection | `auto-healing-failure-evidence` |
| Previous Result History | `auto-healing-previous-result-history` |
| Pass Baseline Retention | `auto-healing-pass-baseline` |
| Failure Taxonomy | `auto-healing-failure-taxonomy` |
| Immediate vs Deferred Scheduling | `auto-healing-scheduling-decision` |
| Retry Policy | `auto-healing-retry-policy` |
| L3 Healing Eligibility | `auto-healing-l3-eligibility` |
| Patch Generation | `auto-healing-patch-generation` |
| Replay Verification | `auto-healing-replay-verification` |
| Final Reconciliation | `auto-healing-final-reconciliation` |
| HTML Report Approval | `auto-healing-html-report-approval` |
| PR Generation | `auto-healing-pr-generation` |
| Knowledge Promotion | `auto-healing-knowledge-promotion` |
| New Case Generator Boundary | `auto-healing-new-case-generator` |
| Metrics | `auto-healing-metrics` |

After identifying the current gate, load and follow the matching gate skill. Use this router only to decide the gate and check ordering.

## Gate Contracts

### 1. Test Identity

Required inputs:
- Stable Case ID, case name, test file path, feature/module, priority, blocking type.

Allowed actions:
- Create or validate identity metadata.
- Mark `identity_gap` if Stable Case ID or registry mapping is missing.

Completion output:
- Identity record or explicit identity gap.

### 2. Failure Evidence Collection

Required inputs:
- Run ID, branch, commit, app version, device, iOS version, environment.
- Fail step id/order/action, test line/function.
- Error message, stack trace, assertion/exception type.
- Fail screenshot, fail hierarchy, step before/after screenshot and hierarchy.

Allowed actions:
- Save raw evidence under `Self-healing/evidence/<timestamp>-<testcasename>/`.
- Mark evidence gaps.

Forbidden actions:
- Do not classify root cause.
- Do not patch code.

Completion output:
- Evidence folder and `metadata.json` with evidence completeness/gaps.

### 3. Previous Result History

Required inputs:
- Stable Case ID and current Run ID.

Allowed actions:
- Query or update last 5 lightweight history records.
- Identify new failure, repeated failure, flaky signal, or recurring infra/service pattern.

Completion output:
- History summary or `history_unavailable` if Stable Case ID is missing.

### 4. Pass Baseline Retention

Required inputs:
- Stable Case ID, fail step id/order, failure reason candidate.

Allowed actions:
- Load trusted step-level baseline only when needed for locator, page object, wait, or micro-flow analysis.
- Compare fail step inclusive previous 5-step window.

Completion output:
- Baseline window, missing/stale baseline note, or baseline-not-needed decision.

### 5. Failure Taxonomy

Required inputs:
- Failure evidence, error step type, screenshot, hierarchy, history, and baseline when needed.

Allowed actions:
- Classify failure by SPEC priority.
- Preserve uncertainty and evidence gaps.

Forbidden actions:
- Do not label flaky from a single run without retry/history support.
- Do not treat assertion failure itself as root cause.

Completion output:
- Failure type, root cause candidate, confidence, evidence used, exclusions.

### 6. Immediate vs Deferred Scheduling

Required inputs:
- Failure type, priority, blocking type, history, evidence, device availability, immediate budget.

Allowed actions:
- Route to Lane A, B, C, or D.
- Decide retry, recovery, deferred healing, manual review, or no healing.

Completion output:
- Lane, action, rerun allowance, rerun limit, reason, final status candidate.

### 7. Retry Policy

Required inputs:
- Retry eligibility reason and remaining retry budget.

Allowed actions:
- Retry original case once without code changes.
- Save retry count, reason, result, status after retry, evidence delta.

Forbidden actions:
- Do not modify code during retry.
- Do not mark retry pass as ordinary `pass`.

Completion output:
- `pass_after_*` or failure type routed to next gate.

### 8. L3 Healing Eligibility

Required inputs:
- Root cause, blocking impact, healing risk, evidence completeness, baseline if needed.

Allowed actions:
- Decide L3, L2/manual, or no healing.
- Determine immediate L3 only for high impact + low risk with budget.

Forbidden actions:
- Do not allow assertion, expected value, comparison rule, golden image, or test intent changes.

Completion output:
- Eligibility decision, risk flags, allowed patch boundary.

### 9. Patch Generation

Required inputs:
- L3 eligibility, allowed patch boundary, target files/functions, evidence.

Allowed actions:
- Patch locator, page object locator, state-based wait, or small micro-flow only.
- Use locator override parameter when shared impact is unclear.
- If the target element exists in hierarchy evidence, repair the locator/reachability path; do not remove the failing step.
- Resolve locator repairs strictly in this hierarchy-backed order: accessibility id, label, name, XPath, then position.

Forbidden actions:
- Do not use fixed sleep as healing.
- Do not skip failed steps.
- Do not delete a step when the target element exists in fail/step hierarchy evidence.
- Do not guess locator values; every ID, label, name, XPath attribute, or position must be copied from hierarchy evidence.

Completion output:
- Patch, diff summary, risk flags, replay plan.

### 10. Replay Verification

Required inputs:
- Candidate patch and replay scope.

Allowed actions:
- Run at most one replay per patch attempt.
- Produce up to 10 patch attempts total.
- Save replay screenshot, replay log summary, attempt result, final status candidate.

Completion output:
- `pass_with_healing`, `healing_failed`, `manual_review_required`, `product_bug_suspected`, or retry/infra status.

### 11. Final Reconciliation

Required inputs:
- Original result, retry result, healing/replay result, review state if available.

Allowed actions:
- Preserve original failure and assign final status.
- Update previous result history.

Completion output:
- Final case status and run-level status summary.

### 12. HTML Report Approval

Required inputs:
- Failure evidence, root cause, patch summary, replay evidence, risk flags, PR diff if any.

Allowed decisions:
- `approve_merge_allowed`
- `reject_healing`
- `need_more_evidence`
- `manual_code_review_required`

Completion output:
- Reviewer decision and merge gate status.

### 13. PR Generation

Required inputs:
- Replay-passed L3 low-risk patches and run-level report.

Allowed actions:
- Create at most one run-level Auto-Healing PR per AT run.
- Include only PR-eligible patches.
- List excluded cases and reasons.

Completion output:
- Draft/blocked PR body aligned with report, or no-eligible-patch report only.

### 14. Knowledge Promotion

Required inputs:
- Approved review event and source evidence.

Allowed actions:
- Promote accepted facts to candidate knowledge.
- Promote to trusted only after repeated approvals or explicit reviewer confirmation.

Forbidden actions:
- Do not promote rejected, evidence-gap, manual-review, product-bug, flaky, network, or generation-fail events into healing knowledge.

Completion output:
- Candidate/trusted/deprecated knowledge record or no-promotion decision.

### 15. New Case Generator Boundary

Required inputs:
- Trusted knowledge and coverage opportunity.

Allowed actions:
- Generate formal test cases only from trusted App Usage or Coverage Opportunity knowledge.
- Generate drafts/ideas from candidate knowledge with clear labeling.

Completion output:
- Generated-case candidate, draft, or blocked reason.

### 16. Metrics

Required inputs:
- Run results, final statuses, healing attempts, reviews, PR state, knowledge state, infra/service signals.

Allowed actions:
- Report run-level and trend metrics without treating `pass_with_healing` or `pass_after_*` as ordinary pass.

Completion output:
- Metrics summary focused on time saved, healing reliability, approval quality, false healing, and preserved quality signals.

## Routing Output Template

When deciding the next step, return:

```text
Current gate: <gate>
Why this gate: <reason>
Required inputs: <available / missing>
Allowed actions: <actions>
Forbidden actions: <actions>
Completion output: <artifact/status expected>
Next gate after completion: <gate>
```

## Safety Rules

- Earlier gates control later gates. Missing evidence or missing identity must be surfaced, not hidden.
- `pass_with_healing`, `pass_after_retry`, `pass_after_network_retry`, and `pass_after_generation_retry` are not ordinary pass.
- Product bug suspected, infra issue, flaky signal, rejected healing, and evidence gaps are quality signals.
- HTML report approval is the merge gate. PR approval cannot bypass it.