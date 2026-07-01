"""
Phase 1 離線驗證腳本（不需要 device）
驗證 state.json 初始化、registry bootstrap、claude CLI 連線

用法：
    cd /Users/rdqe/Desktop/rdqe-ios-autotest-phdm
    python3 /Users/rdqe/Desktop/iOS_auto_healing_skills/tests/test_phase1_dry_run.py
"""

import json
import os
import subprocess
import sys
import time
import shutil

HEALING_PROJECT = '/Users/rdqe/Desktop/iOS_auto_healing_skills'
TEST_PROJECT = '/Users/rdqe/Desktop/rdqe-ios-autotest-phdm'
TEST_RUN_ID = f'test-dryrun-{int(time.time())}'

results = []


def check(name, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    results.append((name, status, detail))
    print(f'  [{status}] {name}' + (f' — {detail}' if detail else ''))
    return condition


def cleanup():
    test_run_dir = os.path.join(HEALING_PROJECT, 'runs', TEST_RUN_ID)
    if os.path.exists(test_run_dir):
        shutil.rmtree(test_run_dir)


def main():
    print(f'\n{"="*60}')
    print(f'  Auto-Healing Phase 1 Dry Run')
    print(f'  Run ID: {TEST_RUN_ID}')
    print(f'{"="*60}\n')

    # ─── 1. 環境檢查 ───────────────────────────────────
    print('1. 環境檢查')

    check('claude CLI 存在', shutil.which('claude') is not None)

    r = subprocess.run(['claude', '--version'], capture_output=True, text=True)
    check('claude CLI 可執行', r.returncode == 0, r.stdout.strip())

    check('Healing 專案存在', os.path.exists(HEALING_PROJECT))
    check('Test 專案存在', os.path.exists(TEST_PROJECT))
    check('conftest.py 存在', os.path.exists(os.path.join(TEST_PROJECT, 'SFT/conftest.py')))
    check('Phase1 skill 存在', os.path.exists(
        os.path.join(HEALING_PROJECT, 'auto_healing_skills/auto-healing-phase1-decision/SKILL.md')))

    # ─── 2. state.json 初始化 ──────────────────────────
    print('\n2. state.json 初始化')

    run_dir = os.path.join(HEALING_PROJECT, 'runs', TEST_RUN_ID)
    os.makedirs(run_dir, exist_ok=True)
    state_path = os.path.join(run_dir, 'state.json')

    state = {
        'run_id': TEST_RUN_ID,
        'branch': 'test',
        'commit': 'dryrun',
        'app_version': '20.10.0',
        'device': 'iPhone 15 Pro Max',
        'ios_version': '18.5',
        'started_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'ended_at': None,
        'phase': 'phase_1',
        'immediate_retry_budget': {'max_cases': 3, 'used': 0, 'max_time_increase_pct': 15},
        'cases': {},
        'summary': {'total': 0, 'pass': 0, 'fail': 0, 'pass_with_healing': 0,
                    'pass_after_retry': 0, 'deferred': 0, 'manual_review': 0,
                    'product_bug': 0, 'healing_attempted': 0, 'healing_succeeded': 0},
    }

    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)
    check('state.json 建立成功', os.path.exists(state_path))

    with open(state_path) as f:
        loaded = json.load(f)
    check('state.json 可讀取', loaded['run_id'] == TEST_RUN_ID)
    check('state.json schema 正確', all(k in loaded for k in ['cases', 'summary', 'phase']))

    # ─── 3. Case 更新模擬 ──────────────────────────────
    print('\n3. state.json case 更新模擬')

    loaded['cases']['PHD-IOS-TEST-001'] = {
        'case_name': 'test_dry_run',
        'test_file': 'SFT/tests/test_dry.py::TestDry::test_001',
        'original_status': 'fail',
        'error_summary': 'Element not found: import_button',
        'error_type': 'NoSuchElementException',
        'scheduling': {'lane': 'C', 'action': 'deferred',
                       'preliminary_category': 'locator_drift',
                       'reason': 'test dry run'},
        'retry': None,
        'root_cause': None, 'patch': None, 'replay': None,
        'final_status': None, 'pr_eligible': False,
    }
    loaded['summary']['total'] = 1
    loaded['summary']['fail'] = 1
    loaded['summary']['deferred'] = 1

    with open(state_path, 'w') as f:
        json.dump(loaded, f, indent=2)

    with open(state_path) as f:
        verify = json.load(f)
    check('case 寫入成功', 'PHD-IOS-TEST-001' in verify['cases'])
    check('case 欄位完整', verify['cases']['PHD-IOS-TEST-001']['scheduling']['lane'] == 'C')

    # ─── 4. Registry 目錄 ─────────────────────────────
    print('\n4. Registry 目錄')

    registry_dir = os.path.join(HEALING_PROJECT, 'registry')
    os.makedirs(registry_dir, exist_ok=True)
    check('registry 目錄存在', os.path.exists(registry_dir))

    # ─── 5. Claude CLI 連線測試 ────────────────────────
    print('\n5. Claude CLI 連線測試（這會花 10-30 秒）')

    try:
        r = subprocess.run(
            ['claude', '-p', 'Return exactly this JSON: {"status": "ok", "test": true}',
             '--output-format', 'json'],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode == 0:
            output = json.loads(r.stdout)
            result_text = output.get('result', str(output))
            check('claude CLI 回應成功', True, f'returncode=0')
            check('claude CLI JSON 輸出', isinstance(output, dict), result_text[:100])
        else:
            check('claude CLI 回應成功', False, f'returncode={r.returncode}, stderr={r.stderr[:200]}')
    except subprocess.TimeoutExpired:
        check('claude CLI 回應成功', False, 'timeout after 60s')
    except Exception as e:
        check('claude CLI 回應成功', False, str(e))

    # ─── 6. Skill 讀取測試 ─────────────────────────────
    print('\n6. Skill 檔案檢查')

    skills = [
        'auto-healing-phase1-decision',
        'auto-healing-root-cause',
        'auto-healing-patch-generation',
        'auto-healing-replay-verification',
        'auto-healing-html-report-approval',
        'auto-healing-knowledge-promotion',
    ]
    for skill in skills:
        path = os.path.join(HEALING_PROJECT, 'auto_healing_skills', skill, 'SKILL.md')
        exists = os.path.exists(path)
        if exists:
            with open(path) as f:
                content = f.read()
            has_frontmatter = content.startswith('---')
            has_user_invocable_false = 'user-invocable: false' in content
            check(f'{skill}',
                  has_frontmatter and has_user_invocable_false,
                  f'{len(content)} bytes, frontmatter={"ok" if has_frontmatter else "missing"}, '
                  f'non-invocable={"ok" if has_user_invocable_false else "missing"}')
        else:
            check(f'{skill}', False, 'file not found')

    # ─── 7. Workflow 檢查 ──────────────────────────────
    print('\n7. Workflow 檔案檢查')

    wf_path = os.path.join(HEALING_PROJECT, 'workflow', 'auto_healing.js')
    check('auto_healing.js 存在', os.path.exists(wf_path))
    if os.path.exists(wf_path):
        with open(wf_path) as f:
            wf = f.read()
        check('export const meta 存在', 'export const meta' in wf)
        check('6 phases 定義', wf.count("phase(") >= 5)
        check('schema 定義', 'ROOT_CAUSE_SCHEMA' in wf and 'PATCH_SCHEMA' in wf)

    # ─── Summary ──────────────────────────────────────
    print(f'\n{"="*60}')
    passed = sum(1 for _, s, _ in results if s == 'PASS')
    failed = sum(1 for _, s, _ in results if s == 'FAIL')
    print(f'  結果：{passed} passed, {failed} failed')

    if failed > 0:
        print(f'\n  失敗項目：')
        for name, status, detail in results:
            if status == 'FAIL':
                print(f'    ✗ {name}: {detail}')

    print(f'\n  測試 state.json 位置：{state_path}')
    print(f'{"="*60}\n')

    # Cleanup prompt
    if failed == 0:
        print(f'全部通過！可以進行 Step 2（device 測試）。')
        print(f'清理測試資料：rm -rf {run_dir}')
    else:
        print(f'有失敗項目，請先修復再繼續。')

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
