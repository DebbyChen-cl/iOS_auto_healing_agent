# Auto-Healing 使用指南

## 前置準備

### 環境需求

| 項目 | 需求 |
|------|------|
| Python | 3.10+（需要 `bool \| None` 語法支援） |
| Appium Python Client | < 4.0.0（需要 `TouchAction`） |
| Claude Code CLI | 已安裝且登入（`claude --version` 可執行） |
| Appium Server | 執行中（預設 `http://localhost:4723`） |
| iOS Device | 已連線、已信任、App 已安裝 |
| Xcode | 已安裝，WDA DerivedData 可用 |

### 建議：建立 venv

```bash
cd /Users/rdqe/Desktop/rdqe-ios-autotest-phdm
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Device 設定

編輯 `configs/driver_config.py` 中的 `ios_device_iphone17`：

```python
ios_device_iphone17 = {
    ...
    "udid": "你的裝置 UDID",
    "platformVersion": "你的 iOS 版本",
    "derivedDataPath": "/Users/你的使用者/Library/Developer/Xcode/DerivedData",
    ...
}
```

取得 UDID：`xcrun xctrace list devices`

---

## Phase 1：AT Run 時自動啟動

### 正常跑測試即可

```bash
cd /Users/rdqe/Desktop/rdqe-ios-autotest-phdm

# 跑全部（搭配 ReportPortal）
.venv/bin/python3 -m pytest SFT/tests/ -m "online"

# 跑單一 case（關閉 ReportPortal，測試用）
.venv/bin/python3 -m pytest SFT/tests/test_pytest_iPHD_SFT_sce_01.py::Test_SFT_sce_01::test_03_01_06_1 \
  --override-ini="rp_enabled=false" -x -v
```

### Phase 1 背後自動做了什麼

每個 test case 執行時：

```
test 開始
  │
  ├─ PASS → 記到 state.json，結束
  │
  └─ FAIL
      ├─ 自動收集 evidence（screenshot、hierarchy、metadata）
      ├─ 呼叫 Claude CLI 分析（~15 秒）
      │   └─ 判斷：retry / deferred / no_healing / manual_review
      ├─ 需要 retry？→ 自動重跑一次（不影響 ReportPortal）
      └─ 結果寫入 state.json
```

### Phase 1 產出

```
iOS_auto_healing_skills/
├── runs/{run_id}/state.json      ← 本次 run 的完整狀態
└── registry/test_registry.json   ← 自動建立的 test case 對照表
```

### 查看結果

```bash
# 看最新的 state.json
cat iOS_auto_healing_skills/runs/*/state.json | python3 -m json.tool

# 看 summary
cat iOS_auto_healing_skills/runs/*/state.json | python3 -c "
import sys, json
s = json.load(sys.stdin)['summary']
print(f'Total: {s[\"total\"]}')
print(f'Pass:  {s[\"pass\"]}')
print(f'Fail:  {s[\"fail\"]}')
print(f'Retry: {s[\"pass_after_retry\"]}')
print(f'Defer: {s[\"deferred\"]}')
"
```

---

## Phase 2：AT Run 結束後手動啟動

### 確認 Phase 1 有 deferred case

```bash
cat iOS_auto_healing_skills/runs/*/state.json | python3 -c "
import sys, json
state = json.load(sys.stdin)
deferred = [cid for cid, c in state['cases'].items()
            if c.get('scheduling', {}).get('action') == 'deferred']
print(f'Run: {state[\"run_id\"]}')
print(f'Deferred: {len(deferred)} cases')
for d in deferred:
    print(f'  - {d}: {state[\"cases\"][d].get(\"scheduling\",{}).get(\"preliminary_category\")}')
"
```

### 啟動 Workflow

在 Claude Code 中執行：

```
cd /Users/rdqe/Desktop/iOS_auto_healing_skills

# 告訴 Claude Code 跑 Phase 2 workflow
# 它會自動讀 state.json、分析 root cause、生成 patch、replay、建 PR
```

或直接用 Workflow API：

```javascript
// workflow/auto_healing.js
// 傳入 run_id 啟動
args: { run_id: "20260701182828" }
```

### Phase 2 自動執行的流程

```
1. Load        → 讀 state.json，找出所有 deferred cases
2. Root Cause  → 每個 case 平行分析（AI 讀 evidence + test code）
3. Healing     → L3-eligible 的 case 依序：生成 patch → replay 驗證
4. Reconcile   → 合併所有結果到 final_status
5. Report & PR → 生成 HTML report，checklist 全過則建 PR
6. Knowledge   → 從 approved event 萃取長期知識
```

### Phase 2 產出

```
iOS_auto_healing_skills/
├── runs/{run_id}/
│   ├── state.json                 ← 更新到 done
│   ├── analysis/{case_id}/        ← root cause 分析
│   ├── patches/{case_id}/         ← patch diff
│   ├── replay/{case_id}/          ← replay 結果
│   └── report.html                ← HTML 審核報告
├── knowledge/                     ← 長期知識（跨 run 累積）
│   ├── app_usage/
│   ├── test_fragility/
│   └── coverage_opportunity/
```

---

## 重要限制

| 限制 | 值 |
|------|-----|
| 每個 case 最多 retry | 1 次 |
| 全域 retry case 上限 | 3 個 |
| Patch 嘗試上限 | 3 次（不同 patch） |
| 同一份 patch 重跑 | 不允許 |
| AI 修改 assertion | 不允許 |
| 自動 merge PR | 不允許（需人工審核 HTML report） |

---

## Dry Run 驗證

不需要 device 就能跑的環境檢查：

```bash
python3 /Users/rdqe/Desktop/iOS_auto_healing_skills/tests/test_phase1_dry_run.py
```

檢查項目：
- claude CLI 是否可用
- state.json 讀寫是否正常
- 6 個 skill 檔案是否完整
- Workflow 腳本是否正確

---

## 常見問題

### Q: Claude CLI 回應太慢？

Phase 1 triage 通常 10-20 秒。如果經常 timeout，檢查網路連線，或調整 `SFT/conftest.py` 中 `_ask_claude_scheduling` 的 timeout 值（目前 120 秒）。

### Q: test 跑到一半 retry 會影響 ReportPortal 嗎？

不會。retry 在 `pytest_runtest_protocol` 內部完成，ReportPortal 只看到最終結果。如果 retry 成功，RP 報 pass；如果 retry 失敗，RP 報 fail。state.json 會保留完整的 original + retry 雙結果。

### Q: 我想跳過 auto-healing，只跑原本的 pytest？

Claude CLI 呼叫如果失敗會自動 fallback 到 `deferred`，不會中斷測試。如果完全不想啟動 auto-healing，可以設環境變數：

```bash
# 未來可以加這個開關（目前尚未實作，需要時再加）
DISABLE_AUTO_HEALING=1 pytest ...
```

### Q: state.json 在哪裡？

```
iOS_auto_healing_skills/runs/{run_id}/state.json
```

run_id 格式是 `YYYYMMDDHHmmss`，例如 `20260701182828`。

### Q: 怎麼看 Claude 對 failure 的判斷？

```bash
cat iOS_auto_healing_skills/runs/*/state.json | python3 -c "
import sys, json
state = json.load(sys.stdin)
for cid, c in state['cases'].items():
    s = c.get('scheduling', {})
    if s:
        print(f'{cid}: lane={s.get(\"lane\")} action={s.get(\"action\")} category={s.get(\"preliminary_category\")}')
        print(f'  reason: {s.get(\"reason\")}')
"
```

### Q: 如何添加 @pytest.mark.case_id？

在 test method 上加裝飾器：

```python
@pytest.mark.case_id('PHD-IOS-IMPORT-001')
def test_import_photo(self):
    ...
```

不加也可以，系統會自動生成 `PHD-IOS-AUTO-XXXX` 格式的 ID。
