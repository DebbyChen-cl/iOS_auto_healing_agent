# Auto-Healing Workflow 詳細流程

## 完整流程圖

```
pytest SFT/tests/ -m "online"
         │
         ▼
┌────────────────────────────────────────────────────────────┐
│  PHASE 1 — conftest.py（每個 test case 執行中）               │
│                                                             │
│  Input : test case function                                 │
│  Output: state.json 中的 case 記錄                           │
│  AI?   : ❌ 否                                              │
│                                                             │
│  test_case()                                                │
│    ├─ PASS → state: { original_status: "pass" }             │
│    │                                                        │
│    └─ FAIL                                                  │
│        │                                                    │
│        ├─ 收集 evidence → evidence/ 目錄                     │
│        │   ├── metadata.json                                │
│        │   ├── fail_moment.png                              │
│        │   ├── fail_moment_hierarchy.xml                    │
│        │   ├── stack_trace.txt                              │
│        │   └── step_*_before/after.*                        │
│        │                                                    │
│        ├─ _classify_failure_heuristic()                     │
│        │   Input : metadata.json（app_state + stack_trace）  │
│        │   Output: { action: "retry"|"deferred" }           │
│        │   AI?   : ❌ 純 Python 規則                         │
│        │                                                    │
│        │   Rules:                                           │
│        │   ├─ app_state ∈ [crash, black_screen] → retry     │
│        │   ├─ stack_trace 含 network 關鍵字 → retry          │
│        │   └─ 其他 → deferred                               │
│        │                                                    │
│        ├─ retry?                                            │
│        │   ├─ YES（且 budget ≤ 3）→ 原 protocol 內 retry 1x │
│        │   │   ├─ retry PASS → state: { original_status: "pass" }
│        │   │   └─ retry FAIL → 改標 deferred                │
│        │   └─ NO → deferred                                 │
│        │                                                    │
│        └─ state: { original_status: "fail",                 │
│                    scheduling: { action: "deferred" },      │
│                    evidence_path: "..." }                    │
└────────────────────────────────────────────────────────────┘
         │
         ▼  pytest_sessionfinish
         │
         ├─ _finalize_state_json()
         ├─ deferred cases > 0 ?
         │   ├─ NO  → 結束
         │   └─ YES → Popen('python3 orchestrator.py {run_id}')
         │            ↓  不 block，log → phase2.log
         ▼
┌────────────────────────────────────────────────────────────┐
│  PHASE 2 — orchestrator.py（pytest 結束後）                  │
│                                                             │
│  Input : run_id → 從 state.json 讀 deferred cases           │
│  Output: healing_results.json, 更新的 state.json, report.html│
│  AI?   : ✅ 每 case 一個 claude -p session                   │
│                                                             │
│  for case in deferred_cases (sequential):                   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  heal_case() — 一個 claude -p session                 │   │
│  │                                                       │   │
│  │  Input : case data (case_id, evidence_path, test_file)│   │
│  │  Model : claude-opus-4-6                              │   │
│  │  Max turns: 50                                        │   │
│  │  Timeout: 30 min                                      │   │
│  │  cwd: TEST_PROJECT                                    │   │
│  │                                                       │   │
│  │  ┌─ Step 1: Read evidence（只讀一次）                  │   │
│  │  │   Read: metadata.json, stack_trace.txt,            │   │
│  │  │         fail_moment_hierarchy.xml, fail_moment.png │   │
│  │  │                                                    │   │
│  │  ├─ Step 2: Root Cause 分類                           │   │
│  │  │   Output: type, confidence, l3_eligible            │   │
│  │  │   NOT L3 → write result.json → END                 │   │
│  │  │                                                    │   │
│  │  ├─ Step 3: Generate & Apply Patch                    │   │
│  │  │   Edit: locator/*.py, pages/*.py, SFT/tests/*.py   │   │
│  │  │                                                    │   │
│  │  │  ┌─────── Replay Loop (max 10x) ────────┐         │   │
│  │  │  │                                       │         │   │
│  │  ├──┤ Step 4: Bash: replay.py               │         │   │
│  │  │  │   Input : test_nodeid, TEST_PROJECT   │         │   │
│  │  │  │   Output: JSON {test_passed, exit_code│         │   │
│  │  │  │           new_error_summary}          │         │   │
│  │  │  │   AI?   : ❌                          │         │   │
│  │  │  │                                       │         │   │
│  │  │  │   test_passed == true                 │         │   │
│  │  │  │     → result.json (healed) → END      │         │   │
│  │  │  │                                       │         │   │
│  │  │  │   exit_code >= 2                      │         │   │
│  │  │  │     → result.json (infra_issue) → END │         │   │
│  │  │  │                                       │         │   │
│  │  │  │   test failed                         │         │   │
│  │  │  │     ↓                                 │         │   │
│  │  │  │ Step 5: Re-analyze（同 session）       │         │   │
│  │  │  │   新 error 已在 stdout → 不用重讀 evidence│        │   │
│  │  │  │   Generate DIFFERENT patch             │         │   │
│  │  │  │     → 回到 Step 4                      │         │   │
│  │  │  └───────────────────────────────────────┘         │   │
│  │  │                                                    │   │
│  │  └─ Step 6: Write result.json                         │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Finalize（Python，❌ 無 AI）                         │   │
│  │                                                       │   │
│  │  1. update_state.py                                   │   │
│  │     Input : healing_results.json                      │   │
│  │     Output: state.json（更新 root_cause, patch,        │   │
│  │             replay, final_status, summary）            │   │
│  │                                                       │   │
│  │  2. generate_report.py                                │   │
│  │     Input : state.json                                │   │
│  │     Output: report.html（固定模板，無 AI）              │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

---

## 每步驟 Input / Output 摘要

| 步驟 | Input | Output | AI? |
|------|-------|--------|-----|
| **Phase 1** ||||
| 執行 test | test function | PASS / FAIL | ❌ |
| 收集 evidence | test failure context | metadata.json, screenshot, hierarchy, stack_trace | ❌ |
| 分類 | metadata.json | { action: retry / deferred } | ❌ |
| Retry | test function | PASS / FAIL | ❌ |
| 寫 state.json | 分類結果 + evidence path | state.json case entry | ❌ |
| Trigger Phase 2 | state.json | Popen orchestrator.py | ❌ |
| **Phase 2** ||||
| orchestrator.py | run_id → state.json | loop over deferred cases | ❌ |
| heal_case (claude -p) | case data + evidence files | result.json | ✅ |
| ├─ Read evidence | evidence files | internal context | ✅ |
| ├─ Root cause | evidence content | type, confidence, l3_eligible | ✅ |
| ├─ Generate patch | root cause + source files | Edit to source files | ✅ |
| ├─ replay.py | test_nodeid, TEST_PROJECT | { test_passed, exit_code, error } | ❌ |
| ├─ Re-analyze | new error (in context) | new patch (Edit) | ✅ |
| update_state.py | healing_results.json | state.json 更新 | ❌ |
| generate_report.py | state.json | report.html | ❌ |

---

## Token 用量預估

### 新版（單 session per case）

| 情境 | Token 用量 |
|------|-----------|
| 一次成功（1 replay） | ~50K |
| 三次 replay 修復 | ~58K |
| 十次 replay 修復 | ~86K |
| 不符 L3（early exit） | ~20K |

**成本結構**：
- 基礎成本（讀 evidence + 分類 + 首次 patch）：~50K
- 每次 re-analyze 增量：~2.5K（error 已在 context，不需重讀 evidence）
- replay.py 本身不消耗 AI token

### 舊版（11 agents / 6 phases）比較

| 情境 | 舊版（11 agents） | 新版（1 session） | 節省 |
|------|------------------|------------------|------|
| 一次成功 | ~349K | ~50K | **86%** |
| 三次 replay | ~455K | ~58K | **87%** |
| 十次 replay | ~700K+ | ~86K | **88%** |

**節省來源**：
1. 移除 Load agent（~15K）
2. 移除 2 個 I/O 寫入 agents（~20K × 2）
3. 移除 Replay agent（~35K per attempt）
4. 移除 Finalize agent（~25K）
5. 合併 Root Cause + Patch 為同一 agent（省去重複讀取 evidence ~30K）
6. Re-analyze 在同 session（省去重新讀取所有 evidence ~45K per re-analysis）

---

## result.json 格式

Agent 在 session 結束前寫入 `runs/{run_id}/analysis/{case_id}/result.json`：

```json
{
  "root_cause": {
    "type": "locator_drift",
    "confidence": 0.92,
    "reason": "Button accessibility ID changed from 'btn_hair' to 'btn_hairstyle'",
    "evidence_used": ["metadata.json", "fail_moment_hierarchy.xml"],
    "excluded_causes": ["test_logic_error", "app_crash"],
    "healable": true,
    "l3_eligible": true,
    "blocking_impact": "low",
    "healing_risk": "low",
    "allowed_patch_boundary": "locator_only",
    "risk_flags": []
  },
  "patch": {
    "patch_created": true,
    "patch_type": "locator_update",
    "changed_files": [
      { "path": "locator/pdr_locator.py", "change": "Updated accessibility_id" }
    ],
    "diff_summary": "Updated btn_hair → btn_hairstyle in pdr_locator.py",
    "shared_locator_handling": "checked 3 other tests using same locator",
    "risk_flags": [],
    "reason": null
  },
  "replay": {
    "status": "pass_with_healing",
    "attempts": 1
  },
  "healed": true
}
```
