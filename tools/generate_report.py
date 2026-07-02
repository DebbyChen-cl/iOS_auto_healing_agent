#!/usr/bin/env python3
"""Generate HTML report from state.json. No AI needed — fixed template."""

import json
import sys
import os
from datetime import datetime

STATUS_COLORS = {
    'pass': '#22c55e',
    'pass_with_healing': '#3b82f6',
    'pass_after_retry': '#a855f7',
    'pass_after_app_crash_retry': '#a855f7',
    'pass_after_network_retry': '#a855f7',
    'healing_failed': '#ef4444',
    'manual_review_required': '#f59e0b',
    'product_bug': '#dc2626',
    'fail': '#ef4444',
    'deferred': '#6b7280',
}

STATUS_LABELS = {
    'pass': 'Pass',
    'pass_with_healing': 'Healed',
    'pass_after_retry': 'Pass (retry)',
    'pass_after_app_crash_retry': 'Pass (crash retry)',
    'pass_after_network_retry': 'Pass (network retry)',
    'healing_failed': 'Healing Failed',
    'manual_review_required': 'Manual Review',
    'product_bug': 'Product Bug',
    'fail': 'Fail',
    'deferred': 'Deferred',
}


def badge(status):
    color = STATUS_COLORS.get(status, '#6b7280')
    label = STATUS_LABELS.get(status, status)
    return f'<span style="background:{color};color:#fff;padding:2px 10px;border-radius:12px;font-size:13px;font-weight:600">{label}</span>'


def esc(text):
    if text is None:
        return '—'
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def generate(state_path, output_path):
    with open(state_path, 'r', encoding='utf-8') as f:
        state = json.load(f)

    run_id = state.get('run_id', 'unknown')
    summary = state.get('summary', {})
    cases = state.get('cases', {})

    case_rows = []
    detail_sections = []

    for case_id, c in cases.items():
        status = c.get('final_status') or c.get('original_status', 'unknown')
        case_rows.append(f'''
        <tr>
          <td style="font-family:monospace;font-size:13px">{esc(case_id)}</td>
          <td>{esc(c.get('case_name'))}</td>
          <td>{badge(status)}</td>
          <td>{esc(c.get('root_cause', {}).get('type') if c.get('root_cause') else None)}</td>
          <td>{esc(c.get('error_type'))}</td>
        </tr>''')

        rc = c.get('root_cause')
        patch = c.get('patch')
        replay = c.get('replay')

        detail_sections.append(f'''
        <div style="border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:16px">
          <h3 style="margin:0 0 12px">{esc(case_id)} — {esc(c.get('case_name'))} {badge(status)}</h3>
          <table style="width:100%;border-collapse:collapse;font-size:14px">
            <tr><td style="padding:4px 8px;color:#6b7280;width:160px">Error</td><td style="padding:4px 8px">{esc(c.get('error_summary'))}</td></tr>
            <tr><td style="padding:4px 8px;color:#6b7280">Error Type</td><td style="padding:4px 8px">{esc(c.get('error_type'))}</td></tr>
            <tr><td style="padding:4px 8px;color:#6b7280">Evidence</td><td style="padding:4px 8px;font-family:monospace;font-size:12px">{esc(c.get('evidence_path'))}</td></tr>
            {f'<tr><td style="padding:4px 8px;color:#6b7280">Root Cause</td><td style="padding:4px 8px"><b>{esc(rc.get("type"))}</b> (confidence: {rc.get("confidence", "?")})<br>{esc(rc.get("reason"))}</td></tr>' if rc else ''}
            {f'<tr><td style="padding:4px 8px;color:#6b7280">L3 Eligible</td><td style="padding:4px 8px">{"Yes" if rc.get("l3_eligible") else "No"} — blocking: {esc(rc.get("blocking_impact"))}, risk: {esc(rc.get("healing_risk"))}</td></tr>' if rc else ''}
            {f'<tr><td style="padding:4px 8px;color:#6b7280">Patch</td><td style="padding:4px 8px">{esc(patch.get("diff_summary") or patch.get("reason"))}</td></tr>' if patch else ''}
            {f'<tr><td style="padding:4px 8px;color:#6b7280">Replay</td><td style="padding:4px 8px">{esc(replay.get("status"))} ({replay.get("attempts", "?")} attempts)</td></tr>' if replay else ''}
          </table>
        </div>''')

    summary_items = []
    for key in ['total', 'deferred', 'analyzed', 'patched', 'healed', 'healing_failed', 'not_eligible']:
        if key in summary:
            summary_items.append(f'<div style="text-align:center;padding:12px"><div style="font-size:28px;font-weight:700">{summary[key]}</div><div style="font-size:12px;color:#6b7280">{key.replace("_", " ").title()}</div></div>')

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Auto-Healing Report — {esc(run_id)}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 960px; margin: 0 auto; padding: 24px; color: #1f2937; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  h2 {{ font-size: 17px; margin: 32px 0 12px; border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ text-align: left; padding: 8px; border-bottom: 2px solid #e5e7eb; font-size: 13px; color: #6b7280; }}
  td {{ padding: 8px; border-bottom: 1px solid #f3f4f6; }}
  tr:hover {{ background: #f9fafb; }}
</style>
</head>
<body>

<h1>Auto-Healing Report</h1>
<p style="color:#6b7280;margin:0 0 24px">Run: <code>{esc(run_id)}</code> &nbsp;|&nbsp; Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

<div style="display:flex;gap:8px;flex-wrap:wrap;background:#f9fafb;border-radius:8px;padding:8px 16px;margin-bottom:24px">
  {''.join(summary_items)}
</div>

<h2>Cases</h2>
<table>
  <thead>
    <tr>
      <th>Case ID</th>
      <th>Name</th>
      <th>Status</th>
      <th>Root Cause</th>
      <th>Error Type</th>
    </tr>
  </thead>
  <tbody>
    {''.join(case_rows)}
  </tbody>
</table>

<h2>Details</h2>
{''.join(detail_sections)}

</body>
</html>'''

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'Report written to {output_path}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python generate_report.py <run_id> [healing_project_path]')
        sys.exit(1)

    run_id = sys.argv[1]
    project = sys.argv[2] if len(sys.argv) > 2 else '/Users/rdqe/Desktop/iOS_auto_healing_skills'

    state_path = os.path.join(project, 'runs', run_id, 'state.json')
    output_path = os.path.join(project, 'runs', run_id, 'report.html')

    if not os.path.exists(state_path):
        print(f'ERROR: {state_path} not found')
        sys.exit(1)

    generate(state_path, output_path)
