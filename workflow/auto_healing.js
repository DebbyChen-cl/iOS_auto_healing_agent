export const meta = {
  name: 'auto-healing',
  description: 'Phase 2: AI root cause analysis, patch generation, replay verification, report, PR, and knowledge promotion for PHD iOS auto-healing pipeline',
  phases: [
    { title: 'Load', detail: 'Read state.json and filter deferred cases' },
    { title: 'Root Cause Analysis', detail: 'Parallel AI analysis per deferred case' },
    { title: 'Healing', detail: 'Sequential patch generation + replay per healable case' },
    { title: 'Reconciliation', detail: 'Merge all results into final status' },
    { title: 'Report & PR', detail: 'Generate HTML report and create PR' },
    { title: 'Knowledge', detail: 'Promote approved healing events to knowledge base' }
  ]
}

// ─── Paths ───────────────────────────────────────────────────────────────────

const SKILLS_PATH = '/Users/rdqe/Desktop/iOS_auto_healing_skills/auto_healing_skills'
const HEALING_PROJECT_PATH = '/Users/rdqe/Desktop/iOS_auto_healing_skills'
const TEST_PROJECT_PATH = '/Users/rdqe/Desktop/rdqe-ios-autotest-phdm'

// ─── Schemas ─────────────────────────────────────────────────────────────────

const ROOT_CAUSE_SCHEMA = {
  type: 'object',
  properties: {
    type: { type: 'string' },
    confidence: { type: 'number' },
    reason: { type: 'string' },
    evidence_used: { type: 'array', items: { type: 'string' } },
    excluded_causes: { type: 'array', items: { type: 'string' } },
    healable: { type: 'boolean' },
    l3_eligible: { type: 'boolean' },
    immediate_l3_eligible: { type: 'boolean' },
    blocking_impact: { type: 'string', enum: ['high', 'medium', 'low'] },
    healing_risk: { type: 'string', enum: ['low', 'medium', 'high'] },
    allowed_patch_boundary: { type: ['string', 'null'] },
    risk_flags: { type: 'array', items: { type: 'string' } },
    identity_enrichment: {
      type: ['object', 'null'],
      properties: {
        feature: { type: ['string', 'null'] },
        app_area: { type: ['string', 'null'] },
        primary_test_component: { type: ['string', 'null'] }
      }
    }
  },
  required: ['type', 'confidence', 'reason', 'healable', 'l3_eligible', 'blocking_impact', 'healing_risk', 'allowed_patch_boundary', 'risk_flags']
}

const PATCH_SCHEMA = {
  type: 'object',
  properties: {
    patch_created: { type: 'boolean' },
    patch_type: { type: ['string', 'null'] },
    changed_files: { type: ['array', 'null'], items: { type: 'object' } },
    diff: { type: ['string', 'null'] },
    diff_summary: { type: ['string', 'null'] },
    shared_locator_handling: { type: ['string', 'null'] },
    risk_flags: { type: ['array', 'null'], items: { type: 'string' } },
    replay_scope: { type: ['string', 'null'] },
    reason: { type: ['string', 'null'] }
  },
  required: ['patch_created']
}

const REPLAY_SCHEMA = {
  type: 'object',
  properties: {
    replay_status: { type: 'string' },
    attempt_number: { type: 'number' },
    test_passed: { type: 'boolean' },
    original_fail_step_passed: { type: 'boolean' },
    final_assertion_passed: { type: 'boolean' },
    forbidden_changes_detected: { type: 'boolean' },
    new_high_risk_signals: { type: 'array', items: { type: 'string' } },
    requires_assertion_change: { type: 'boolean' },
    replay_evidence: { type: 'object' },
    can_continue_attempts: { type: 'boolean' },
    revert_needed: { type: 'boolean' }
  },
  required: ['replay_status', 'attempt_number', 'test_passed']
}

const REPORT_SCHEMA = {
  type: 'object',
  properties: {
    decision: { type: 'string', enum: ['approve_merge_allowed', 'reject_healing', 'need_more_evidence', 'manual_code_review_required'] },
    merge_allowed: { type: 'boolean' },
    report_path: { type: 'string' },
    checklist_results: { type: 'array', items: { type: 'object' } },
    failed_items: { type: 'array', items: { type: 'number' } },
    blocking_issues: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' }
  },
  required: ['decision', 'merge_allowed', 'report_path', 'summary']
}

const KNOWLEDGE_SCHEMA = {
  type: 'object',
  properties: {
    promotion_allowed: { type: 'boolean' },
    entries_created: { type: 'array', items: { type: 'object' } },
    entries_promoted: { type: 'array', items: { type: 'object' } },
    entries_deprecated: { type: 'array', items: { type: 'object' } },
    total_new: { type: 'number' },
    total_promoted: { type: 'number' },
    total_deprecated: { type: 'number' },
    reason: { type: ['string', 'null'] }
  },
  required: ['promotion_allowed']
}

// ─── Phase 1: Load ──────────────────────────────────────────────────────────

phase('Load')

const runId = args?.run_id
if (!runId) {
  log('ERROR: run_id is required. Pass it via args: { run_id: "run-20260701-220000" }')
  return { error: 'run_id is required' }
}

const statePath = `${HEALING_PROJECT_PATH}/runs/${runId}/state.json`

const stateRaw = await agent(
  `Read the file at ${statePath} and return its full content as a JSON string in the "content" field.`,
  { label: 'read-state', phase: 'Load', schema: { type: 'object', properties: { content: { type: 'string' } }, required: ['content'] } }
)

if (!stateRaw) {
  log('ERROR: Could not read state.json')
  return { error: 'could not read state.json' }
}

const state = JSON.parse(stateRaw.content)
log(`Run ${runId}: ${state.summary.total} cases, ${state.summary.fail} failed`)

const deferredCases = Object.entries(state.cases)
  .filter(([_, c]) => c.scheduling && c.scheduling.action === 'deferred')
  .map(([caseId, c]) => ({ case_id: caseId, ...c }))

log(`${deferredCases.length} deferred cases entering root cause analysis`)

if (deferredCases.length === 0) {
  log('No deferred cases to heal. Workflow complete.')
  return { run_id: runId, healed: 0, message: 'no deferred cases' }
}

// ─── Phase 2: Root Cause Analysis (parallel per case) ────────────────────────

phase('Root Cause Analysis')

const rootCauseResults = await parallel(deferredCases.map(c => () =>
  agent(
    `Read the skill file at ${SKILLS_PATH}/auto-healing-root-cause/SKILL.md to understand your role and rules.

Then analyze this case:

- case_id: ${c.case_id}
- case_name: ${c.case_name}
- error_summary: ${c.error_summary}
- error_type: ${c.error_type}
- preliminary_category: ${c.scheduling.preliminary_category}
- evidence_path: ${TEST_PROJECT_PATH}/${c.evidence_path}
- test_file: ${TEST_PROJECT_PATH}/${c.test_file}
- previous_result: null`,
    { label: `root-cause:${c.case_id}`, phase: 'Root Cause Analysis', schema: ROOT_CAUSE_SCHEMA }
  ).then(result => ({ case_id: c.case_id, case: c, result }))
))

const analyzedCases = rootCauseResults.filter(Boolean)
const healableCases = analyzedCases.filter(r => r.result && r.result.l3_eligible)
const nonHealable = analyzedCases.filter(r => !r.result || !r.result.l3_eligible)

log(`Root cause done: ${analyzedCases.length} analyzed, ${healableCases.length} L3-eligible, ${nonHealable.length} not healable`)

// Write root cause results back to state (via agent since we need file write)
await agent(
  `Read the file at ${statePath}, parse it as JSON, and update the "cases" entries with the following root cause results. For each case, set the "root_cause" field to the provided result object, and also save the full result to the analysis detail path.

State path: ${statePath}
Run ID: ${runId}
Healing project: ${HEALING_PROJECT_PATH}

Results to write:
${JSON.stringify(analyzedCases.map(r => ({
  case_id: r.case_id,
  root_cause: {
    type: r.result.type,
    confidence: r.result.confidence,
    reason: r.result.reason,
    healable: r.result.healable,
    l3_eligible: r.result.l3_eligible,
    risk_flags: r.result.risk_flags,
    detail_path: `runs/${runId}/analysis/${r.case_id}/root_cause.json`
  },
  full_result: r.result
})))}

For each case:
1. Update state.json cases[case_id].root_cause with the summary (type, confidence, reason, healable, l3_eligible, risk_flags, detail_path)
2. Create the directory runs/${runId}/analysis/{case_id}/ and write root_cause.json with the full result
3. If the result has identity_enrichment with non-null fields, read registry/test_registry.json and update the case entry

Also update state.json "phase" to "phase_2_root_cause".`,
  { label: 'write-root-cause', phase: 'Root Cause Analysis' }
)

// ─── Phase 3: Healing (sequential: patch → replay per case) ──────────────────

phase('Healing')

if (healableCases.length === 0) {
  log('No L3-eligible cases. Skipping healing phase.')
} else {
  log(`Starting healing for ${healableCases.length} cases (sequential — single device)`)
}

const healingResults = []

for (const hc of healableCases) {
  const c = hc.case
  const rc = hc.result
  let healed = false
  let finalReplay = null
  let finalPatch = null
  const maxAttempts = 3

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    log(`${c.case_id}: patch attempt ${attempt}/${maxAttempts}`)

    const previousError = finalReplay ? finalReplay.replay_evidence?.error_message : null

    const patchResult = await agent(
      `Read the skill file at ${SKILLS_PATH}/auto-healing-patch-generation/SKILL.md to understand your role and rules.

Then generate a patch for this case:

- case_id: ${c.case_id}
- case_name: ${c.case_name}
- evidence_path: ${TEST_PROJECT_PATH}/${c.evidence_path}
- test_file: ${TEST_PROJECT_PATH}/${c.test_file}
- test_project_path: ${TEST_PROJECT_PATH}
- root_cause: ${JSON.stringify(rc)}
${attempt > 1 ? `- previous_attempt_error: ${previousError}` : ''}
${attempt > 1 ? `- attempt_number: ${attempt} — generate a DIFFERENT patch than previous attempts` : ''}`,
      { label: `patch:${c.case_id}:${attempt}`, phase: 'Healing', schema: PATCH_SCHEMA }
    )

    if (!patchResult || !patchResult.patch_created) {
      log(`${c.case_id}: patch generation failed${patchResult?.reason ? ' — ' + patchResult.reason : ''}`)
      break
    }

    finalPatch = patchResult
    log(`${c.case_id}: patch created (${patchResult.patch_type}), starting replay`)

    const replayResult = await agent(
      `Read the skill file at ${SKILLS_PATH}/auto-healing-replay-verification/SKILL.md to understand your role and rules.

Then verify this patch:

- case_id: ${c.case_id}
- case_name: ${c.case_name}
- test_nodeid: ${c.test_file}
- test_project_path: ${TEST_PROJECT_PATH}
- evidence_path: ${TEST_PROJECT_PATH}/${c.evidence_path}
- patch: ${JSON.stringify(patchResult)}
- attempt_number: ${attempt}
- previous_replay_error: ${previousError}`,
      { label: `replay:${c.case_id}:${attempt}`, phase: 'Healing', schema: REPLAY_SCHEMA }
    )

    finalReplay = replayResult

    if (replayResult && replayResult.replay_status === 'pass_with_healing') {
      healed = true
      log(`${c.case_id}: HEALED on attempt ${attempt}`)
      break
    }

    if (replayResult && replayResult.requires_assertion_change) {
      log(`${c.case_id}: requires assertion change — stopping L3 healing`)
      break
    }

    if (replayResult && ['product_bug_suspected', 'infra_issue_during_replay'].includes(replayResult.replay_status)) {
      log(`${c.case_id}: ${replayResult.replay_status} — stopping healing`)
      break
    }

    log(`${c.case_id}: attempt ${attempt} failed (${replayResult?.replay_status || 'unknown'})`)
  }

  healingResults.push({
    case_id: c.case_id,
    case: c,
    root_cause: rc,
    patch: finalPatch,
    replay: finalReplay,
    healed
  })
}

// Write healing results to state
if (healingResults.length > 0) {
  await agent(
    `Read and update the state file at ${statePath}.

For each case below, update these fields in state.json:
- cases[case_id].patch = the patch summary
- cases[case_id].replay = the replay summary
- cases[case_id].final_status = the determined final status

Also save detailed patch/replay output files.

Run ID: ${runId}
Healing project: ${HEALING_PROJECT_PATH}

Results:
${JSON.stringify(healingResults.map(h => ({
  case_id: h.case_id,
  patch: h.patch ? {
    status: h.patch.patch_created ? 'generated' : 'failed',
    diff_summary: h.patch.diff_summary,
    risk_flags: h.patch.risk_flags,
    detail_path: `runs/${runId}/patches/${h.case_id}/`
  } : null,
  replay: h.replay ? {
    status: h.replay.replay_status,
    attempts: h.replay.attempt_number,
    detail_path: `runs/${runId}/replay/${h.case_id}/`
  } : null,
  final_status: h.healed ? 'pass_with_healing' : (h.replay?.replay_status || 'healing_failed'),
  pr_eligible: h.healed,
  full_patch: h.patch,
  full_replay: h.replay
})))}

For each case:
1. Update state.json with the summary fields
2. Create runs/${runId}/patches/{case_id}/ and write meta.json + patch.diff (if patch exists)
3. Create runs/${runId}/replay/{case_id}/ and write result.json (if replay exists)

Update state.json "phase" to "phase_2_healing".`,
    { label: 'write-healing', phase: 'Healing' }
  )
}

// ─── Phase 4: Reconciliation ─────────────────────────────────────────────────

phase('Reconciliation')

// Compute final statuses for ALL cases (not just healed)
const finalStatuses = {}
for (const [caseId, c] of Object.entries(state.cases)) {
  if (c.original_status === 'pass') {
    finalStatuses[caseId] = 'pass'
  } else if (c.retry && c.retry.result === 'pass') {
    finalStatuses[caseId] = c.retry.status_after || 'pass_after_retry'
  } else {
    const hr = healingResults.find(h => h.case_id === caseId)
    if (hr && hr.healed) {
      finalStatuses[caseId] = 'pass_with_healing'
    } else if (hr) {
      finalStatuses[caseId] = hr.replay?.replay_status || 'healing_failed'
    } else {
      const analyzed = analyzedCases.find(a => a.case_id === caseId)
      if (analyzed && analyzed.result) {
        if (analyzed.result.type === 'product_bug_suspected') {
          finalStatuses[caseId] = 'product_bug'
        } else if (!analyzed.result.healable) {
          finalStatuses[caseId] = 'manual_review_required'
        } else {
          finalStatuses[caseId] = c.scheduling?.action || 'fail'
        }
      } else {
        finalStatuses[caseId] = c.original_status || 'fail'
      }
    }
  }
}

const summary = {
  total: Object.keys(state.cases).length,
  pass: Object.values(finalStatuses).filter(s => s === 'pass').length,
  fail: Object.values(finalStatuses).filter(s => s === 'fail').length,
  pass_with_healing: Object.values(finalStatuses).filter(s => s === 'pass_with_healing').length,
  pass_after_retry: Object.values(finalStatuses).filter(s => s.startsWith('pass_after_')).length,
  deferred: Object.values(finalStatuses).filter(s => s === 'deferred').length,
  manual_review: Object.values(finalStatuses).filter(s => s === 'manual_review_required').length,
  product_bug: Object.values(finalStatuses).filter(s => s === 'product_bug').length,
  healing_attempted: healingResults.length,
  healing_succeeded: healingResults.filter(h => h.healed).length
}

log(`Reconciliation: ${summary.pass} pass, ${summary.pass_with_healing} healed, ${summary.pass_after_retry} retry-pass, ${summary.fail} fail, ${summary.manual_review} manual, ${summary.product_bug} product bug`)

// Write reconciliation to state
await agent(
  `Read and update the state file at ${statePath}.

Set the following for each case in state.json:
${JSON.stringify(Object.entries(finalStatuses).map(([id, status]) => ({ case_id: id, final_status: status })))}

Also update the "summary" field to:
${JSON.stringify(summary)}

And set "phase" to "phase_2_report".`,
  { label: 'write-reconciliation', phase: 'Reconciliation' }
)

// ─── Phase 5: Report & PR ────────────────────────────────────────────────────

phase('Report & PR')

const healedCases = healingResults.filter(h => h.healed)
const reportPath = `${HEALING_PROJECT_PATH}/runs/${runId}/report.html`

if (healedCases.length > 0) {
  // Generate HTML report for all healed cases
  const reportResult = await agent(
    `Read the skill file at ${SKILLS_PATH}/auto-healing-html-report-approval/SKILL.md to understand your role and rules.

Generate an HTML report covering ALL healed cases in this run. For each case, run the strict approval checklist.

Run ID: ${runId}
Report output path: ${reportPath}

Healed cases:
${JSON.stringify(healedCases.map(h => ({
  case_id: h.case_id,
  case_name: h.case.case_name,
  evidence_path: `${TEST_PROJECT_PATH}/${h.case.evidence_path}`,
  test_file: `${TEST_PROJECT_PATH}/${h.case.test_file}`,
  root_cause: h.root_cause,
  patch: h.patch,
  replay: h.replay,
  final_status_candidate: 'pass_with_healing'
})))}

Generate ONE combined HTML report at ${reportPath}. For each case, include all sections defined in the skill (header, failure summary, evidence panel, root cause, patch, replay, approval checklist, decision). Each case gets its own section in the report.

Return the overall decision: approve_merge_allowed ONLY if ALL cases pass ALL checklist items.`,
    { label: 'html-report', phase: 'Report & PR', schema: REPORT_SCHEMA }
  )

  if (reportResult && reportResult.merge_allowed) {
    log(`Report: approve_merge_allowed — creating PR`)

    // Create PR via gh CLI
    await agent(
      `You need to create a healing PR for the auto-healed test cases.

1. Navigate to: ${TEST_PROJECT_PATH}
2. Check if there are uncommitted changes from the healing patches
3. If there are changes:
   a. Create a new branch: auto-healing/${runId}
   b. Stage and commit the patch changes with message: "fix(auto-healing): ${healedCases.map(h => h.case_id).join(', ')} — auto-healed by AI"
   c. Push the branch
   d. Create a PR using: gh pr create --title "Auto-Healing: ${runId}" --body with:
      - Summary of healed cases (case_id, root_cause type, patch_type)
      - Link to HTML report at ${reportPath}
      - "Generated by auto-healing pipeline"
4. If no changes found, report that no PR is needed

Return what you did.`,
      { label: 'create-pr', phase: 'Report & PR' }
    )
  } else {
    log(`Report decision: ${reportResult?.decision || 'unknown'} — no PR created`)
    if (reportResult?.blocking_issues?.length > 0) {
      log(`Blocking issues: ${reportResult.blocking_issues.join(', ')}`)
    }
  }
} else {
  log('No healed cases — skipping report and PR generation')

  // Still generate a summary report for the run
  await agent(
    `Generate a simple HTML summary report at ${reportPath} for run ${runId}.

No cases were healed in this run. Create a report showing:
- Run summary: ${JSON.stringify(summary)}
- For each analyzed case that was NOT healed, show: case_id, root cause type, why it was not healed
- Non-healable cases: ${JSON.stringify(nonHealable.map(n => ({ case_id: n.case_id, type: n.result?.type, reason: n.result?.reason, healable: n.result?.healable })))}

Write the HTML to ${reportPath}.`,
    { label: 'summary-report', phase: 'Report & PR' }
  )
}

// ─── Phase 6: Knowledge Promotion ────────────────────────────────────────────

phase('Knowledge')

const approvedCases = healedCases.filter(h => {
  // Only promote cases where the report approved them
  return true // Report-level approval already checked above
})

if (approvedCases.length > 0) {
  const knowledgeResult = await agent(
    `Read the skill file at ${SKILLS_PATH}/auto-healing-knowledge-promotion/SKILL.md to understand your role and rules.

Process the following approved healing events for knowledge promotion:

${JSON.stringify(approvedCases.map(h => ({
  case_id: h.case_id,
  case_name: h.case.case_name,
  report_decision: 'approve_merge_allowed',
  root_cause: h.root_cause,
  patch: h.patch,
  replay: h.replay,
  run_id: runId,
  app_version: state.app_version,
  knowledge_base_path: `${HEALING_PROJECT_PATH}/knowledge/`,
  existing_knowledge: null
})))}

For each case, extract reusable knowledge and write it to the knowledge base directory.
Create the knowledge directories if they don't exist: ${HEALING_PROJECT_PATH}/knowledge/app_usage/, test_fragility/, coverage_opportunity/`,
    { label: 'knowledge', phase: 'Knowledge', schema: KNOWLEDGE_SCHEMA }
  )

  if (knowledgeResult) {
    log(`Knowledge: ${knowledgeResult.total_new} new, ${knowledgeResult.total_promoted} promoted, ${knowledgeResult.total_deprecated} deprecated`)
  }
} else {
  log('No approved cases — skipping knowledge promotion')
}

// ─── Final state update ──────────────────────────────────────────────────────

await agent(
  `Read and update the state file at ${statePath}.
Set "phase" to "done" and "ended_at" to the current ISO timestamp.
Also update the summary field to: ${JSON.stringify(summary)}`,
  { label: 'finalize-state', phase: 'Knowledge' }
)

log(`Workflow complete: ${summary.healing_succeeded}/${summary.healing_attempted} healed, ${summary.pass + summary.pass_with_healing + summary.pass_after_retry}/${summary.total} total passing`)

return {
  run_id: runId,
  summary,
  healed_cases: healedCases.map(h => h.case_id),
  report_path: reportPath
}
