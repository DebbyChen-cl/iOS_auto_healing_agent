# L3 Healing Eligibility 規格

本文件定義 AI Auto-Healing 系統中哪些 failure 可以進入 L3 healing，也就是 AI 自動產生 patch、replay 驗證、建立 PR，但不自動 merge。

## 核心原則

| 原則 | 說明 |
|---|---|
| L3 healing 不等於 auto merge | L3 只允許 AI 自動 patch + replay + PR，merge 仍需人工 review |
| 只修測試路徑，不改測試意圖 | 不能修改 assertion、expected value、比較規則或產品規格判斷 |
| Immediate healing 比 L3 更嚴格 | 只有 blocking impact high 且 healing risk low 才可在 AT 未跑完前搶 device 修 |
| Deferred L3 是預設 | 多數可 healing 類型等 full AT run 完成後再處理 |
| Product bug / major workflow / assertion logic change 不可 healing | 保護品質訊號 |

## Blocking Impact 定義

Blocking Impact 用來判斷 failure 是否會污染後續測試結果。

| 等級 | 定義 | 例子 |
|---|---|---|
| High | 會讓後續多數 case 無法進行或結果失真 | App launch、登入/session、匯入圖片、建立編輯專案、相簿/檔案權限 |
| Medium | 會影響同 feature 或同 flow 下的一組 case | Export setup、Tool panel 開啟、某個 editor mode、某個 shared setup |
| Low | 只影響單一 case 或低範圍功能 | 單一 filter、單一 button、單一 edge case |

## Healing Risk 定義

Healing Risk 用來判斷 AI patch 是否可能改變測試意圖或掩蓋產品問題。

| 等級 | 定義 | 例子 |
|---|---|---|
| Low | 不改測試意圖，只修測試路徑、定位或等待條件 | locator drift、page object drift、明確狀態型 wait、小 micro-flow |
| Medium | 可能影響流程解讀，需要更小心 | optional dialog、visual compare instability、較不明確的 workflow change |
| High | 會改測試意圖、expected behavior，或可能掩蓋產品問題 | assertion logic change、expected value change、major workflow、product bug suspected |

## L3 Eligibility Matrix

| Blocking Impact | Healing Risk | 是否可 L3 | 處理 |
|---|---|---|---|
| High | Low | 可以 | 可 immediate healing，若 device budget 可用 |
| High | Medium | 不建議 L3 | deferred L2 或 manual review |
| High | High | 不可以 | no healing / manual path |
| Medium | Low | 可以 | deferred L3 |
| Medium | Medium | 不建議 L3 | deferred L2 / manual review |
| Medium | High | 不可以 | no healing / manual path |
| Low | Low | 可以 | deferred L3 |
| Low | Medium | 不建議 L3 | deferred L2 / manual review |
| Low | High | 不可以 | no healing / manual path |

## Immediate Healing Eligibility

Immediate healing 是 L3 的更嚴格子集。

只有同時符合以下條件，才允許在整份 AT 還沒跑完前使用 device 進行 healing：

1. Blocking Impact = High。
2. Healing Risk = Low。
3. Root cause 明確屬於低風險 healing 類型。
4. 不修改 assertion、expected value、比較規則。
5. 有足夠 failure evidence 與必要 baseline。
6. device budget 尚未用完。
7. patch 範圍局部，且 replay 可在可接受時間內完成。

若不符合上述條件，即使可 L3，也應進 deferred healing queue。

## Failure Type Eligibility

| Failure Type | Healing Risk | L3 Eligibility | Immediate Healing |
|---|---|---|---|
| `locator_drift` | Low | 可以 | 只有 blocking impact high 才可 |
| `page_object_drift` | Low | 可以 | 只有 blocking impact high 才可 |
| `readiness_wait_drift` | Low / Medium | 有條件可以 | 只有明確狀態型 wait 且 blocking impact high 才可 |
| `micro_flow_drift` | Low / Medium | 小流程可以 | 只有明確單一步驟且 blocking impact high 才可 |
| `workflow_change` | Medium / High | 視範圍 | 大流程不可以 |
| `previous_step_not_completed` | 未定 | 需追 root cause | 不直接 immediate |
| `visual_compare_instability` | Medium | 不建議 L3 | 不可以 |
| `ad_interruption` | Medium | 不建議 L3 | 不可以 |
| `permission_dialog` | Medium | 視 setup policy | 不建議 immediate healing |
| `network_issue` | 不屬於 healing | 不可以 | retry policy 處理 |
| `server_busy` | 不屬於 healing | 不可以 | retry policy 處理 |
| `generation_fail` | 未定 | 視 root cause | 不直接 L3 |
| `product_bug_suspected` | High | 不可以 | 不可以 |
| `assertion_logic_change_required` | High | 不可以 | 不可以 |
| `major_workflow_change` | High | 不可以 | 不可以 |
| `flaky_suspect` | 未定 | 不直接 L3 | 不可以 |

## Low-Risk Healing 定義

以下修補屬於 low-risk healing：

| 修補類型 | 條件 |
|---|---|
| Locator replacement | 目標元素語意一致，且 pass baseline / current hierarchy 支持替代 locator |
| Page object locator update | 只更新 page object 裡的 locator 或等待條件，不改 test assertion |
| State-based wait | 等待 visible、enabled、spinner gone、API complete、screen ready 等明確狀態 |
| Small micro-flow step | 只新增一個語意明確的中介操作，例如 Continue、Confirm、Open、Next |

以下修補不屬於 low-risk：

| 修補類型 | 原因 |
|---|---|
| 修改 assertion | 改變測試意圖 |
| 修改 expected value / golden image | 改變預期結果 |
| 修改比較容忍度或 ignore region | 可能掩蓋產品問題，需另定 visual compare policy |
| 大幅重排測試流程 | 可能是產品流程或規格改變 |
| 直接跳過失敗步驟 | 繞過品質訊號 |
| 只增加固定 sleep | 不穩定，且可能掩蓋效能問題 |

## L3 Decision Flow

```text
failure after retry / deferred candidate
      |
      v
root cause identified?
      |
      +-- no -> manual_review_required
      |
      +-- yes
            |
            v
is product bug / assertion logic / major workflow?
      |
      +-- yes -> no healing
      |
      +-- no
            |
            v
determine blocking impact
            |
            v
determine healing risk
            |
            v
matrix decision
      |
      +-- High impact + Low risk -> immediate L3 if budget, else deferred L3
      |
      +-- Medium/Low impact + Low risk -> deferred L3
      |
      +-- Medium risk -> L2/manual review
      |
      +-- High risk -> no healing
```

## L3 輸出要求

若 case 進入 L3 healing，必須產生：

| 輸出 | 說明 |
|---|---|
| Patch | AI 修改的測試碼或 page object |
| Diff Summary | 修改了什麼、為什麼 |
| Risk Flags | 是否碰到 wait、micro-flow、baseline、locator |
| Replay Result | replay 是否通過 |
| Final Status | 成功後標 `pass_with_healing` |
| HTML Report Section | failure screenshot、root cause、修補內容、replay 證據 |
| PR | 自動建立 PR，但不 auto merge |

## v1 實作規則

1. `locator_drift`、`page_object_drift` 可進 L3。
2. `readiness_wait_drift` 只有狀態型 wait 可進 L3；固定 sleep 不可 L3。
3. `micro_flow_drift` 只有單一步驟、語意明確、assertion 不變時可進 L3。
4. Immediate healing 只允許 Blocking Impact = High 且 Healing Risk = Low。
5. Medium risk 不走 L3，先走 L2 / manual review。
6. High risk 不 healing。
7. L3 成功後 final status 必須是 `pass_with_healing`。

## 待討論

1. Medium risk 是否未來允許「AI 產 PR，但需人工先確認才 replay」。
2. Visual compare instability 是否需要獨立 policy。
3. Permission dialog 是否應歸入 setup recovery，或可作 micro-flow handling。
