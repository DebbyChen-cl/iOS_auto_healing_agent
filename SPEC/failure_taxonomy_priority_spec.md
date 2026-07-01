# Failure Taxonomy Priority 規格

本文件定義 AI Auto-Healing 系統在分析 fail case 時的分類優先順序。v1 分類邏輯以人工 debug 習慣為基礎：先從 fail screenshot 與 Error Step 開始，再逐步追 root cause。

## 核心原則

| 原則 | 說明 |
|---|---|
| Assert Error 是表象 | Error Step 通常都是 assert error，不可直接把 assertion 當 root cause |
| 先看 fail screenshot + Error Step | 分類起點是實際 debug 流程，而不是抽象 failure type |
| 先判斷畫面是否對 | 畫面不對時，locator / compare 結果通常只是下游表象 |
| Flaky 放最後 | Flaky 需要 retry evidence 或 previous result history，不能靠單次 fail 判斷 |
| 可 healing 類型要先排除產品問題 | 若疑似 product bug，不應讓 AI 修改測試掩蓋品質訊號 |

## 第一層：Error Step 類型

目前 Error Step 都是 assert error，通常分為兩種：

| Error Step 類型 | 說明 |
|---|---|
| Element Not Found | 測試要找的元素不存在或找不到 |
| Compare Fail | 圖像、畫面或 before / after 比較不符合預期 |

分類流程：

```text
Assert Error
  |
  +-- Element Not Found
  |
  +-- Compare Fail
```

## Element Not Found 分類順序

### Step 1：目標 element 是否出現在 fail screenshot 上

```text
Element Not Found
      |
      v
target element visible in fail screenshot?
      |
      +-- yes -> locator / timing branch
      |
      +-- no  -> screen / flow / dialog branch
```

### 如果 element 有出現在截圖上

| 優先順序 | 先懷疑 | 可能分類 | 說明 |
|---:|---|---|---|
| 1 | locator 有改變 | `locator_drift` / `page_object_drift` | 元素看得到，但測試找不到，最先懷疑 locator 或 page object 落後 |
| 2 | timing issue | `readiness_wait_drift` | 元素可能剛出現、尚未 enabled、hierarchy 尚未 ready |

補充判斷：

| 截圖 | Hierarchy | 可能判斷 |
|---|---|---|
| 有目標元素 | hierarchy 也有 | locator / page object drift 機率高 |
| 有目標元素 | hierarchy 沒有 | accessibility / locator strategy 問題，或 hierarchy capture timing 問題 |

### 如果 element 沒有出現在截圖上

| 優先順序 | 先懷疑 | 可能分類 | 說明 |
|---:|---|---|---|
| 1 | 特殊 dialog / overlay 跳出 | `network_issue`、`server_busy`、`ad_interruption`、`permission_dialog`、`app_crash` | 例如網路不穩、APP crash、廣告、權限彈窗 |
| 2 | 前一個步驟沒有如預期完成 | `previous_step_not_completed` | 當前 step 找不到元素，可能是上一個 action 沒成功 |
| 3 | 新版本預期流程改變 | `micro_flow_drift` / `workflow_change` | 例如進入功能前多了一個 button 或 confirmation |
| 4 | 點擊真的沒有反應 | `product_bug_suspected` | 操作應該生效但產品無反應 |
| 5 | 重跑結果不穩 | `flaky_suspect` | 需要 retry evidence 或 history 支撐 |

## Compare Fail 分類順序

Compare Fail 分為兩種主要情境：

| Compare 類型 | 說明 |
|---|---|
| GroundTruth Compare | actual image / screen 與 ground truth 比較 |
| Before / After Compare | action 前後畫面或輸出結果比較 |

## GroundTruth Compare

人工 debug 流程是打開 actual 與 ground truth 兩張圖，觀察差異。

| 優先順序 | 先懷疑 | 可能分類 | 說明 |
|---:|---|---|---|
| 1 | AT 不穩定造成差異 | `visual_compare_instability`、`ad_interruption` | 例如時間列表、廣告、動態內容、非穩定區域 |
| 2 | 前一個步驟沒有如預期完成 | `previous_step_not_completed` | 畫面根本不在預期狀態 |
| 3 | 新版本預期流程改變 | `micro_flow_drift` / `workflow_change` / `needs_new_test_case` | 新版功能或流程改變造成 GT 不再適用 |
| 4 | 點擊真的沒有反應或輸出錯 | `product_bug_suspected` | 操作無效、輸出錯誤、產品行為異常 |
| 5 | 重跑結果不穩 | `flaky_suspect` | 需要 retry evidence 或 history 支撐 |

## Before / After Compare

人工 debug 流程是打開 before 與 after 兩張圖，確認 action 是否造成預期變化。

| 優先順序 | 先懷疑 | 可能分類 | 說明 |
|---:|---|---|---|
| 1 | 前一個步驟沒有如預期完成 | `previous_step_not_completed` | action 前的狀態已經不對 |
| 2 | 新版本預期流程改變 | `micro_flow_drift` / `workflow_change` / `needs_new_test_case` | 操作流程改變，導致 before / after 預期不成立 |
| 3 | 點擊真的沒有反應或效果未套用 | `product_bug_suspected` | 產品功能可能壞掉 |
| 4 | 重跑結果不穩 | `flaky_suspect` | 需要 retry evidence 或 history 支撐 |

## 新增分類

| 分類 | 意義 | 是否可 healing |
|---|---|---|
| `previous_step_not_completed` | 當前 fail 是結果，真正問題可能發生在前一個 step | 視 root cause |
| `visual_compare_instability` | GroundTruth 或 before/after 比較受到時間、廣告、動態內容影響 | 不直接 L3，先 review |
| `ad_interruption` | 廣告或非測試目標 overlay 干擾 UI | 視專案策略，通常不直接 L3 |
| `permission_dialog` | iOS 系統權限彈窗造成流程中斷 | 視是否為預期 setup 問題 |
| `workflow_change` | 產品流程改變 | 小流程可視為 micro-flow drift，大流程走 new test case / redesign |

## Flaky 判斷規則

Flaky 不應靠單次 fail 判斷。

只有在以下資料支持時，才標成 `flaky_suspect`：

1. 不改 code retry 後出現 pass / fail 交替。
2. Previous Result History 最近 5 次出現 pass / fail 交替。
3. 同一 Stable Case ID 在相近 app version / environment 下反覆不穩。

如果沒有 retry evidence 或 history support，不能只因為「看起來怪」就標 flaky。

## L3 Healing 關係

| 分類 | L3 auto-healing |
|---|---|
| `locator_drift` | 可以 |
| `page_object_drift` | 可以 |
| `readiness_wait_drift` | 有條件可以 |
| `micro_flow_drift` | 小流程可進 L3 |
| `workflow_change` | 小流程才可，主流程改變不可以 |
| `previous_step_not_completed` | 需再追 root cause |
| `visual_compare_instability` | 不直接 L3 |
| `network_issue` / `server_busy` | 不屬於 healing |
| `product_bug_suspected` | 不可以 |
| `needs_new_test_case` | 不可以 |
| `flaky_suspect` | 不直接 L3 |

## v1 分類流程總覽

```text
fail case
   |
   v
read fail screenshot + error step
   |
   v
error step type?
   |
   +-- Element Not Found
   |      |
   |      v
   |   target visible in screenshot?
   |      |
   |      +-- yes -> locator drift / page object drift / readiness wait drift
   |      |
   |      +-- no  -> dialog / overlay / previous step / workflow change / product bug / flaky
   |
   +-- Compare Fail
          |
          v
       compare type?
          |
          +-- GroundTruth -> instability / previous step / workflow change / product bug / flaky
          |
          +-- Before-After -> previous step / workflow change / product bug / flaky
```

## 待討論

1. `ad_interruption` 是否獨立成正式 final status，或歸入 `manual_review_required`。
2. `permission_dialog` 是否屬於 setup issue、workflow issue，或獨立分類。
3. `visual_compare_instability` 是否允許未來用固定 ignore region 或 mask rule 處理。
