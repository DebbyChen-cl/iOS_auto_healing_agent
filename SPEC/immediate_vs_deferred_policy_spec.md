# Immediate vs Deferred Policy 規格

本文件定義 AI Auto-Healing 系統在 test case fail 後，哪些情境可以立即使用唯一 iOS device 進行 retry / recovery，哪些情境要等整份 AT 跑完後再 deferred healing。

## 核心原則

| 原則 | 說明 |
|---|---|
| 立即處理要克制 | 目前只有一台 iOS device，immediate action 會拉長整份 AT 時間 |
| 只處理高必要性 failure | 只有會影響後續測試可信度，或晚點處理會失真的 failure 才 immediate |
| Immediate 不等於 healing | v1 的 immediate 多數是 retry、recovery 或 dependency analysis，不是 AI patch |
| Deferred 不等於不處理 | deferred healing 會在 full AT run 完成後進 queue |
| 所有 immediate rerun 最多一次 | 避免 CI 被無限制重跑拖住 |

## 四個 Lane

```text
Fail occurs
   |
   v
Scheduling Decision
   |
   +-- Lane A: Immediate crash / infrastructure handling
   |
   +-- Lane B: Immediate retry / recovery
   |
   +-- Lane C: Deferred healing after full AT run
   |
   +-- Lane D: No healing / manual path
```

## Lane A：Immediate Crash / Infrastructure Handling

| 類型 | v1 Policy | Rerun 次數 | Final Status |
|---|---|---:|---|
| App crash | 立刻重跑一次 | 1 | pass 後標 `pass_after_app_crash_retry`；仍 crash 則標 `app_crash` |
| Runner crash | 需要獨立 recover flow，但 v1 先不做 | 0 | `recover_flow_required` |
| Device disconnect | 需要獨立 recover flow，但 v1 先不做 | 0 | `recover_flow_required` |
| Env issue | 需要獨立 recover flow，但 v1 先不做 | 0 | `env_issue` 或 `recover_flow_required` |

說明：

1. App crash 允許立即重跑一次，因為它可能是單次不穩定，也可能代表產品或環境問題。
2. Runner crash、device disconnect、env issue 都需要更完整的 recover flow，例如重啟 runner、重新連 device、重建環境。v1 先不實作自動 recovery。
3. v1 不允許針對 crash / infra issue 做 AI healing patch。

## Lane B：Immediate Retry / Recovery

| 類型 | v1 Policy | Rerun / Recovery 次數 | 說明 |
|---|---|---:|---|
| Network / server busy | 立即重跑一次 | 1 | 這類問題跟時間點高度相關，晚點 retry 可能失真 |
| Smoke case fail | 立即重跑一次 | 1 | App 基本能力不通，後面結果可信度低 |
| Blocking case fail | 立即重跑一次 | 1 | 失敗會造成 downstream `blocked_by_upstream` |
| Setup / fixture root failure | recovery 或重跑一次 | 1 | 不處理會造成 cascade failure |
| Dependency root failure | immediate dependency analysis | 0 或 1 | 先找 root cause，不重跑大量 downstream |

說明：

1. 所有 immediate rerun 最多一次。
2. 若一次 retry / recovery 後仍失敗，不繼續重跑，交給 Final Reconciliation 標註。
3. Blocking case 的 retry 目的是保護後續結果可信度，不是為了把失敗洗成 pass。

## Lane C：Deferred Healing After Full AT Run

| 類型 | v1 Policy | 原因 |
|---|---|---|
| Locator drift | deferred healing queue | 不值得中斷 main run，full run 後可統一修 |
| Page object drift | deferred healing queue | 通常可以等 |
| Readiness / wait drift | deferred healing queue，除非 blocking case | 避免每個 timeout 都搶 device |
| Micro-flow drift | deferred healing queue，除非 blocking flow | 需要 App 操作 replay，成本較高 |
| Compare fail requiring image analysis | deferred analysis / healing | 圖像比較需要上下文，不適合搶 device |

說明：

1. Deferred healing 會在 full AT run 完成後執行。
2. Deferred healing 可以產生 patch、replay、HTML report、PR。
3. Deferred case 若最後修復成功，標成 `pass_with_healing`，不可標成普通 `pass`。

## Lane D：No Healing / Manual Path

| 類型 | v1 Policy | 說明 |
|---|---|---|
| Product bug suspected | 不做 healing，只 report | 保護品質訊號 |
| Assertion logic change required | 不做 healing | 走 new test case / redesign |
| Major workflow change | 不做 L3 healing | 需要人工判斷或新測試設計 |
| Insufficient evidence | 不做 healing | 標 `manual_review_required` |
| Unclassified low-confidence failure | 不做 healing | 避免 AI 誤修 |

## Immediate Rerun Budget

v1 統一規則：

| 類型 | 最多重跑 |
|---|---:|
| App crash | 1 |
| Network / server busy | 1 |
| Smoke case fail | 1 |
| Blocking case fail | 1 |
| Setup / fixture root failure | 1 |

全域限制：

1. 每個 case 的 immediate rerun 最多 1 次。
2. 同一 test run 的 immediate rerun 總量需要有上限，建議 v1 先設為最多 3 個 case 或總測試時間增加不超過 15%，先到先停。
3. 超過 immediate budget 後，後續 case 改走 deferred 或 manual path。

## Scheduling Decision 輸入

Scheduling Decision Gate 需要以下輸入：

| 輸入 | 用途 |
|---|---|
| failure type | 判斷 lane |
| Stable Case ID | 查 priority、blocking type、history |
| Priority | 高優先 case 可優先 immediate |
| Blocking Type | smoke / blocking case 可 immediate |
| Previous Result History | 判斷是否 repeated failure、flaky suspect |
| Failure Evidence | 判斷是否 crash、network、dialog、workflow |
| Device Availability | 確認是否能立即重跑 |
| Remaining Immediate Budget | 避免重跑失控 |

## Scheduling Decision 輸出

| 輸出 | 說明 |
|---|---|
| Lane | A / B / C / D |
| Action | rerun、recovery、dependency analysis、deferred healing、manual review、no healing |
| Rerun Allowed | yes / no |
| Rerun Count Limit | v1 一律最多 1 |
| Reason | 為什麼 immediate 或 deferred |
| Final Status Candidate | 若不重跑或不可 healing，先給候選狀態 |

## v1 實作規則

1. App crash 立即重跑一次。
2. Runner crash、device disconnect、env issue 需要獨立 recover flow，但 v1 不做自動 recovery。
3. Network/server busy、smoke fail、blocking fail、setup/fixture root failure 可 immediate rerun 或 recovery，但最多一次。
4. Locator drift、page object drift、readiness/wait drift、micro-flow drift 預設 deferred。
5. Product bug suspected、assertion logic change required、major workflow change 不進 healing。
6. 超過 immediate budget 後，不再搶 device，改 deferred 或 manual path。

## 待討論

1. 同一 test run 的 immediate rerun 全域上限是否採用最多 3 個 case 或 +15% 時間。
2. `pass_after_app_crash_retry` 是否要作為正式 final status。
3. Runner crash、device disconnect、env issue 的 recover flow 是否列入後續版本。
