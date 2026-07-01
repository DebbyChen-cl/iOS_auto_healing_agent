# Auto-Healing Agent 架構決策紀錄

本文件記錄 2026-07-01 討論定案的架構決策。

## 一、整體架構：兩階段設計

```
Phase 1: During AT Run (pytest session, ~14hrs, 200 cases)
├── conftest.py 執行測試
├── 每個 case fail 時：
│   ├── 收集 evidence（已完成）
│   ├── 呼叫 claude CLI（一次性 subprocess）判斷分類 + retry 決策
│   ├── 若 retry → pytest_runtest_protocol 內重跑一次
│   └── 更新 state.json
└── pytest 結束，state.json + evidence/ 完成

Phase 2: After AT Run (Claude Code Workflow)
├── 讀 state.json + evidence
├── AI Root Cause Analysis（parallel per case）
├── AI Patch Generation → Replay Verification（pipeline per case）
├── Final Reconciliation + HTML Report + PR Generation
└── Knowledge Promotion
```

## 二、已定案決策

### 2.1 Phase 1：conftest.py + claude CLI

| 決策 | 結論 |
|------|------|
| AI 參與方式 | `subprocess.run(["claude", "-p", prompt, "--output-format", "json"])` — 每次 fail 叫一次，做完就關 |
| Retry 機制 | `pytest_runtest_protocol` hook 接管，retry 包在 protocol 內部，對 pytest / ReportPortal 不可見 |
| Evidence 收集 | 沿用現有 `_collect_failure_evidence()` + `metadata.json`（failure_evidence_v1 schema） |
| Evidence 路徑 | 沿用 `Self-healing/evidence/{timestamp}-{test_name}/` |
| State 寫入 | conftest.py 在每個 case 結束後更新 state.json |
| Retry 上限 | 每個 case 最多 retry 一次；全域上限 3 個 case 或 +15% 時間 |
| Retry 結果標註 | RP 看到最終結果（pass 或 fail）；state.json 保留 `pass_after_*` 品質訊號 |
| 原始 evidence 保留 | retry 前的 evidence 保留，不因 retry pass 而刪除 |

### 2.2 Phase 2：Claude Code Workflow

| 決策 | 結論 |
|------|------|
| 編排機制 | Workflow script（agent / pipeline / parallel） |
| State 寫入權 | Workflow 統一寫入 state.json；sub-agent 只回傳 structured output |
| Agent 溝通 | prompt 只帶 summary + evidence_path；agent 需要 details 時自己 Read |
| 並行策略 | Root Cause Analysis 可 parallel；Replay Verification 必須序列（單一 device） |

### 2.3 Sub-agent 粒度

需要 AI 的 gate（5 個 sub-agent）：

| Gate | Agent 類型 | 說明 |
|------|-----------|------|
| G07 AI Root Cause | agent per case | 讀 evidence + screenshot + hierarchy，分析 root cause |
| G11 Patch Generation | agent per case | 根據 root cause 生成 patch diff |
| G12 Replay Verification | agent per case（序列） | 套 patch 後重跑，驗證是否通過。需要 device，不能並行 |
| G14 HTML Report | agent per run | 彙整所有 case 結果，生成 reviewer 審核用 HTML report |
| G16 Knowledge Promotion | agent per run | 從 approved event 萃取長期知識 |

不需要 AI 的 gate（Workflow JS 邏輯或 conftest.py）：

| Gate | 處理方式 | 說明 |
|------|---------|------|
| G01 Test Identity | 查 registry JSON | conftest.py 讀取 `@pytest.mark.case_id` |
| G02 Context Capture | conftest.py | 已完成，寫入 metadata.json |
| G03 Previous Result | 查 history JSON | Workflow JS 邏輯 |
| G04 Pass Baseline | conftest.py | pass case 保留最小 baseline，已有 `_cleanup_passed_evidence()` |
| G05 Failure Evidence | conftest.py | 已完成，rule-based 驗完整性 |
| G06 Preliminary Classify | Phase 1 claude CLI | 初步分類 |
| G08 Scheduling Decision | Phase 1 claude CLI | Lane A/B/C/D 判斷 |
| G09 Immediate Action | conftest.py | pytest_runtest_protocol 內 retry |
| G10 Deferred Queue | Workflow JS | 排序 deferred cases |
| G13 Final Reconciliation | Workflow JS | 合併原始 / retry / healing 結果 |
| G15 PR Generation | Workflow JS + gh CLI | `gh pr create` + template |

### 2.4 State 管理

| 項目 | 位置 | 寫入者 |
|------|------|--------|
| state.json | `runs/{run_id}/state.json` | Phase 1: conftest.py / Phase 2: Workflow |
| Evidence | `Self-healing/evidence/{timestamp}-{test_name}/` | conftest.py |
| Analysis | `runs/{run_id}/analysis/{case_id}/` | Workflow（存 agent 詳細輸出） |
| Patches | `runs/{run_id}/patches/{case_id}/` | Workflow |
| Replay | `runs/{run_id}/replay/{case_id}/` | Workflow |
| Report | `runs/{run_id}/report.html` | Workflow |
| Test Registry | `registry/test_registry.json` | 手動 / bootstrap script（跨 run 持久） |
| History | `registry/history.json` | Workflow（跨 run 持久） |
| Knowledge | `knowledge/{type}/` | Workflow（跨 run 持久） |

### 2.5 Retry 機制

```python
pytest_runtest_protocol (tryfirst=True)
  ├─ 第一次跑: runtestprotocol(item)
  ├─ 失敗？
  │   ├─ 收集 evidence
  │   ├─ subprocess 呼叫 claude CLI 判斷
  │   └─ 不 retry → 回報原始結果
  ├─ retry？
  │   ├─ 保存原始 evidence（不刪）
  │   ├─ 第二次跑: runtestprotocol(item)  ← driver fixture 重啟 App
  │   └─ 只回報 retry 結果給 pytest / ReportPortal
  └─ 更新 state.json（保留原始 + retry 雙結果）
```

不衝突的原因：
- ReportPortal 只收到一筆最終結果
- driver() fixture 是 function-scoped，retry 時會重新 setup
- retry 在 protocol 內部完成，下一個 test 正常排隊

## 三、Phase 2 Workflow 結構

```javascript
export const meta = {
  name: 'auto-healing',
  description: 'Phase 2: AI root cause, patch, replay, report, PR, knowledge',
  phases: [
    { title: 'Root Cause Analysis' },
    { title: 'Healing' },
    { title: 'Report & PR' },
    { title: 'Knowledge' }
  ]
}

// 1. 讀 state.json，過濾 deferred cases
// 2. Root Cause: parallel agent per case
// 3. Healing: pipeline per healable case (patch → replay，replay 序列)
// 4. Final Reconciliation: JS 邏輯合併狀態
// 5. HTML Report: agent per run
// 6. PR Generation: JS + gh CLI
// 7. Knowledge Promotion: agent per run
```

## 四、資料夾結構

```
iOS_auto_healing_skills/                    # 專案根目錄
├── auto_healing_skills/                    # 已有：skills (SKILL.md)
├── SPEC/                                   # 已有：specs
├── runs/                                   # 每次 AT run 的輸出
│   └── {run_id}/
│       ├── state.json                      # 核心狀態檔
│       ├── analysis/{case_id}/             # root cause 詳細輸出
│       │   └── root_cause.json
│       ├── patches/{case_id}/              # patch 詳細輸出
│       │   ├── patch.diff
│       │   └── meta.json
│       ├── replay/{case_id}/               # replay 詳細輸出
│       │   ├── replay_screenshot.png
│       │   └── result.json
│       └── report.html                     # HTML report
├── registry/                               # 跨 run 持久
│   ├── test_registry.json                  # Stable Case ID 對照表
│   └── history.json                        # Previous result history
├── knowledge/                              # 跨 run 持久
│   ├── app_usage/
│   ├── test_fragility/
│   └── coverage_opportunity/
└── workflow/                               # Workflow scripts
    └── auto_healing.js
```

Evidence 資料夾沿用現有位置：
```
rdqe-ios-autotest-phdm/                     # 測試專案
└── Self-healing/evidence/
    └── {timestamp}-{test_name}/
        ├── metadata.json
        ├── fail_moment.png
        ├── fail_moment_hierarchy.xml
        ├── stack_trace.txt
        └── step_*_before/after.png/xml
```

## 五、state.json schema

```jsonc
{
  "run_id": "run-20260701-220000",
  "branch": "main",
  "commit": "abc1234",
  "app_version": "20.10.0",
  "device": "iPhone 15 Pro Max",
  "ios_version": "18.5",
  "started_at": "2026-07-01T22:00:00",
  "ended_at": null,
  "phase": "phase_1",
  // phase_1 | phase_2_root_cause | phase_2_healing | phase_2_report | done

  "immediate_retry_budget": {
    "max_cases": 3,
    "used": 0,
    "max_time_increase_pct": 15
  },

  "cases": {
    "PHD-IOS-IMPORT-001": {
      // identity
      "case_name": "test_import_photo_from_album",
      "test_file": "SFT/tests/test_pytest_iPHD_SFT_sce_01.py::TestImport::test_import_photo",
      "feature": "Import",
      "priority": "P0",
      "blocking_type": "blocking",

      // phase 1: original result
      "original_status": "fail",
      "error_summary": "Element 'import_button' not found after 10s",
      "error_type": "element_not_found",
      "fail_step": { "id": "step_003", "order": 3, "action": "tap import_button" },
      "evidence_path": "Self-healing/evidence/20260701-223045-test_import_photo/",
      "evidence_complete": true,

      // phase 1: AI scheduling (claude CLI)
      "scheduling": {
        "lane": "C",
        "action": "deferred",
        "preliminary_category": "locator_drift",
        "reason": "locator mismatch, non-blocking for current run"
      },

      // phase 1: retry (null if no retry)
      "retry": null,
      // { "count": 1, "reason": "app_crash", "result": "pass",
      //   "status_after": "pass_after_app_crash_retry",
      //   "evidence_path": "Self-healing/evidence/20260701-223145-test_import_retry/" }

      // phase 2: root cause (Workflow 寫入)
      "root_cause": null,
      // { "type": "locator_drift", "confidence": 0.92,
      //   "reason": "accessibility id changed",
      //   "healable": true, "risk_flags": [],
      //   "detail_path": "runs/run-xxx/analysis/PHD-IOS-IMPORT-001/root_cause.json" }

      // phase 2: patch (Workflow 寫入)
      "patch": null,
      // { "status": "generated",
      //   "diff_summary": "ImportPage.py: 更新 import_button locator",
      //   "risk_flags": [],
      //   "detail_path": "runs/run-xxx/patches/PHD-IOS-IMPORT-001/" }

      // phase 2: replay (Workflow 寫入)
      "replay": null,
      // { "status": "pass", "attempts": 1,
      //   "detail_path": "runs/run-xxx/replay/PHD-IOS-IMPORT-001/" }

      // phase 2: final
      "final_status": null,
      // "pass_with_healing" | "healing_failed" | "manual_review_required" | etc.
      "pr_eligible": false
    }
  },

  "summary": {
    "total": 200,
    "pass": 0,
    "fail": 0,
    "pass_with_healing": 0,
    "pass_after_retry": 0,
    "deferred": 0,
    "manual_review": 0,
    "product_bug": 0,
    "healing_attempted": 0,
    "healing_succeeded": 0
  }
}
```

## 六、conftest.py 需要修改的部分

基於 `/Users/rdqe/Desktop/rdqe-ios-autotest-phdm/SFT/conftest.py`（已完成 evidence 收集），需要新增：

### 6.1 新增 `pytest_runtest_protocol` hook

- 接管測試執行流程
- 第一次跑：正常執行
- 失敗時：呼叫 claude CLI 做 scheduling 判斷
- 若需要 retry：在 protocol 內重跑一次
- 回報最終結果給 pytest / ReportPortal

### 6.2 新增 `ask_claude_scheduling()` function

- `subprocess.run(["claude", "-p", prompt, "--output-format", "json"])`
- prompt 引用 auto-healing-scheduling-decision skill
- 讀取 evidence_path 下的 metadata.json + screenshot
- 回傳 `{ "lane": "A|B|C|D", "action": "retry|deferred|manual|no_healing", "preliminary_category": "...", "reason": "..." }`

### 6.3 新增 state.json 管理

- `_init_state_json()`: pytest_configure 時建立 state.json 骨架
- `_update_case_state()`: 每個 case 結束後更新對應欄位
- `_finalize_state_json()`: pytest_sessionfinish 時計算 summary、標 phase 為 phase_1 完成

### 6.4 新增 retry budget 管理

- 全域計數器追蹤已 retry 次數
- 超過上限後不再 retry，改標 deferred

### 6.5 修改現有 `pytest_runtest_makereport` hook

- 需要跟新的 `pytest_runtest_protocol` 協調
- evidence 收集仍在 makereport 觸發，但 retry 的第二次執行也需要收集

## 七、跨專案架構

兩個獨立 repo，Workflow 有兩邊的存取權限：

```
/Users/rdqe/Desktop/iOS_auto_healing_skills/    # Skills + Specs + Workflow + State
├── auto_healing_skills/    → sub-agent 讀取 SKILL.md
├── SPEC/                   → 參考規格
├── runs/                   → state.json + analysis + patches + replay + report
├── registry/               → test_registry.json + history.json
├── knowledge/              → 長期知識
└── workflow/               → auto_healing.js

/Users/rdqe/Desktop/rdqe-ios-autotest-phdm/     # 測試碼 + Evidence
├── SFT/conftest.py         → Phase 1 修改（retry hook + claude CLI + state.json）
├── Self-healing/evidence/  → evidence 資料夾
├── SFT/tests/              → 測試碼（patch generation 修改對象）
├── pages/                  → page object（patch generation 修改對象）
└── locator/                → locator 定義（patch generation 修改對象）
```

## 八、Skill 架構改造

### 8.1 三類 Skill

現有 16 個 SKILL.md 重新分類：

**Sub-agent Skills（5 個，重寫）— AI sub-agent 讀取執行：**

| 新 Skill | 合併自 | 對應 Gate |
|----------|--------|-----------|
| `auto-healing-root-cause` | failure-taxonomy + l3-eligibility | G07 |
| `auto-healing-patch-generation` | patch-generation（改格式） | G11 |
| `auto-healing-replay-verification` | replay-verification（改格式） | G12 |
| `auto-healing-html-report` | html-report-approval（改格式） | G14 |
| `auto-healing-knowledge-promotion` | knowledge-promotion（改格式） | G16 |

**Phase 1 Skill（1 個，新建）— conftest.py 的 claude CLI 讀取：**

| 新 Skill | 合併自 | 用途 |
|----------|--------|------|
| `auto-healing-phase1-decision` | failure-taxonomy + scheduling-decision | 即時分類 + retry/defer 決策 |

**Reference Skills（原有保留）— 供 conftest.py / Workflow JS 實作規則參考：**

不給 agent 讀，保留作為規則的原始文件。包含 test-identity、failure-evidence、
retry-policy、pass-baseline、previous-result-history、final-reconciliation、
pr-generation、new-case-generator、metrics。

### 8.2 Sub-agent Skill 新結構

所有 sub-agent skill 統一格式：

```markdown
---
name: auto-healing-{gate}
description: "Sub-agent skill for..."
user-invocable: false
---

# Role
你是 auto-healing 系統的 {角色}。
Workflow 給你一個 case 的摘要和 evidence 路徑。

# Input from Workflow
你會收到的欄位說明。

# 你需要讀取的檔案
1. {evidence_path}/metadata.json
2. {evidence_path}/fail_moment.png
3. ...（依 gate 不同）

# 規則
從對應 SPEC 提煉的核心規則。
（不再引用 SPEC 路徑，直接內嵌關鍵規則）

# Forbidden
不可做的事。

# Output（structured JSON）
回傳 schema 的完整定義。
```

關鍵改動：
- `user-invocable: false`
- 加 Role 和 Input from Workflow 段落
- 規則直接內嵌（不引用 SPEC 路徑，減少 agent 的 Read 次數）
- Output 改為 structured JSON schema
- Root cause agent 順便做 identity_enrichment（自動補齊 registry）

### 8.3 Workflow 裡的 agent 呼叫

```javascript
agent(
  `先讀取 ${SKILLS_PATH}/auto-healing-root-cause/SKILL.md 了解你的角色和規則。
   然後分析這個 case：
   
   Case: ${c.case_id}
   Error: ${c.error_summary}
   Category: ${c.preliminary_category}
   Evidence: ${c.evidence_path}`,
  { schema: ROOT_CAUSE_SCHEMA, phase: 'Root Cause Analysis' }
)
```

SKILL.md 更新時 agent 自動拿到最新版，Workflow script 不需要改。

### 8.4 Main Agent（Workflow）不需要 Skill

Workflow 是 JS 腳本，不是 Claude agent。
現有的 `auto-healing-workflow/SKILL.md` 轉為 Workflow script 的 README。

## 九、Test Registry 動態建立 + AI 自動補齊

### 9.1 Bootstrap（pytest_collection_modifyitems 自動生成骨架）

| 欄位 | 自動生成方式 | 例子 |
|------|-------------|------|
| stable_case_id | 從 test path hash 或流水號 | `PHD-IOS-AUTO-001` |
| case_name | `item.name` | `test_import_photo_from_album` |
| test_file | `str(item.fspath)` | `SFT/tests/test_pytest_iPHD_SFT_sce_01.py` |
| test_nodeid | `item.nodeid` | `SFT/tests/...::TestImport::test_import_photo` |
| feature | 從資料夾名 / class 名推斷，不確定時標 `null` | `Import` 或 `null` |
| priority | 預設 `P2` | `P2` |
| blocking_type | 預設 `non-blocking` | `non-blocking` |
| app_area | `null`（待 AI 補） | `null` |
| primary_test_component | `null`（待 AI 補） | `null` |
| identity_complete | `false` | `false` |

### 9.2 AI 自動補齊（Phase 2 healing 過程中）

當 root cause agent 分析某個 case 時，它已經讀了 evidence（screenshot、hierarchy、error）和 test code。
順便補齊 registry 中該 case 的缺失欄位：

- **feature** — 從 test code 的操作流程推斷（例如看到 ImportPage → Import）
- **app_area** — 從 fail screenshot 的畫面判斷（例如看到匯入選擇器 → Import Picker）
- **primary_test_component** — 從 test code 的 page object import 推斷
- **priority** — 從 blocking impact 分析建議（但不覆蓋人工標註）
- **blocking_type** — 從 dependency 分析建議

AI 補齊後標 `identity_complete: true`，但 priority 和 blocking_type 的 AI 建議標 `ai_suggested: true`，人工確認後改為 `confirmed: true`。

### 9.3 零人工介入流程

```
第一次跑 pytest
  → pytest_collection_modifyitems 自動建 registry 骨架
  → 200 個 case 都有 ID + name + file，但 feature/area/component 多數是 null

某個 case fail 進入 Phase 2 healing
  → root cause agent 讀 evidence + test code
  → 順便補齊該 case 的 feature / app_area / primary_test_component
  → Workflow 寫回 registry

跑越多輪，registry 越完整
  → 不需要人工標註
  → 只有 priority / blocking_type 的 AI 建議需要人工確認（可選）
```

Registry JSON 存在 `iOS_auto_healing_skills/registry/test_registry.json`

## 十、Replay 機制

Replay 使用 pytest 跑單一 case：

```bash
# Workflow agent 透過 Bash tool 執行
cd /Users/rdqe/Desktop/rdqe-ios-autotest-phdm
pytest SFT/tests/test_file.py::TestClass::test_method -m "case_id" --override-ini="rp_enabled=false"
```

- 套用 patch 後，用 pytest 跑指定的單一 test case
- 關閉 ReportPortal（replay 結果不應進 RP）
- driver fixture 會處理 App 重啟
- 收集 replay evidence（screenshot + result）
- 最多 3 個 patch attempts，同一份 patch 不重跑

## 十一、已定案原則（承自 auto_healing_todo.md）

1. 目標成熟度 L3：AI 可自動套用低風險修補並建立 PR，但不能自動 merge
2. AI 不能修改 assertion 程式碼、expected value 或驗證邏輯
3. AI 修復後通過的 case 標 `pass_with_healing`，不可標成 `pass`
4. HTML report 是主要人工審核介面，approve 後才允許 merge PR
5. Knowledge 需 review 後才可 promotion
6. Replay 預設最多 3 個 patch attempts；同一份 patch 不重複 replay
7. 每輪 AT run 最多一個 Auto-Healing PR
8. 不以總 pass rate 作為主 KPI
