#!/usr/bin/env python3
"""
Phase 2 orchestrator. Replaces the Workflow for replay + finalize.
- Parallel analyze-and-patch via claude -p (ThreadPoolExecutor)
- Sequential replay via direct subprocess (no agent)
- Re-analysis via claude -p when replay fails
- State update + report via Python scripts (no agent)
"""

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HEALING_PROJECT = os.environ.get(
    'HEALING_PROJECT', '/Users/rdqe/Desktop/iOS_auto_healing_skills'
)
TEST_PROJECT = os.environ.get(
    'TEST_PROJECT', '/Users/rdqe/Desktop/rdqe-ios-autotest-phdm'
)
MAX_ATTEMPTS = 10
MAX_PARALLEL = 3

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


def _call_claude(prompt, timeout=600):
    result = subprocess.run(
        ['claude', '-p', prompt, '--max-turns', '15'],
        capture_output=True, text=True, timeout=timeout,
        cwd=TEST_PROJECT,
    )
    return result.returncode == 0


# ─── Analyze & Patch ────────────────────────────────────────────────────────

def analyze_and_patch(case, run_id, extra_context=''):
    case_id = case['case_id']
    result_dir = os.path.join(HEALING_PROJECT, 'runs', run_id, 'analysis', case_id)
    os.makedirs(result_dir, exist_ok=True)
    result_path = os.path.join(result_dir, 'result.json')

    instructions = _read_agent_instructions()
    prompt = f"""{instructions}

Analyze this failed test case and generate a patch if L3-eligible.

Case: {case_id}
Name: {case.get('case_name', '')}
Error: {case.get('error_summary', 'unknown')}
Error type: {case.get('error_type', 'unknown')}
Evidence: {TEST_PROJECT}/{case.get('evidence_path', '')}
Test file: {TEST_PROJECT}/{case.get('test_file', '')}
Test project root: {TEST_PROJECT}
{extra_context}

Read the evidence files, classify root cause, and generate patch if eligible.
Apply the patch directly to the source files.

After you finish, write your complete result as JSON to: {result_path}
The JSON must have exactly two top-level keys: "root_cause" and "patch".
- root_cause: type, confidence, reason, evidence_used, excluded_causes, healable, l3_eligible, blocking_impact, healing_risk, allowed_patch_boundary, risk_flags
- patch: patch_created (bool), patch_type, changed_files, diff_summary, shared_locator_handling, risk_flags, reason"""

    _log(f'  [{case_id}] calling claude for analysis...')
    _call_claude(prompt, timeout=900)

    try:
        with open(result_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        _log(f'  [{case_id}] failed to read result: {e}')
        return None


def reanalyze(case, prev_result, replay_result, run_id, attempt):
    extra = f"""Previous root cause: {prev_result['root_cause']['type']} — {prev_result['root_cause'].get('reason', '')}
Previous patch: {prev_result['patch'].get('diff_summary', '')}
New error after replay: {replay_result.get('new_error_summary', 'unknown')}
Pytest output (last 1000 chars): {replay_result.get('stdout', '')[-1000:]}
Attempt: {attempt} — generate a DIFFERENT patch than previous attempts"""

    case_copy = dict(case)
    result_dir = os.path.join(HEALING_PROJECT, 'runs', run_id, 'analysis', case['case_id'])
    result_path = os.path.join(result_dir, f'result_attempt_{attempt}.json')

    instructions = _read_agent_instructions()
    prompt = f"""{instructions}

The previous patch was applied but the test still fails with a NEW error.
Re-analyze and generate a new patch.

Case: {case['case_id']}
Name: {case.get('case_name', '')}
Evidence: {TEST_PROJECT}/{case.get('evidence_path', '')}
Test file: {TEST_PROJECT}/{case.get('test_file', '')}
Test project root: {TEST_PROJECT}
{extra}

Read the evidence, identify the NEW root cause, and generate a new patch if L3-eligible.
Apply the patch directly to the source files.

Write your result JSON to: {result_path}
Same format: root_cause + patch."""

    _log(f'  [{case["case_id"]}] re-analyzing (attempt {attempt})...')
    _call_claude(prompt, timeout=900)

    try:
        with open(result_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        _log(f'  [{case["case_id"]}] re-analysis failed: {e}')
        return None


# ─── Replay ─────────────────────────────────────────────────────────────────

def replay(test_nodeid, attempt):
    """Run pytest directly. No agent, no AI."""
    result = subprocess.run(
        ['python3', os.path.join(TOOLS_DIR, 'replay.py'),
         test_nodeid, TEST_PROJECT, str(attempt)],
        capture_output=True, text=True, timeout=660,
    )
    try:
        return json.loads(result.stdout)
    except Exception:
        return {
            'test_passed': False, 'exit_code': 2, 'attempt_number': attempt,
            'replay_status': 'infra_issue', 'new_error_summary': result.stderr[:500],
        }


# ─── Main ───────────────────────────────────────────────────────────────────

def main(run_id, deferred_cases):
    _log(f'Phase 2 start: {len(deferred_cases)} deferred cases')

    # ── 1. Parallel analyze-and-patch ──
    _log('── Analyze & Patch (parallel) ──')
    analyze_results = {}

    workers = min(len(deferred_cases), MAX_PARALLEL)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(analyze_and_patch, c, run_id): c
            for c in deferred_cases
        }
        for future in as_completed(futures):
            case = futures[future]
            try:
                result = future.result()
            except Exception as e:
                _log(f'  [{case["case_id"]}] exception: {e}')
                result = None
            analyze_results[case['case_id']] = {
                'case': case, 'result': result,
            }

    patched = {cid: ar for cid, ar in analyze_results.items()
               if ar['result'] and ar['result'].get('patch', {}).get('patch_created')}
    not_patched = {cid: ar for cid, ar in analyze_results.items() if cid not in patched}

    _log(f'Analysis done: {len(patched)} patched, {len(not_patched)} not patched')

    # ── 2. Sequential replay loop ──
    _log('── Replay (sequential) ──')
    healing_results = []

    for case_id, ar in patched.items():
        case = ar['case']
        current = ar['result']
        healed = False
        last_replay = None
        attempt = 0

        for attempt in range(1, MAX_ATTEMPTS + 1):
            _log(f'  [{case_id}] replay attempt {attempt}/{MAX_ATTEMPTS}')
            last_replay = replay(case.get('test_file', ''), attempt)

            if last_replay['test_passed']:
                healed = True
                _log(f'  [{case_id}] HEALED on attempt {attempt}')
                break

            if last_replay.get('exit_code', 1) >= 2:
                _log(f'  [{case_id}] infra issue — stopping')
                break

            if attempt >= MAX_ATTEMPTS:
                _log(f'  [{case_id}] max attempts reached')
                break

            new_analysis = reanalyze(case, current, last_replay, run_id, attempt + 1)
            if not new_analysis or not new_analysis.get('patch', {}).get('patch_created'):
                _log(f'  [{case_id}] re-analysis cannot produce patch — stopping')
                break

            current = new_analysis

        final_status = 'pass_with_healing' if healed else (
            last_replay.get('replay_status', 'healing_failed') if last_replay else 'healing_failed'
        )

        healing_results.append({
            'case_id': case_id,
            'root_cause': current.get('root_cause'),
            'patch': current.get('patch'),
            'replay': last_replay,
            'healed': healed,
            'attempts': attempt,
            'final_status': final_status,
        })

    for case_id, ar in not_patched.items():
        rc = ar['result'].get('root_cause') if ar['result'] else None
        healing_results.append({
            'case_id': case_id,
            'root_cause': rc,
            'patch': ar['result'].get('patch') if ar['result'] else None,
            'replay': None,
            'healed': False,
            'attempts': 0,
            'final_status': 'manual_review_required' if rc else 'fail',
        })

    # ── 3. Update state + report ──
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
    _log(f'Done: {healed_count}/{len(patched)} healed, {len(not_patched)} not eligible')
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
