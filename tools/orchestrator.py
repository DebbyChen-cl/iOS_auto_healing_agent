#!/usr/bin/env python3
"""
Phase 2 orchestrator.
- One claude -p session per case (via --session-id / --resume): analyze + patch only.
- Orchestrator (this process) runs replay.py directly and drives the
  replay -> re-analyze loop — claude never executes pytest itself.
- State update + report via Python scripts (no AI)
"""

import json
import os
import subprocess
import sys
import threading
import time
import uuid

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
HEALING_PROJECT = os.environ.get(
    'HEALING_PROJECT', os.path.dirname(TOOLS_DIR)
)
TEST_PROJECT = os.environ.get(
    'TEST_PROJECT',
    os.path.join(os.path.dirname(HEALING_PROJECT), 'rdqe-ios-autotest-phdm-auto-heal'),
)
MAX_ATTEMPTS = 10
REPLAY_TIMEOUT = 5400  # 90 min — some cases run long test flows
CLAUDE_TURN_TIMEOUT = 900  # 15 min — one analyze/patch turn, no test execution inside it

AGENT_MD = os.path.join(HEALING_PROJECT, '.claude', 'agents', 'analyze-and-patch.md')

DECISION_SCHEMA = {
    'type': 'object',
    'required': ['root_cause', 'patch'],
    'properties': {
        'root_cause': {
            'type': 'object',
            'required': ['type', 'confidence', 'reason', 'healable', 'l3_eligible'],
            'properties': {
                'type': {'type': 'string'},
                'confidence': {'type': 'number'},
                'reason': {'type': 'string'},
                'evidence_used': {'type': 'array', 'items': {'type': 'string'}},
                'excluded_causes': {'type': 'array', 'items': {'type': 'string'}},
                'healable': {'type': 'boolean'},
                'l3_eligible': {'type': 'boolean'},
                'blocking_impact': {'type': 'string'},
                'healing_risk': {'type': 'string'},
                'allowed_patch_boundary': {'type': 'string'},
                'risk_flags': {'type': 'array', 'items': {'type': 'string'}},
            },
        },
        'patch': {
            'type': ['object', 'null'],
            'required': ['patch_created'],
            'properties': {
                'patch_created': {'type': 'boolean'},
                'patch_type': {'type': 'string'},
                'changed_files': {'type': 'array'},
                'diff_summary': {'type': 'string'},
                'shared_locator_handling': {'type': 'string'},
                'risk_flags': {'type': 'array', 'items': {'type': 'string'}},
                'reason': {'type': 'string'},
            },
        },
    },
}


def _log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)


def _describe_tool(name, tool_input):
    tool_input = tool_input or {}
    if name == 'Bash':
        cmd = tool_input.get('command', '')
        desc = tool_input.get('description', '')
        return f'Bash: {desc or cmd[:160]}'
    if name == 'Edit':
        return f'editing {tool_input.get("file_path", "?")}'
    if name == 'Write':
        return f'writing {tool_input.get("file_path", "?")}'
    if name == 'Read':
        return f'reading {tool_input.get("file_path", "?")}'
    return name


def _print_stream_event(case_id, obj):
    """Print a single stream-json event from the claude turn as a
    human-readable progress line. Pure printing — no extra AI calls."""
    etype = obj.get('type')

    if etype == 'assistant':
        for block in obj.get('message', {}).get('content', []):
            btype = block.get('type')
            if btype == 'text':
                text = block.get('text', '').strip()
                if text:
                    _log(f'  [{case_id}] {text}')
            elif btype == 'tool_use' and block.get('name') != 'StructuredOutput':
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
        _log(f'  [{case_id}] turn done: {obj.get("num_turns", "?")} turns, '
             f'{obj.get("duration_ms", "?")}ms')


def _read_agent_instructions():
    with open(AGENT_MD, 'r', encoding='utf-8') as f:
        content = f.read()
    if content.startswith('---'):
        end = content.index('---', 3)
        content = content[end + 3:].strip()
    return content


# ─── One claude turn: analyze + patch (no test execution) ────────────────────

def _run_claude_turn(prompt, session_id, resume, case_id):
    """Run one headless claude turn. Returns the validated decision dict
    (root_cause/patch) from structured_output, or None on failure/timeout."""
    cmd = ['claude', '-p', prompt, '--max-turns', '30',
           '--permission-mode', 'acceptEdits',
           '--output-format', 'stream-json', '--verbose',
           '--json-schema', json.dumps(DECISION_SCHEMA)]
    cmd += ['--resume', session_id] if resume else ['--session-id', session_id]

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, cwd=TEST_PROJECT,
    )

    timed_out = threading.Event()
    timer = threading.Timer(CLAUDE_TURN_TIMEOUT, lambda: (timed_out.set(), proc.kill()))
    timer.start()

    structured = None
    result_obj = None
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
            if obj.get('type') == 'result':
                result_obj = obj
                structured = obj.get('structured_output')
        proc.wait()
    finally:
        timer.cancel()

    if timed_out.is_set():
        _log(f'  [{case_id}] claude turn timed out ({CLAUDE_TURN_TIMEOUT}s)')
        return None
    if proc.returncode != 0 or structured is None:
        err = (result_obj or {}).get('result')
        _log(f'  [{case_id}] claude turn failed (exit {proc.returncode}): {err}')
        return None
    return structured


# ─── Replay: plain Python subprocess, no Bash-tool timeout involved ──────────

def _run_replay(case, context_file=None, not_healed_reason=None):
    cmd = ['python3', os.path.join(TOOLS_DIR, 'replay.py'),
           case.get('test_file', ''), TEST_PROJECT]
    if context_file:
        cmd += ['--context-file', context_file]
    if not_healed_reason:
        cmd += ['--not-healed-reason', not_healed_reason]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=REPLAY_TIMEOUT + 60,
        )
    except subprocess.TimeoutExpired:
        return {
            'test_passed': False, 'exit_code': 2, 'replay_status': 'infra_issue',
            'new_error_summary': 'orchestrator-level replay timeout exceeded',
            'stdout': '',
        }

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            'test_passed': False, 'exit_code': 2, 'replay_status': 'infra_issue',
            'new_error_summary': f'replay.py produced no valid JSON: {proc.stdout[-500:]}',
            'stdout': proc.stdout[-2000:],
        }


# ─── One case: analyze -> patch -> replay -> re-analyze loop ──────────────────

def heal_case(case, run_id):
    case_id = case['case_id']
    result_dir = os.path.join(HEALING_PROJECT, 'runs', run_id, 'analysis', case_id)
    os.makedirs(result_dir, exist_ok=True)
    result_path = os.path.join(result_dir, 'result.json')
    context_path = os.path.join(result_dir, 'context.json')

    session_id = str(uuid.uuid4())
    instructions = _read_agent_instructions()

    def _write_result(root_cause, patch, replay_status, attempts, healed):
        result = {
            'root_cause': root_cause,
            'patch': patch,
            'replay': {'status': replay_status, 'attempts': attempts},
            'healed': healed,
        }
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        return result

    def _give_up(root_cause, patch, reason):
        replay_result = _run_replay(case, not_healed_reason=reason)
        return _write_result(root_cause, patch, replay_result.get('replay_status', 'not_healed'), 0, False)

    initial_prompt = f"""{instructions}

Your task for this case:

Case: {case_id}
Name: {case.get('case_name', '')}
Error: {case.get('error_summary', 'unknown')}
Error type: {case.get('error_type', 'unknown')}
Evidence: {TEST_PROJECT}/{case.get('evidence_path', '')}
Test file: {TEST_PROJECT}/{case.get('test_file', '')}
Test project root: {TEST_PROJECT}

Steps:
1. Read evidence files, classify root cause, determine L3 eligibility.
2. If NOT L3-eligible: do not patch. Return your decision with patch.patch_created=false and patch.reason set.
3. If L3-eligible: generate the smallest patch and apply it directly to the source files in the test project (use Edit). Then return your decision with the patch details filled in.

You will NOT run the test yourself — a separate process replays it and will come back to you with the result if it fails. Just return your analysis and patch decision as structured output now."""

    _log(f'  [{case_id}] starting analyze+patch turn...')
    decision = _run_claude_turn(initial_prompt, session_id, resume=False, case_id=case_id)
    if decision is None:
        return None

    root_cause = decision.get('root_cause')
    patch = decision.get('patch')

    if not root_cause.get('l3_eligible') or not patch or not patch.get('patch_created'):
        reason = (patch or {}).get('reason') or root_cause.get('reason')
        return _give_up(root_cause, patch, reason)

    attempts = 0
    while attempts < MAX_ATTEMPTS:
        attempts += 1
        with open(context_path, 'w', encoding='utf-8') as f:
            json.dump({'root_cause': root_cause, 'patch': patch}, f, ensure_ascii=False)

        _log(f'  [{case_id}] replay attempt {attempts}...')
        replay_result = _run_replay(case, context_file=context_path)

        if replay_result.get('test_passed'):
            return _write_result(root_cause, patch, replay_result.get('replay_status', 'pass_with_healing'),
                                  attempts, True)

        if replay_result.get('exit_code', 0) >= 2:
            return _write_result(root_cause, patch, 'infra_issue', attempts, False)

        if attempts >= MAX_ATTEMPTS:
            break

        reanalyze_prompt = f"""Replay attempt {attempts} failed after your patch. New error from the test run:

{replay_result.get('new_error_summary')}

Test output (tail):
{replay_result.get('stdout', '')[-2000:]}

Re-analyze using this new evidence — you already have full context from before, no need to re-read the evidence files unless the new error suggests something you missed. Generate a DIFFERENT patch than before targeting the actual new failure. Apply it directly to the source files (use Edit). If you now determine the case is not fixable or not L3-eligible, set patch.patch_created=false with patch.reason and do not edit anything further.

Return your updated decision as structured output."""

        _log(f'  [{case_id}] re-analyzing after failed attempt {attempts}...')
        decision = _run_claude_turn(reanalyze_prompt, session_id, resume=True, case_id=case_id)
        if decision is None:
            break

        root_cause = decision.get('root_cause')
        patch = decision.get('patch')

        if not root_cause.get('l3_eligible') or not patch or not patch.get('patch_created'):
            reason = (patch or {}).get('reason') or root_cause.get('reason')
            return _give_up(root_cause, patch, reason)

    return _write_result(root_cause, patch, 'fail', attempts, False)


# ─── Commit + push healing changes to a new timestamped branch ──────────────

def _run_git(args, cwd):
    return subprocess.run(['git'] + args, cwd=cwd, capture_output=True, text=True)


def _commit_and_push_healing_changes(run_id, healed_count, total_count):
    """After heal completes, if any patches were applied to the test project,
    commit them on a new branch '{current_branch}_YYMMDD_hhmmss' and push it."""
    status = _run_git(['status', '--porcelain'], TEST_PROJECT)
    if status.returncode != 0:
        _log(f'  [git] status check failed: {status.stderr.strip()}')
        return
    if not status.stdout.strip():
        _log('  [git] no changes to commit, skipping')
        return

    branch = _run_git(['rev-parse', '--abbrev-ref', 'HEAD'], TEST_PROJECT).stdout.strip()
    if not branch or branch == 'HEAD':
        _log('  [git] could not determine current branch, skipping commit')
        return

    new_branch = f'{branch}_{time.strftime("%y%m%d_%H%M%S")}'

    steps = [
        (['checkout', '-b', new_branch], 'create branch'),
        (['add', '-A'], 'stage changes'),
        (['commit', '-m',
          f'Auto-heal: apply patches from run {run_id} ({healed_count}/{total_count} healed)'],
         'commit'),
        (['push', '-u', 'origin', new_branch], 'push'),
    ]
    for args, desc in steps:
        result = _run_git(args, TEST_PROJECT)
        if result.returncode != 0:
            _log(f'  [git] {desc} failed: {result.stderr.strip()}')
            return

    _log(f'  [git] committed and pushed changes to {new_branch}')


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

    _commit_and_push_healing_changes(run_id, healed_count, len(deferred_cases))

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
