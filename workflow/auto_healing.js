export const meta = {
  name: 'auto-healing',
  description: 'Phase 2: parallel root cause + patch, sequential replay with re-analysis loop',
  phases: [
    { title: 'Analyze & Patch', detail: 'Parallel root cause analysis + patch generation per case' },
    { title: 'Replay', detail: 'Sequential replay verification with re-analysis loop on failure' },
    { title: 'Finalize', detail: 'Write results, generate report' }
  ]
}

// ─── Config (edit these per run) ────────────────────────────────────────────

const HEALING_PROJECT = '/Users/rdqe/Desktop/iOS_auto_healing_skills'
const TEST_PROJECT = '/Users/rdqe/Desktop/rdqe-ios-autotest-phdm'
const MAX_HEAL_ATTEMPTS = 10

// ─── Schemas ────────────────────────────────────────────────────────────────

const ANALYZE_PATCH_SCHEMA = {
  type: 'object',
  properties: {
    root_cause: {
      type: 'object',
      properties: {
        type: { type: 'string' },
        confidence: { type: 'number' },
        reason: { type: 'string' },
        evidence_used: { type: 'array', items: { type: 'string' } },
        excluded_causes: { type: 'array', items: { type: 'string' } },
        healable: { type: 'boolean' },
        l3_eligible: { type: 'boolean' },
        blocking_impact: { type: 'string', enum: ['high', 'medium', 'low'] },
        healing_risk: { type: 'string', enum: ['low', 'medium', 'high'] },
        allowed_patch_boundary: { type: ['string', 'null'] },
        risk_flags: { type: 'array', items: { type: 'string' } }
      },
      required: ['type', 'confidence', 'reason', 'healable', 'l3_eligible']
    },
    patch: {
      type: 'object',
      properties: {
        patch_created: { type: 'boolean' },
        patch_type: { type: ['string', 'null'] },
        changed_files: { type: ['array', 'null'], items: { type: 'object' } },
        diff_summary: { type: ['string', 'null'] },
        shared_locator_handling: { type: ['string', 'null'] },
        risk_flags: { type: ['array', 'null'], items: { type: 'string' } },
        reason: { type: ['string', 'null'] }
      },
      required: ['patch_created']
    }
  },
  required: ['root_cause', 'patch']
}

const REPLAY_SCHEMA = {
  type: 'object',
  properties: {
    replay_status: { type: 'string', enum: ['pass_with_healing', 'fail_same_step', 'fail_different_step', 'product_bug_suspected', 'infra_issue_during_replay'] },
    attempt_number: { type: 'number' },
    test_passed: { type: 'boolean' },
    original_fail_step_passed: { type: 'boolean' },
    new_error_summary: { type: ['string', 'null'] },
    requires_assertion_change: { type: 'boolean' },
    revert_needed: { type: 'boolean' }
  },
  required: ['replay_status', 'attempt_number', 'test_passed']
}

// ─── Input from pytest (via args) ───────────────────────────────────────────

const runId = args?.run_id
const deferredCases = args?.cases

if (!runId || !deferredCases?.length) {
  log('ERROR: args must contain run_id and cases[]')
  return { error: 'run_id and cases[] are required via args from pytest' }
}

const statePath = `${HEALING_PROJECT}/runs/${runId}/state.json`

log(`Run ${runId}: ${deferredCases.length} deferred cases from pytest`)

// ─── Phase 1: Analyze & Patch (parallel — merged agent) ────────────────────

phase('Analyze & Patch')

const analyzeResults = await parallel(deferredCases.map(c => () =>
  agent(
    `Analyze this failed test case and generate a patch if L3-eligible.

Case: ${c.case_id}
Name: ${c.case_name}
Error: ${c.error_summary || 'unknown'}
Error type: ${c.error_type || 'unknown'}
Evidence: ${TEST_PROJECT}/${c.evidence_path}
Test file: ${TEST_PROJECT}/${c.test_file}
Test project root: ${TEST_PROJECT}

Read the evidence files, classify the root cause, and if L3-eligible, generate the smallest possible patch. Apply the patch directly to the source files.`,
    {
      label: `analyze:${c.case_id}`,
      phase: 'Analyze & Patch',
      schema: ANALYZE_PATCH_SCHEMA,
      agentType: 'analyze-and-patch'
    }
  ).then(result => ({ case_id: c.case_id, case: c, result }))
))

const analyzed = analyzeResults.filter(Boolean)
const patchedCases = analyzed.filter(r => r.result?.patch?.patch_created)
const notPatched = analyzed.filter(r => !r.result?.patch?.patch_created)

log(`Analyze done: ${analyzed.length} analyzed, ${patchedCases.length} patched, ${notPatched.length} not patched`)

// ─── Phase 3: Replay (sequential — single device, with re-analysis loop) ───

phase('Replay')

const healingResults = []

for (const pc of patchedCases) {
  const c = pc.case
  let currentResult = pc.result
  let healed = false
  let attempt = 1

  while (attempt <= MAX_HEAL_ATTEMPTS && !healed) {
    log(`${c.case_id}: replay attempt ${attempt}/${MAX_HEAL_ATTEMPTS}`)

    const replayResult = await agent(
      `Verify the auto-healing patch by replaying the test.

Case: ${c.case_id}
Test nodeid: ${c.test_file}
Test project: ${TEST_PROJECT}
Evidence: ${TEST_PROJECT}/${c.evidence_path}
Attempt: ${attempt}
Root cause: ${currentResult.root_cause.type} — ${currentResult.root_cause.reason}
Patch: ${currentResult.patch.diff_summary}

Steps:
1. cd to ${TEST_PROJECT}
2. Run: python -m pytest "${c.test_file}" -x --timeout=300 --tb=short -q
3. Check if the test passed
4. If failed, capture the new error message

Report the replay result.`,
      { label: `replay:${c.case_id}:${attempt}`, phase: 'Replay', schema: REPLAY_SCHEMA }
    )

    if (!replayResult) {
      log(`${c.case_id}: replay agent failed`)
      break
    }

    if (replayResult.test_passed) {
      healed = true
      log(`${c.case_id}: HEALED on attempt ${attempt}`)
      healingResults.push({
        case_id: c.case_id, case: c,
        root_cause: currentResult.root_cause, patch: currentResult.patch,
        replay: replayResult, healed: true, attempts: attempt
      })
      break
    }

    const stopStatuses = ['product_bug_suspected', 'infra_issue_during_replay']
    if (replayResult.requires_assertion_change || stopStatuses.includes(replayResult.replay_status)) {
      log(`${c.case_id}: cannot continue — ${replayResult.replay_status}`)
      healingResults.push({
        case_id: c.case_id, case: c,
        root_cause: currentResult.root_cause, patch: currentResult.patch,
        replay: replayResult, healed: false, attempts: attempt
      })
      break
    }

    if (replayResult.revert_needed) {
      log(`${c.case_id}: reverting patch before re-analysis`)
    }

    // Re-analyze with new error context
    if (attempt < MAX_HEAL_ATTEMPTS) {
      log(`${c.case_id}: re-analyzing with new error: ${replayResult.new_error_summary || 'unknown'}`)

      const reAnalysis = await agent(
        `The previous patch for this case was applied but the test still fails with a NEW error.
Re-analyze and generate a new patch.

Case: ${c.case_id}
Name: ${c.case_name}
Evidence: ${TEST_PROJECT}/${c.evidence_path}
Test file: ${TEST_PROJECT}/${c.test_file}
Test project root: ${TEST_PROJECT}
Previous root cause: ${currentResult.root_cause.type} — ${currentResult.root_cause.reason}
Previous patch: ${currentResult.patch.diff_summary}
New error after patch: ${replayResult.new_error_summary || 'unknown'}
Attempt: ${attempt + 1}

Read the evidence, identify the NEW root cause (it may be a different step failing now), and generate a patch if L3-eligible. Apply the patch directly.`,
        {
          label: `re-analyze:${c.case_id}:${attempt + 1}`,
          phase: 'Replay',
          schema: ANALYZE_PATCH_SCHEMA,
          agentType: 'analyze-and-patch'
        }
      )

      if (!reAnalysis?.patch?.patch_created) {
        log(`${c.case_id}: re-analysis could not produce patch`)
        healingResults.push({
          case_id: c.case_id, case: c,
          root_cause: reAnalysis?.root_cause || currentResult.root_cause,
          patch: reAnalysis?.patch || currentResult.patch,
          replay: replayResult, healed: false, attempts: attempt
        })
        break
      }

      currentResult = reAnalysis
    }

    attempt++
  }

  if (!healed && !healingResults.find(h => h.case_id === c.case_id)) {
    healingResults.push({
      case_id: c.case_id, case: c,
      root_cause: currentResult.root_cause, patch: currentResult.patch,
      replay: null, healed: false, attempts: attempt
    })
  }
}

// Add non-patched cases to results
for (const np of notPatched) {
  healingResults.push({
    case_id: np.case_id, case: np.case,
    root_cause: np.result.root_cause, patch: np.result.patch,
    replay: null, healed: false, attempts: 0
  })
}

// ─── Phase 4: Finalize (single agent — write state + report) ────────────────

phase('Finalize')

const healedCount = healingResults.filter(h => h.healed).length
const summary = {
  total: Object.keys(state.cases).length,
  deferred: deferredCases.length,
  analyzed: analyzed.length,
  patched: patchedCases.length,
  healed: healedCount,
  healing_failed: healingResults.filter(h => !h.healed && h.attempts > 0).length,
  not_eligible: notPatched.length
}

const stateUpdates = JSON.stringify(healingResults.map(h => ({
  case_id: h.case_id,
  root_cause: { type: h.root_cause.type, confidence: h.root_cause.confidence, reason: h.root_cause.reason, healable: h.root_cause.healable, l3_eligible: h.root_cause.l3_eligible, risk_flags: h.root_cause.risk_flags || [] },
  patch: h.patch ? { status: h.patch.patch_created ? 'generated' : 'failed', diff_summary: h.patch.diff_summary, reason: h.patch.reason } : null,
  replay: h.replay ? { status: h.replay.replay_status, attempts: h.attempts } : null,
  final_status: h.healed ? 'pass_with_healing' : (h.replay?.replay_status || (h.root_cause.l3_eligible ? 'healing_failed' : 'manual_review_required')),
  pr_eligible: h.healed
})))

await agent(
  `Update state.json and generate the HTML report.

State file: ${statePath}
Run ID: ${runId}

1. Read ${statePath}, update each case with these results, and write back:
${stateUpdates}

For each entry, set cases[case_id].root_cause, .patch, .replay, .final_status, .pr_eligible.
Update summary to: ${JSON.stringify(summary)}
Set phase to "done".

2. Run: python3 ${HEALING_PROJECT}/tools/generate_report.py ${runId} ${HEALING_PROJECT}`,
  { label: 'finalize', phase: 'Finalize' }
)

log(`Done: ${healedCount}/${patchedCases.length} healed, ${summary.not_eligible} not eligible`)

return { run_id: runId, summary, healed_cases: healingResults.filter(h => h.healed).map(h => h.case_id) }
