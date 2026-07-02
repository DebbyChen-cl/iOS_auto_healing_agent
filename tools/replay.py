#!/usr/bin/env python3
"""Run pytest for a single test case and return structured result. No AI needed."""

import json
import subprocess
import sys
import re


def replay(test_nodeid, test_project, attempt=1):
    try:
        result = subprocess.run(
            ['python3', '-m', 'pytest', test_nodeid, '-x', '--timeout=300', '--tb=short', '-q'],
            capture_output=True, text=True, cwd=test_project, timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {
            'test_passed': False,
            'exit_code': 2,
            'attempt_number': attempt,
            'replay_status': 'infra_issue',
            'new_error_summary': 'pytest timed out (600s)',
            'stdout': '',
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
    if len(sys.argv) < 3:
        print('Usage: python replay.py <test_nodeid> <test_project> [attempt]')
        sys.exit(1)

    nodeid = sys.argv[1]
    project = sys.argv[2]
    attempt_num = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    out = replay(nodeid, project, attempt_num)
    print(json.dumps(out, indent=2))
