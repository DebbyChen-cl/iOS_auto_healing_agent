# PHD iOS Auto-Healing Agent 架構總覽

## 系統目標

為 PhotoDirector iOS（PHD iOS）的 UI 自動化測試建立 AI 驅動的自動修復系統。
成熟度目標 **L3**：AI 可自動生成低風險 patch 並建立 PR，但不能自動 merge。

---

## 整體架構

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Phase 1: During AT Run                        │
│                    （pytest session, ~14 hrs, 200 cases）            │
│                                                                     │
│  conftest.py                                                        │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐              │
│  │ 執行測試  │───▶│ 失敗？收 evidence│───▶│ claude CLI     │              │
│  │ (pytest)  │    │ (metadata.json│    │ Phase1 triage │              │
│  └──────────┘    │  screenshot   │    │ Lane A/B/C/D  │              │
│       │          │  hierarchy)   │    └───────┬───────┘              │
│       │          └──────────────┘            │                      │
│       │                                 ┌───▼────┐                  │
│       │                                 │ retry? │                  │
│       │                                 └───┬────┘                  │
│       │                            Yes ─────┴───── No               │
│       │                            │               │                │
│       │                    ┌───────▼──────┐  ┌─────▼─────┐          │
│       │                    │ retry 1 次    │  │ deferred  │          │
│       │                    │ (protocol 內) │  │ to Phase 2│          │
│       │                    └───────┬──────┘  └───────────┘          │
│       │                            │                                │
│       ▼                            ▼                                │
│  ┌─────────────────────────────────────┐                            │
│  │       state.json（每 case 更新）      │                            │
│  └─────────────────────────────────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Phase 2: After AT Run                          │
│                   （Claude Code Workflow）                           │
│                                                                     │
│  auto_healing.js                                                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │ Root     │    │ Patch    │    │ Replay   │    │ Report   │      │
│  │ Cause    │───▶│ Generate │───▶│ Verify   │───▶│ & PR     │──┐   │
│  │ Analysis │    │          │    │ (device) │    │          │  │   │
│  │(parallel)│    │(per case)│    │(sequential)   │          │  │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │   │
│                                                                │   │
│                                                    ┌───────────▼┐  │
│                                                    │ Knowledge  │  │
│                                                    │ Promotion  │  │
│                                                    └────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 兩個 Repo 的分工

```
/Users/rdqe/Desktop/iOS_auto_healing_skills/       ← 本 Repo（Auto-Healing）
├── ARCHITECTURE.md              # 本文件
├── SPEC/                        # 14 份規格文件（gate I/O、taxonomy、policy…）
├── auto_healing_skills/         # 6 個 sub-agent skill + reference skills
│   ├── auto-healing-root-cause/       SKILL.md  ← G07 Sub-agent
│   ├── auto-healing-patch-generation/ SKILL.md  ← G11 Sub-agent
│   ├── auto-healing-replay-verification/ SKILL.md ← G12 Sub-agent
│   ├── auto-healing-html-report-approval/ SKILL.md ← G14 Sub-agent
│   ├── auto-healing-knowledge-promotion/ SKILL.md ← G16 Sub-agent
│   ├── auto-healing-phase1-decision/  SKILL.md  ← Phase 1 claude CLI
│   └── (其他 reference skills，保留作為規則文件)
├── workflow/
│   └── auto_healing.js          # Phase 2 Workflow 編排腳本
├── runs/                        # 每次 AT run 的輸出（自動生成）
│   └── {run_id}/
│       ├── state.json
│       ├── analysis/{case_id}/root_cause.json
│       ├── patches/{case_id}/
│       ├── replay/{case_id}/
│       └── report.html
├── registry/                    # 跨 run 持久
│   ├── test_registry.json       # Stable Case ID 對照表
│   └── history.json             # Previous result history
└── knowledge/                   # 跨 run 持久
    ├── app_usage/
    ├── test_fragility/
    └── coverage_opportunity/

/Users/rdqe/Desktop/rdqe-ios-autotest-phdm/        ← 測試 Repo
├── SFT/conftest.py              # Phase 1 邏輯（已修改）
├── SFT/tests/                   # 測試碼（patch 修改對象）
├── pages/                       # Page Object（patch 修改對象）
├── locator/                     # Locator 定義（patch 修改對象）
└── Self-healing/evidence/       # Evidence 資料夾（已有）
    └── {timestamp}-{test_name}/
        ├── metadata.json
        ├── fail_moment.png
        ├── fail_moment_hierarchy.xml
        ├── stack_trace.txt
        └── step_*_before/after.*
```

---

## Phase 1 流程（conftest.py）

### pytest_runtest_protocol（retry hook）

```
pytest 執行 test case
  │
  ├─ PASS → 寫 state.json（original_status: pass）→ 結束
  │
  └─ FAIL
      ├─ 收集 evidence（metadata.json + screenshot + hierarchy）
      ├─ 呼叫 claude CLI（auto-healing-phase1-decision skill）
      │   └─ 回傳 { lane, action, preliminary_category, reason }
      │
      ├─ action == "retry" && 預算夠？
      │   ├─ YES → 保留原始 evidence → retry 一次（driver 自動重啟 App）
      │   │         └─ 結果寫 state.json（含 original + retry 雙結果）
      │   └─ NO  → 標 deferred，寫 state.json
      │
      └─ action == "deferred" / "no_healing" / "manual_review"
          └─ 寫 state.json
```

### Retry 不打架的原因

- `pytest_runtest_protocol` 用 `tryfirst=True` 完全接管 test 執行
- retry 在 protocol 內部完成，ReportPortal 只收到最終結果
- `runtestprotocol(item, log=False)` 阻止中間結果外流
- `driver()` fixture 是 function-scoped，retry 時自動重啟 App

### Retry 預算

| 限制 | 值 |
|------|-----|
| 每個 case 最多 retry | 1 次 |
| 全域 retry case 數上限 | 3 個 |
| 全域時間增幅上限 | +15% |

### claude CLI 呼叫方式

```python
subprocess.run(
    ["claude", "-p", prompt, "--output-format", "json"],
    capture_output=True, text=True, timeout=60
)
```

一次性呼叫：fail → 起來判斷 → 回傳 JSON → 關閉。不是長駐程序。

### Test Registry 自動建立

`pytest_collection_modifyitems` hook 在 pytest 收集完 test items 後自動執行：
- 有 `@pytest.mark.case_id` → 用指定 ID
- 沒有 → 自動生成 `PHD-IOS-AUTO-XXXX`
- 骨架寫入 `registry/test_registry.json`
- feature、app_area、primary_test_component 留 null，Phase 2 root cause agent 會自動補齊

---

## Phase 2 流程（Workflow）

### 啟動方式

```bash
# 在 Claude Code 中執行
claude workflow run workflow/auto_healing.js --args '{"run_id": "run-20260701-220000"}'
```

### 6 個 Phase

| Phase | 動作 | 並行/序列 |
|-------|------|-----------|
| **Load** | 讀 state.json，過濾 deferred cases | — |
| **Root Cause Analysis** | 每個 deferred case 呼叫 root cause agent | **parallel** |
| **Healing** | L3-eligible cases：patch → replay | **sequential**（單一 device） |
| **Reconciliation** | JS 邏輯合併所有結果為 final_status | — |
| **Report & PR** | 生成 HTML report，通過 checklist 則建 PR | — |
| **Knowledge** | 從 approved event 萃取長期知識 | — |

### Healing 迴圈

```
for each L3-eligible case:
    for attempt 1..3:
        patch = agent(patch-generation, root_cause)
        if not patch.created → break

        replay = agent(replay-verification, patch)
        if replay == pass_with_healing → HEALED, break
        if replay requires assertion change → STOP
        if replay == product_bug / infra_issue → STOP
        
        # else: try next patch attempt
```

- 最多 3 次不同 patch，同一份 patch 不重跑
- Replay 用 pytest 執行單一 case（`--override-ini="rp_enabled=false"`）

---

## Sub-agent 架構

### Agent 與 Workflow 的關係

```
Workflow (auto_healing.js)          ← JS 腳本，不是 AI agent
  │
  ├─ agent(prompt + SKILL.md path)  ← 每次呼叫一個 sub-agent
  │     │
  │     ├─ 讀 SKILL.md 了解角色和規則
  │     ├─ 讀 evidence / test code
  │     └─ 回傳 structured JSON（schema 強制）
  │
  ├─ Workflow 用 JS 邏輯處理 agent 回傳
  └─ Workflow 寫入 state.json
```

Sub-agent 不直接寫 state.json，只回傳 structured output。Workflow 統一管理狀態。

### 6 個 Agent Skill

| Skill | Gate | 呼叫時機 | 輸出格式 |
|-------|------|---------|---------|
| `auto-healing-phase1-decision` | G06+G08 | Phase 1 claude CLI | `{ lane, action, preliminary_category, reason }` |
| `auto-healing-root-cause` | G07 | Phase 2 parallel | Root cause + L3 eligibility + identity enrichment |
| `auto-healing-patch-generation` | G11 | Phase 2 per case | Patch diff + risk flags + shared locator handling |
| `auto-healing-replay-verification` | G12 | Phase 2 sequential | Replay status + pass conditions + evidence |
| `auto-healing-html-report-approval` | G14 | Phase 2 per run | 12-item checklist + decision |
| `auto-healing-knowledge-promotion` | G16 | Phase 2 per run | Knowledge entries (candidate/trusted/deprecated) |

### Reference Skills（不給 agent 讀，保留作為文件）

failure-evidence、failure-taxonomy、l3-eligibility、scheduling-decision、
retry-policy、pass-baseline、previous-result-history、final-reconciliation、
pr-generation、new-case-generator、metrics、test-identity、workflow

---

## 16-Gate Pipeline 對照表

| Gate | 名稱 | 處理方式 | Phase |
|------|------|---------|-------|
| G01 | Test Identity | conftest.py (`pytest_collection_modifyitems`) | 1 |
| G02 | Context Capture | conftest.py（已完成，metadata.json） | 1 |
| G03 | Previous Result | Workflow JS（查 history.json） | 2 |
| G04 | Pass Baseline | conftest.py（`_cleanup_passed_evidence`） | 1 |
| G05 | Failure Evidence | conftest.py（rule-based 驗完整性） | 1 |
| G06 | Preliminary Classify | Phase 1 claude CLI | 1 |
| G07 | AI Root Cause | **Sub-agent**（root-cause） | 2 |
| G08 | Scheduling Decision | Phase 1 claude CLI | 1 |
| G09 | Immediate Action | conftest.py（`pytest_runtest_protocol` retry） | 1 |
| G10 | Deferred Queue | Workflow JS（排序 deferred cases） | 2 |
| G11 | Patch Generation | **Sub-agent**（patch-generation） | 2 |
| G12 | Replay Verification | **Sub-agent**（replay-verification） | 2 |
| G13 | Final Reconciliation | Workflow JS（合併狀態） | 2 |
| G14 | HTML Report | **Sub-agent**（html-report-approval） | 2 |
| G15 | PR Generation | Workflow JS + `gh pr create` | 2 |
| G16 | Knowledge Promotion | **Sub-agent**（knowledge-promotion） | 2 |

---

## state.json 核心欄位

```jsonc
{
  "run_id": "run-20260701-220000",
  "app_version": "20.10.0",
  "phase": "phase_1 | phase_2_root_cause | phase_2_healing | phase_2_report | done",

  "cases": {
    "PHD-IOS-IMPORT-001": {
      // Identity
      "case_name": "test_import_photo_from_album",
      "test_file": "SFT/tests/test_file.py::TestClass::test_method",

      // Phase 1
      "original_status": "fail",
      "error_summary": "Element 'import_button' not found",
      "evidence_path": "Self-healing/evidence/20260701-223045-test_import_photo/",
      "scheduling": { "lane": "C", "action": "deferred", "preliminary_category": "locator_drift" },
      "retry": null,  // or { count, reason, result, status_after, evidence_path }

      // Phase 2（Workflow 寫入）
      "root_cause": null,  // { type, confidence, reason, healable, l3_eligible, risk_flags }
      "patch": null,       // { status, diff_summary, risk_flags }
      "replay": null,      // { status, attempts }
      "final_status": null, // pass_with_healing | healing_failed | manual_review_required | ...
      "pr_eligible": false
    }
  },

  "summary": {
    "total": 200, "pass": 180, "fail": 5,
    "pass_with_healing": 3, "pass_after_retry": 8,
    "deferred": 2, "manual_review": 1, "product_bug": 1
  }
}
```

---

## 安全原則

1. **AI 不能修改** assertion、expected value、golden image、comparison rule、test intent
2. **AI 修復後**標 `pass_with_healing`，不可標成普通 `pass`
3. **HTML report** 是主要人工審核介面，`approve_merge_allowed` 後才允許 merge PR
4. **每輪 AT run** 最多一個 Auto-Healing PR
5. **同一份 patch** 不重複 replay；最多 3 個不同 patch
6. **Knowledge** 需 approved event 才能 promotion，單次 approved 為 candidate
7. **Replay** 關閉 ReportPortal（`rp_enabled=false`），不影響主報告數據
8. **Retry** 在 `pytest_runtest_protocol` 內部完成，對 pytest/RP 不可見

---

## 如何執行

### Phase 1（AT run 時自動啟動）

```bash
cd /Users/rdqe/Desktop/rdqe-ios-autotest-phdm
pytest SFT/tests/ -m "online"
# conftest.py 會自動：
# - 建 state.json
# - 建 test_registry.json
# - 每個 fail 呼叫 claude CLI 做 triage
# - 需要 retry 的 case 在 protocol 內重跑
```

### Phase 2（AT run 結束後手動啟動）

```bash
# 在 Claude Code 中
cd /Users/rdqe/Desktop/iOS_auto_healing_skills
# 執行 Workflow，傳入 run_id
```

Workflow 會自動執行 root cause → patch → replay → report → PR → knowledge 全流程。
