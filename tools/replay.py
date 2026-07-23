#!/usr/bin/env python3
"""Run pytest for a single test case and return structured result. No AI needed."""

import argparse
import json
import os
import subprocess
import sys
import re


def replay(test_nodeid, test_project, attempt=1, context_file=None, not_healed_reason=None):
    # AUTO_HEALING_REPLAY tells the test project's conftest.py this is an internal
    # replay verification, not a new top-level run: it skips creating a new
    # state.json/run folder and skips sending the "final result" email.
    env = {**os.environ, 'AUTO_HEALING_REPLAY': '1'}

    cmd = ['python3', '-m', 'pytest', test_nodeid, '-x', '--tb=short', '-q']

    # If the caller (SFT/conftest.py, via orchestrator.py) knows the original
    # run's still-open ReportPortal launch, attach this replay's results to it
    # instead of starting a new launch — pytest-reportportal treats rp_launch_id
    # as an externally-provided launch UUID, so start_launch()/finish_launch()
    # become no-ops and results just get reported into that launch.
    # With no launch id known (e.g. a standalone/manual replay run), fall
    # through to the default addopts and let it open its own new launch.
    launch_id = os.environ.get('AUTO_HEALING_RP_LAUNCH_ID')
    if launch_id:
        cmd.append(f'--override-ini=rp_launch_id={launch_id}')

    if context_file:
        try:
            with open(context_file, 'r', encoding='utf-8') as f:
                env['AUTO_HEALING_CONTEXT'] = f.read()
        except Exception as e:
            print(f'Warning: could not read context file {context_file}: {e}', file=sys.stderr)

    if not_healed_reason:
        env['AUTO_HEALING_NOT_HEALED_REASON'] = not_healed_reason

    REPLAY_TIMEOUT = 5400  # 90 min — some cases run long test flows

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=test_project, timeout=REPLAY_TIMEOUT, env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            'test_passed': False,
            'exit_code': 2,
            'attempt_number': attempt,
            'replay_status': 'infra_issue',
            'new_error_summary': f'pytest timed out ({REPLAY_TIMEOUT}s)',
            'stdout': '',
        }

    if not_healed_reason:
        # The test was never actually executed — conftest.py marks it skipped
        # at collection time so it still shows up (same name) in the same
        # ReportPortal launch, carrying the not-healed reason as its message.
        return {
            'test_passed': None,
            'exit_code': result.returncode,
            'attempt_number': attempt,
            'replay_status': 'not_healed',
            'reason': not_healed_reason,
            'stdout': result.stdout[-2000:] if result.stdout else '',
        }

    test_passed = result.returncode == 0
    error_summary = None

    if not test_passed:
        lines = (result.stdout + '\n' + result.stderr).strip().splitlines()
        for line in reversed(lines):
            line = line.strip()
            if line and ('Error' in line or 'FAILED' in line or 'assert' in line.lower()):
                error_summary = line[:500]
                break
        if not error_summary and lines:
            error_summary = lines[-1][:500]

    if test_passed:
        status = 'pass_with_healing'
    elif result.returncode >= 2:
        status = 'infra_issue'
    else:
        status = 'fail'

    return {
        'test_passed': test_passed,
        'exit_code': result.returncode,
        'attempt_number': attempt,
        'replay_status': status,
        'new_error_summary': error_summary,
        'stdout': result.stdout[-2000:] if result.stdout else '',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('test_nodeid')
    parser.add_argument('test_project')
    parser.add_argument('attempt', nargs='?', type=int, default=1)
    parser.add_argument('--context-file', default=None,
                         help='Path to a file with the current root_cause/patch summary; '
                              'its content gets logged onto this replay\'s RP test item.')
    parser.add_argument('--not-healed-reason', default=None,
                         help='If set, skip actually running the test — just record a '
                              'SKIPPED test item (same name) with this reason.')
    args = parser.parse_args()

    out = replay(args.test_nodeid, args.test_project, args.attempt,
                 context_file=args.context_file, not_healed_reason=args.not_healed_reason)
    print(json.dumps(out, indent=2))
