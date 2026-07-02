#!/usr/bin/env python3
"""
Phase 2 orchestrator.
- One claude -p session per case: analyze → patch → replay → re-analyze loop (same session)
- Replay runs via Bash inside the session (replay.py, no extra AI)
- State update + report via Python scripts (no AI)
"""

import json
import os
import subprocess
import sys
import time

HEALING_PROJECT = os.environ.get(
    'HEALING_PROJECT', '/Users/rdqe/Desktop/iOS_auto_healing_skills'
)
TEST_PROJECT = os.environ.get(
    'TEST_PROJECT', '/Users/rdqe/Desktop/rdqe-ios-autotest-phdm'
)
MAX_ATTEMPTS = 10

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_MD = os.path.join(HEALING_PROJECT, '.claude', 'agents', 'analyze-and-patch.md')


def _log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)


def _read_agent_instructions():
    with open(AGENT_MD, 'r', encoding='utf-8') as f:
        content = f.read()
    if content.startswith('---'):
        end = content.index('---', 3)
        content = content[end + 3:].strip()
    return content


# ─── One session per case: analyze + patch + replay loop ─────────────────────

def heal_case(case, run_id):
    """One claude -p session handles the full loop for one case.
    Re-analysis stays in the same session — no re-reading evidence."""
    case_id = case['case_id']
    result_dir = os.path.join(HEALING_PROJECT, 'runs', run_id, 'analysis', case_id)
    os.makedirs(result_dir, exist_ok=True)
    result_path = os.path.join(result_dir, 'result.json')

    instructions = _read_agent_instructions()
    prompt = f"""{instructions}

Your complete task for this case — do everything in this session:

Case: {case_id}
Name: {case.get('case_name', '')}
Error: {case.get('error_summary', 'unknown')}
Error type: {case.get('error_type', 'unknown')}
Evidence: {TEST_PROJECT}/{case.get('evidence_path', '')}
Test file: {TEST_PROJECT}/{case.get('test_file', '')}
Test project root: {TEST_PROJECT}

Steps:
1. Read evidence files, classify root cause, determine L3 eligibility
2. If NOT L3-eligible → write result.json and stop
3. Generate patch and apply it directly to source files
4. Run replay: python3 {TOOLS_DIR}/replay.py "{case.get('test_file', '')}" "{TEST_PROJECT}"
5. Parse the JSON from stdout
6. If test_passed == true → healed, write result.json and stop
7. If exit_code >= 2 → infra error, write result.json and stop
8. If test failed → re-analyze using the new error (you already have all context), generate a DIFFERENT patch, go back to step 4
9. Maximum {MAX_ATTEMPTS} replay attempts
10. Write final result to: {result_path}

Result JSON format:
{{
  "root_cause": {{ type, confidence, reason, evidence_used, excluded_causes, healable, l3_eligible, blocking_impact, healing_risk, allowed_patch_boundary, risk_flags }},
  "patch": {{ patch_created, patch_type, changed_files, diff_summary, shared_locator_handling, risk_flags, reason }},
  "replay": {{ "status": "pass_with_healing"|"fail"|"infra_issue", "attempts": N }},
  "healed": true|false
}}"""

    _log(f'  [{case_id}] starting session (analyze → patch → replay loop)...')

    result = subprocess.run(
        ['claude', '-p', prompt, '--max-turns', '50'],
        capture_output=True, text=True, timeout=1800,
        cwd=TEST_PROJECT,
    )

    if result.returncode != 0:
        _log(f'  [{case_id}] claude session failed (exit {result.returncode})')

    try:
        with open(result_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        _log(f'  [{case_id}] failed to read result: {e}')
        return None


# ─── Main ───────────────────────────────────────────────────────────────────

def main(run_id, deferred_cases):
    _log(f'Phase 2 start: {len(deferred_cases)} deferred cases')

    healing_results = []

    for case in deferred_cases:
        case_id = case['case_id']
        _log(f'── Case: {case_id} ──')

        result = heal_case(case, run_id)

        if result:
            healing_results.append({
                'case_id': case_id,
                'root_cause': result.get('root_cause'),
                'patch': result.get('patch'),
                'replay': result.get('replay'),
                'healed': result.get('healed', False),
                'attempts': result.get('replay', {}).get('attempts', 0) if result.get('replay') else 0,
                'final_status': 'pass_with_healing' if result.get('healed') else (
                    result.get('replay', {}).get('status', 'healing_failed') if result.get('replay') else
                    ('manual_review_required' if result.get('root_cause') else 'fail')
                ),
            })
        else:
            healing_results.append({
                'case_id': case_id,
                'root_cause': None, 'patch': None, 'replay': None,
                'healed': False, 'attempts': 0, 'final_status': 'fail',
            })

    # ── Finalize (Python, no AI) ──
    _log('── Finalize ──')

    results_path = os.path.join(HEALING_PROJECT, 'runs', run_id, 'healing_results.json')
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(healing_results, f, indent=2, ensure_ascii=False)

    subprocess.run(
        ['python3', os.path.join(TOOLS_DIR, 'update_state.py'),
         run_id, results_path, HEALING_PROJECT],
    )
    subprocess.run(
        ['python3', os.path.join(TOOLS_DIR, 'generate_report.py'),
         run_id, HEALING_PROJECT],
    )

    healed_count = sum(1 for h in healing_results if h['healed'])
    _log(f'Done: {healed_count}/{len(deferred_cases)} healed')
    return healing_results


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python orchestrator.py <run_id> [cases_json_path]')
        print('  If cases_json_path not given, reads deferred cases from state.json')
        sys.exit(1)

    rid = sys.argv[1]

    if len(sys.argv) >= 3:
        with open(sys.argv[2], 'r', encoding='utf-8') as f:
            cases = json.load(f)
    else:
        state_path = os.path.join(HEALING_PROJECT, 'runs', rid, 'state.json')
        with open(state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
        cases = []
        for cid, c in state.get('cases', {}).items():
            if c.get('scheduling', {}).get('action') == 'deferred':
                cases.append({
                    'case_id': cid,
                    'case_name': c.get('case_name'),
                    'error_summary': c.get('error_summary'),
                    'error_type': c.get('error_type'),
                    'evidence_path': c.get('evidence_path'),
                    'test_file': c.get('test_file'),
                })

    main(rid, cases)
