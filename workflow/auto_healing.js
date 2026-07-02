// NOTE: This workflow is kept as a BACKUP entry point for manual use via the
// Claude Code Workflow tool. The primary entry point is tools/orchestrator.py,
// which removes the need for replay and finalize agents entirely.
//
// Usage (manual): Workflow({ scriptPath: "workflow/auto_healing.js", args: { run_id: "...", cases: [...] } })
// Usage (primary): python3 tools/orchestrator.py <run_id>

export const meta = {
  name: 'auto-healing',
  description: 'Backup: parallel analyze-and-patch via Workflow tool (primary path is tools/orchestrator.py)',
  phases: [
    { title: 'Analyze & Patch', detail: 'Parallel root cause analysis + patch generation per case' },
  ]
}

const HEALING_PROJECT = '/Users/rdqe/Desktop/iOS_auto_healing_skills'
const TEST_PROJECT = '/Users/rdqe/Desktop/rdqe-ios-autotest-phdm'

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

const runId = args?.run_id
const deferredCases = args?.cases

if (!runId || !deferredCases?.length) {
  log('ERROR: args must contain run_id and cases[]')
  return { error: 'run_id and cases[] are required' }
}

phase('Analyze & Patch')
log(`Run ${runId}: ${deferredCases.length} deferred cases`)

const results = await parallel(deferredCases.map(c => () =>
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
  ).then(r => ({ case_id: c.case_id, result: r }))
))

const valid = results.filter(Boolean)
const patched = valid.filter(r => r.result?.patch?.patch_created).length

log(`Done: ${valid.length} analyzed, ${patched} patched`)

return { run_id: runId, results: valid }
