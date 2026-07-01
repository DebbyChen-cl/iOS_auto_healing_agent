# Pass Baseline Retention 規格

本文件定義 AI Auto-Healing 系統如何保存 pass case 的 baseline 資料。Pass baseline 的目的不是保存完整測試 artifact，而是在 case fail 時，能用相對應 step 的正常畫面與 hierarchy 協助 AI 判斷 root cause。

## 核心決策

| 決策 | 內容 |
|---|---|
| Baseline 粒度 | Step-level baseline |
| 比對範圍 | 失敗 step 往前數 5 個 step，包含 fail step 本身；最多比對 5 個 step |
| 每個 step 保存內容 | before snapshot、after snapshot、before hierarchy、after hierarchy |
| 不保存內容 | visible elements summary、app screen / area、used page function / test component、used locator summary、assertion summary、full video、full raw log |
| 補抓時機 | 只有當本次 fail reason 符合特定類型，且需要正常流程比較時，才補抓或更新 pass baseline |
| 查詢方式 | Stable Case ID + Step ID / Step Key |

## 為什麼使用 Step-level Baseline

UI auto-healing 最需要比較的不是整個 case 的最終畫面，而是失敗附近的正常流程。

當某個 step fail 時，AI 需要知道：

1. 失敗前幾步的正常畫面是否一致。
2. 失敗 step 的正常 hierarchy 中，目標元素原本在哪裡。
3. 失敗時的 hierarchy 與 pass baseline 的 hierarchy 差異。
4. 是否出現 micro-flow drift，例如中間多了一個 button 或 confirmation step。
5. fail step 前的狀態是否已經偏離正常流程。

因此 v1 不只保存 final screen，而是保存 step-level before / after snapshot 與 hierarchy。

## Step Window 定義

當 case fail 時，系統先定位 fail step，然後取以下範圍做比較：

```text
fail step inclusive previous 5-step window

example:
step 08 failed
compare: step 04, step 05, step 06, step 07, step 08
```

規則：

1. 最多取 5 個 step。
2. 包含 fail step 本身。
3. 若 fail step 前不足 4 個 step，就取可取得的全部前置 step。
4. 不需要載入整個 case 的所有 pass baseline。

## 每個 Step Baseline 保存內容

| 資料 | 是否保存 | 說明 |
|---|---|---|
| Step ID / Step Key | 必須 | 用於把 fail step 對應到 pass baseline step |
| Step Order | 必須 | 用於 fail step 前 5 個 step 的 window 查詢 |
| Before Snapshot | 必須 | step 執行前畫面截圖 |
| After Snapshot | 必須 | step 執行後畫面截圖 |
| Before Hierarchy | 必須 | step 執行前 UI hierarchy / accessibility hierarchy |
| After Hierarchy | 必須 | step 執行後 UI hierarchy / accessibility hierarchy |

## 不保存的內容

以下內容不放在 Pass Baseline 中：

| 資料 | 不保存原因 | 替代來源 |
|---|---|---|
| Visible elements summary | 可由 hierarchy 推導，不需要重複保存 | hierarchy |
| App screen / area | 屬於 Test Identity 或 runtime context | Test Identity / Context |
| Used page function / test component | 屬於 Test Identity、Static Code Metadata 或 Runtime Execution Trace | Test Identity / Trace |
| Used locator summary | 只在 failure 或 patch 時需要 | Failure Evidence / Healing Record |
| Assertion summary | 屬於測試意圖或 execution trace，不放 baseline | Test Code / Trace |
| Full video | 體積大，v1 不保存 | 必要時由 failure evidence 保存 |
| Full raw log | 體積大，且 baseline 比對不需要 | Failure Evidence / CI log |

## 什麼時候補抓或更新 Pass Baseline

不是每次 case pass 都永久保存完整 step-level baseline。系統只在需要時補抓或更新。

### 需要補抓 / 更新的情境

| Failure Reason | 是否需要 baseline | 原因 |
|---|---|---|
| Workflow / Micro-flow Change | 需要 | 要比較正常流程中是否少了一步、多了一步或順序改變 |
| Locator Drift | 需要 | 要用正常 hierarchy 找原本元素與候選替代元素 |
| Page Object Drift | 需要 | 要確認 page object 封裝的行為與畫面狀態是否一致 |
| Readiness / Wait Drift | 視情況需要 | 若需比較 step 前後狀態，才需要 baseline |
| Assertion Failure Symptom | 視 root cause 決定 | 若 root cause 是 workflow、locator、wait，才需要 baseline |

### 不需要補抓 / 更新的情境

| Failure Reason | 原因 |
|---|---|
| Network / Server Busy | 重點是 retry policy 與 network evidence，不需要 pass baseline |
| Environment / Infra Issue | 屬於環境或設備問題 |
| Product Bug Suspected | 不應用 pass baseline 引導 AI 修改測試 |
| Assertion Logic Change Required | 應走 new test case / test redesign |
| Dependency Cascade | 應先看 upstream root failure |

## Baseline 查詢流程

```text
case fail
      |
      v
identify fail step
      |
      v
check failure reason
      |
      +-- reason needs baseline
      |       |
      |       v
      |  lookup pass baseline by Stable Case ID + Step ID
      |       |
      |       +-- found compatible baseline
      |       |       -> compare fail step window with pass baseline window
      |       |
      |       +-- missing / stale / incompatible
      |               -> schedule baseline refresh if trusted pass source exists
      |
      +-- reason does not need baseline
              -> continue analysis without baseline
```

## Baseline 來源優先順序

當需要 pass baseline 時，來源優先順序如下：

| 優先 | 來源 |
|---|---|
| 1 | 同 Stable Case ID、同 App version/build 的最近 trusted pass baseline |
| 2 | 同 Stable Case ID、相近 App version/build 的最近 trusted pass baseline |
| 3 | main / release branch 的最近 trusted pass baseline |
| 4 | 手動指定 baseline run |
| 5 | 無可用 baseline，AI 只能依 failure evidence、test code、history 分析 |

## Trusted Pass Baseline 定義

可作為 baseline 的 pass 來源：

1. 原始 `pass`，未經 retry、healing、recovery。
2. Reviewer approved 的 `pass_with_healing`，且對應 PR 已被接受或確認修補合理。

不建議作為 baseline 的來源：

1. `pass_after_retry`
2. `pass_after_network_retry`
3. `pass_after_dependency_recovery`
4. 未經 review 的 `pass_with_healing`

## Storage 策略

| 項目 | v1 建議 |
|---|---|
| 每個 Stable Case ID 保存幾份 baseline | 最近 1 份 trusted pass baseline；必要時保留 main/release baseline 各 1 份 |
| 每份 baseline 保存哪些 step | 不必保存全部；至少可回查 fail window 需要的 step |
| 是否每次 pass 都更新 baseline | 不建議 |
| 是否每次 fail 都補抓 baseline | 不建議，只在特定 failure reason 需要時補抓 |

## 待討論

1. Step ID / Step Key 如何產生，是否由測試框架 instrumentation 自動提供。
2. Snapshot 與 hierarchy 的保存格式與壓縮策略。
3. Baseline compatible 的判斷條件，例如 App version、branch、device、iOS version 是否必須一致。
4. Trusted pass baseline 的更新時機是否只由 nightly / main run 產生。
