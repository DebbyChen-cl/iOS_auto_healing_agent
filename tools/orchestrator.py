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
import threading
import time

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
HEALING_PROJECT = os.environ.get(
    'HEALING_PROJECT', os.path.dirname(TOOLS_DIR)
)
TEST_PROJECT = os.environ.get(
    'TEST_PROJECT',
    os.path.join(os.path.dirname(HEALING_PROJECT), 'rdqe-ios-autotest-phdm-auto-heal'),
)
MAX_ATTEMPTS = 10

AGENT_MD = os.path.join(HEALING_PROJECT, '.claude', 'agents', 'analyze-and-patch.md')


def _log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)


def _describe_tool(name, tool_input):
    tool_input = tool_input or {}
    if name == 'Bash':
        cmd = tool_input.get('command', '')
        desc = tool_input.get('description', '')
        if 'replay.py' in cmd:
            return f'running replay ({desc or cmd})'
        return f'Bash: {desc or cmd[:160]}'
    if name == 'Edit':
        return f'editing {tool_input.get("file_path", "?")}'
    if name == 'Write':
        return f'writing {tool_input.get("file_path", "?")}'
    if name == 'Read':
        return f'reading {tool_input.get("file_path", "?")}'
    return name


def _print_stream_event(case_id, obj):
    """Print a single stream-json event from the claude session as a
    human-readable progress line. Pure printing — no extra AI calls."""
    etype = obj.get('type')

    if etype == 'assistant':
        for block in obj.get('message', {}).get('content', []):
            btype = block.get('type')
            if btype == 'text':
                text = block.get('text', '').strip()
                if text:
                    _log(f'  [{case_id}] {text}')
            elif btype == 'tool_use':
                _log(f'  [{case_id}] → {_describe_tool(block.get("name"), block.get("input"))}')

    elif etype == 'user':
        for block in obj.get('message', {}).get('content', []):
            if block.get('type') != 'tool_result':
                continue
            content = block.get('content')
            if isinstance(content, list):
                content = '\n'.join(
                    c.get('text', '') for c in content if isinstance(c, dict)
                )
            if isinstance(content, str) and content.strip():
                snippet = '\n'.join(content.strip().splitlines()[:15])
                for snippet_line in snippet.splitlines():
                    _log(f'  [{case_id}]     {snippet_line}')

    elif etype == 'result':
        _log(f'  [{case_id}] session done: {obj.get("num_turns", "?")} turns, '
             f'{obj.get("duration_ms", "?")}ms')


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

    # The claude -p session is sandboxed to TEST_PROJECT — it has no filesystem
    # access outside it, so it can't write result.json directly under
    # HEALING_PROJECT. Have it write inside TEST_PROJECT instead, then this
    # (unsandboxed) parent process copies the file over afterward.
    session_result_dir = os.path.join(TEST_PROJECT, 'Self-healing', 'analysis', case_id)
    os.makedirs(session_result_dir, exist_ok=True)
    session_result_path = os.path.join(session_result_dir, 'result.json')
    context_path = os.path.join(session_result_dir, 'context.json')

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
2. If NOT L3-eligible → write your root_cause (and patch.reason) summary to {context_path} as {{"root_cause": {{...}}, "patch": null}}, then run:
   python3 {TOOLS_DIR}/replay.py "{case.get('test_file', '')}" "{TEST_PROJECT}" --not-healed-reason "<short reason from root_cause.reason>"
   This does NOT run the real test — it only records a SKIPPED entry (same test name) in the report, carrying the reason. Then write result.json and stop.
3. Generate patch and apply it directly to source files
4. Before each replay attempt, write your current root_cause + patch summary to {context_path} (same shape as the Result JSON's root_cause/patch fields), then run replay:
   python3 {TOOLS_DIR}/replay.py "{case.get('test_file', '')}" "{TEST_PROJECT}" --context-file "{context_path}"
5. Parse the JSON from stdout
6. If test_passed == true → healed, write result.json and stop
7. If exit_code >= 2 → infra error, write result.json and stop
8. If test failed → re-analyze using the new error (you already have all context), generate a DIFFERENT patch, update {context_path}, go back to step 4
9. Maximum {MAX_ATTEMPTS} replay attempts
10. Write final result to: {session_result_path}

Result JSON format:
{{
  "root_cause": {{ type, confidence, reason, evidence_used, excluded_causes, healable, l3_eligible, blocking_impact, healing_risk, allowed_patch_boundary, risk_flags }},
  "patch": {{ patch_created, patch_type, changed_files, diff_summary, shared_locator_handling, risk_flags, reason }},
  "replay": {{ "status": "pass_with_healing"|"fail"|"infra_issue", "attempts": N }},
  "healed": true|false
}}"""

    _log(f'  [{case_id}] starting session (analyze → patch → replay loop)...')

    proc = subprocess.Popen(
        ['claude', '-p', prompt, '--max-turns', '50',
         '--permission-mode', 'acceptEdits',
         '--output-format', 'stream-json', '--verbose'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, cwd=TEST_PROJECT,
    )

    timed_out = threading.Event()
    timer = threading.Timer(1800, lambda: (timed_out.set(), proc.kill()))
    timer.start()

    try:
        for line in proc.stdout:
            line = line.rstrip('\n')
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                _log(f'  [{case_id}] {line}')
                continue
            _print_stream_event(case_id, obj)
        proc.wait()
    finally:
        timer.cancel()

    if timed_out.is_set():
        _log(f'  [{case_id}] claude session timed out (1800s)')
    elif proc.returncode != 0:
        _log(f'  [{case_id}] claude session failed (exit {proc.returncode})')

    try:
        with open(session_result_path, 'r', encoding='utf-8') as f:
            parsed = json.load(f)
    except Exception as e:
        _log(f'  [{case_id}] failed to read result: {e}')
        return None

    try:
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(parsed, f, indent=2, ensure_ascii=False)
    except Exception as e:
        _log(f'  [{case_id}] failed to archive result to {result_path}: {e}')

    return parsed


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
