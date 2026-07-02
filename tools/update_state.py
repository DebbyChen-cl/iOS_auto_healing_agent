#!/usr/bin/env python3
"""Update state.json with healing results. No AI needed."""

import json
import sys
import os
from datetime import datetime


def update(run_id, healing_results, healing_project):
    state_path = os.path.join(healing_project, 'runs', run_id, 'state.json')

    with open(state_path, 'r', encoding='utf-8') as f:
        state = json.load(f)

    for h in healing_results:
        cid = h['case_id']
        if cid not in state.get('cases', {}):
            continue

        c = state['cases'][cid]
        if h.get('root_cause'):
            c['root_cause'] = {
                'type': h['root_cause'].get('type'),
                'confidence': h['root_cause'].get('confidence'),
                'reason': h['root_cause'].get('reason'),
                'healable': h['root_cause'].get('healable'),
                'l3_eligible': h['root_cause'].get('l3_eligible'),
                'risk_flags': h['root_cause'].get('risk_flags', []),
            }
        if h.get('patch'):
            c['patch'] = {
                'status': 'generated' if h['patch'].get('patch_created') else 'failed',
                'diff_summary': h['patch'].get('diff_summary'),
                'reason': h['patch'].get('reason'),
            }
        if h.get('replay'):
            c['replay'] = {
                'status': h['replay'].get('replay_status'),
                'attempts': h.get('attempts', 0),
            }

        c['final_status'] = h.get('final_status', 'fail')
        c['pr_eligible'] = h.get('healed', False)

    healed = sum(1 for h in healing_results if h.get('healed'))
    state['summary']['healed'] = healed
    state['summary']['healing_failed'] = sum(
        1 for h in healing_results if not h.get('healed') and h.get('attempts', 0) > 0
    )
    state['summary']['not_eligible'] = sum(
        1 for h in healing_results if h.get('attempts', 0) == 0
    )
    state['phase'] = 'done'
    state['ended_at'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    print(f'State updated: {healed} healed, {len(healing_results)} total')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python update_state.py <run_id> <results_json_path> [healing_project]')
        sys.exit(1)

    rid = sys.argv[1]
    results_path = sys.argv[2]
    project = sys.argv[3] if len(sys.argv) > 3 else '/Users/rdqe/Desktop/iOS_auto_healing_skills'

    with open(results_path, 'r', encoding='utf-8') as f:
        results = json.load(f)

    update(rid, results, project)
