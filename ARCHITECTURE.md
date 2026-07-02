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
│  ┌──────────┐    ┌──────────────┐    ┌────────────────┐             │
│  │ 執行測試  │───▶│ 失敗？收 evidence│───▶│ Python heuristic│             │
│  │ (pytest)  │    │ (metadata.json│    │ 即時分類（無 AI）  │             │
│  └──────────┘    │  screenshot   │    └───────┬────────┘             │
│       │          │  hierarchy)   │            │                      │
│       │          └──────────────┘        ┌───▼────┐                  │
│       │                                  │ retry? │                  │
│       │                                  └───┬────┘                  │
│       │                             Yes ─────┴───── No               │
│       │                             │               │                │
│       │                     ┌───────▼──────┐  ┌─────▼─────┐          │
│       │                     │ retry 1 次    │  │ deferred  │          │
│       │                     │ (protocol 內) │  │ to Phase 2│          │
│       │                     └───────┬──────┘  └───────────┘          │
│       │                             │                                │
│       ▼                             ▼                                │
│  ┌─────────────────────────────────────┐                             │
│  │       state.json（每 case 更新）      │                             │
│  └─────────────────────────────────────┘                             │
│       │                                                              │
│       ▼  pytest_sessionfinish                                        │
│  ┌─────────────────────────────────────┐                             │
│  │ 有 deferred? → Popen orchestrator.py│                             │
│  └─────────────────────────────────────┘                             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Phase 2: After AT Run                          │
│                   （orchestrator.py + claude -p）                    │
│                                                                     │
│  for each case (sequential):                                        │
│  ┌──────────────────────────────────────────────────┐               │
│  │ 一個 claude -p session（max-turns 50）              │               │
│  │                                                    │               │
│  │  ┌─ Read evidence ──── 只讀一次                     │               │
│  │  ├─ Root cause 分類                                │               │
│  │  ├─ Generate patch → Edit source                   │               │
│  │  │                                                  │               │
│  │  │  ┌─ Bash: replay.py ──── 不用 AI                │               │
│  │  │  │   pass → result.json → END                   │               │
│  │  │  │   infra → result.json → END                  │               │
│  │  │  │   fail ↓                                     │               │
│  │  │  │                                              │               │
│  │  │  └─ Re-analyze（同 session）                     │               │
│  │  │       新 patch → 回到 replay.py                  │               │
│  │  │       max 10 次                                  │               │
│  │  └─ Write result.json → END                        │               │
│  └──────────────────────────────────────────────────┘               │
│                                                                     │
│  Finalize（Python，無 AI）                                           │
│  ├─ update_state.py → state.json                                    │
│  └─ generate_report.py → report.html                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 兩個 Repo 的分工

```
/Users/rdqe/Desktop/iOS_auto_healing_skills/       ← 本 Repo（Auto-Healing）
├── ARCHITECTURE.md              # 本文件
├── WORKFLOW.md                  # 詳細流程圖（含 input/output）
├── SPEC/                        # 14 份規格文件
├── .claude/agents/
│   └── analyze-and-patch.md     # 合併的 root-cause + patch agent（opus 4.6）
├── auto_healing_skills/         # Sub-agent skills（保留作為規則參考）
│   ├── auto-healing-root-cause/       SKILL.md
│   ├── auto-healing-patch-generation/ SKILL.md
│   └── (其他 reference skills)
├── tools/                       # Python 工具（無 AI）
│   ├── orchestrator.py          # Phase 2 主控（每 case 一個 claude -p session）
│   ├── replay.py                # 跑 pytest，解析結果，回傳 JSON
│   ├── update_state.py          # 更新 state.json
│   └── generate_report.py       # 從 state.json 產生 HTML report（固定模板）
├── workflow/
│   └── auto_healing.js          # Backup：僅 parallel analyze-and-patch（Workflow tool）
├── runs/                        # 每次 AT run 的輸出
│   └── {run_id}/
│       ├── state.json
│       ├── analysis/{case_id}/result.json
│       ├── healing_results.json
│       ├── report.html
│       └── phase2.log
├── registry/
│   └── test_registry.json       # Stable Case ID 對照表
└── knowledge/                   # 跨 run 持久（未來）

/Users/rdqe/Desktop/rdqe-ios-autotest-phdm/        ← 測試 Repo
├── SFT/conftest.py              # Phase 1 邏輯
├── SFT/tests/                   # 測試碼（patch 修改對象）
├── pages/                       # Page Object（patch 修改對象）
├── locator/                     # Locator 定義（patch 修改對象）
└── Self-healing/evidence/       # Evidence 資料夾
    └── {timestamp}-{test_name}/
        ├── metadata.json
        ├── fail_moment.png
        ├── fail_moment_hierarchy.xml
        ├── stack_trace.txt
        └── step_*_before/after.*
```

---

## Phase 1 流程（conftest.py）

### pytest_runtest_protocol

```
pytest 執行 test case
  │
  ├─ PASS → 寫 state.json（original_status: pass）→ 結束
  │
  └─ FAIL
      ├─ 收集 evidence（metadata.json + screenshot + hierarchy）
      ├─ _classify_failure_heuristic()（純 Python，不呼叫 AI）
      │   ├─ app_state 異常（crash/黑屏）→ action: retry
      │   ├─ stack trace 含 network 關鍵字 → action: retry
      │   └─ 其他 → action: deferred
      │
      ├─ action == "retry" && 預算夠？
      │   ├─ YES → 保留原始 evidence → retry 一次
      │   └─ NO  → 標 deferred
      │
      └─ action == "deferred" → 寫 state.json，繼續下一個 test
```

### pytest_sessionfinish

```
所有 test 跑完
  ├─ _finalize_state_json()
  ├─ 掃 state.json 找 deferred cases
  └─ 有 → Popen('python3 orchestrator.py {run_id}')
       └─ 不 block pytest 退出，log 寫 phase2.log
```

### Retry 預算

| 限制 | 值 |
|------|-----|
| 每個 case 最多 retry | 1 次 |
| 全域 retry case 數上限 | 3 個 |

---

## Phase 2 流程（orchestrator.py）

### 核心設計：一個 case = 一個 claude -p session

每個 deferred case 由一個 `claude -p --max-turns 50` session 處理全部工作：
analyze → patch → replay（Bash）→ re-analyze（同 session）→ loop。

Re-analyze 不開新 session — evidence 已在 context 中，只需看新 error。

### 決策邏輯（orchestrator.py，Python）

| 條件 | 動作 |
|------|------|
| result.json `healed == true` | 記錄成功 |
| result.json 無法讀取 | 記錄失敗 |
| 全部 case 完成 | 進 Finalize |

### Finalize（Python，無 AI）

| 步驟 | 工具 | 做什麼 |
|------|------|--------|
| 1 | `update_state.py` | 讀 healing_results.json → 更新 state.json |
| 2 | `generate_report.py` | 讀 state.json → 產生 report.html（固定模板） |

---

## Agent 使用概覽

### 唯一的 AI agent：analyze-and-patch

| 項目 | 值 |
|------|-----|
| 定義位置 | `.claude/agents/analyze-and-patch.md` |
| Model | `claude-opus-4-6` |
| 呼叫方式 | `claude -p`（orchestrator subprocess） |
| 職責 | 讀 evidence → root cause 分類 → L3 判定 → patch 生成 → apply patch → replay loop → 寫 result.json |
| 工具 | Read, Edit, Bash, Write |

### 不需要 AI 的部分

| 功能 | 處理方式 |
|------|---------|
| Phase 1 分類 | Python heuristic（`_classify_failure_heuristic`） |
| Replay 執行 | `replay.py`（agent 透過 Bash 呼叫） |
| State 更新 | `update_state.py` |
| HTML Report | `generate_report.py`（固定模板） |

---

## state.json 核心欄位

```jsonc
{
  "run_id": "20260702095018",
  "phase": "done",

  "cases": {
    "PHD-IOS-AUTO-0001": {
      "case_name": "test_ai_hairstyle_custom",
      "test_file": "SFT/test_pytest_iPHD_SFT_renew.py::...",

      // Phase 1
      "original_status": "fail",
      "error_summary": "NoSuchElementException: ...",
      "evidence_path": "Self-healing/evidence/20260702...-test_ai_hairstyle_custom/",
      "scheduling": { "lane": "C", "action": "deferred", "preliminary_category": "unknown" },
      "retry": null,

      // Phase 2（orchestrator 寫入）
      "root_cause": { "type": "locator_drift", "confidence": 0.92, "reason": "...", "l3_eligible": true },
      "patch": { "status": "generated", "diff_summary": "Updated btn_hairstyle accessibility id" },
      "replay": { "status": "pass_with_healing", "attempts": 1 },
      "final_status": "pass_with_healing",
      "pr_eligible": true
    }
  },

  "summary": { "total": 1, "healed": 1, "healing_failed": 0, "not_eligible": 0 }
}
```

---

## 安全原則

1. **AI 不能修改** assertion、expected value、golden image、comparison rule、test intent
2. **AI 修復後**標 `pass_with_healing`，不可標成普通 `pass`
3. **每輪 AT run** 最多一個 Auto-Healing PR
4. **同一份 patch** 不重複 replay；re-analyze 必須產生不同 patch
5. **Replay** 關閉 ReportPortal（`rp_enabled=false`），不影響主報告數據
6. **Retry** 在 `pytest_runtest_protocol` 內部完成，對 pytest/RP 不可見

---

## 如何執行

### 自動（正常流程）

```bash
cd /Users/rdqe/Desktop/rdqe-ios-autotest-phdm
pytest SFT/tests/ -m "online"
# conftest.py 自動：
#   1. 每個 fail → heuristic 分類 → retry 或 deferred
#   2. 全部跑完 → sessionfinish 自動啟動 orchestrator.py
#   3. orchestrator.py 逐 case 分析+修復 → 更新 state + 產生 report
```

### 手動（僅 Phase 2）

```bash
python3 /Users/rdqe/Desktop/iOS_auto_healing_skills/tools/orchestrator.py {run_id}
```
