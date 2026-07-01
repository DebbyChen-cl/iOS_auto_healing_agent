# Replay Verification 規格

本文件定義 AI Auto-Healing 修補後的 replay 驗證規則，包含 replay 次數、驗證範圍、通過條件，以及 shared page object / shared locator 的風險處理方式。

## 核心原則

Replay 的目的不是把 case 重跑到綠，而是驗證 AI 產生的 patch 是否真的修正 root cause，且沒有把品質訊號蓋掉。

| 原則 | 說明 |
|---|---|
| 原始 failure 不可覆蓋 | 原始 fail result 永遠保留；replay 只產生 healing result。 |
| Replay pass 不等於一般 pass | 修補後通過只能標為 `pass_with_healing`。 |
| 同一份 patch 不重複碰運氣 | 同一份 patch 最多 replay 一次；若失敗，必須由 AI 產生下一版 patch 後才能再次 replay。 |
| Assertion 不可被修改 | Replay 只能驗證 patch，不允許 AI 透過修改 assertion、expected value 或 comparison rule 讓 case pass。 |
| Device-aware queue | 目前只有一台 iOS device，所有 replay 都必須走 device queue。 |

## Replay 次數上限

Replay 預設最多可跑 3 次，但這 3 次代表最多 3 個 patch attempt，不是同一份 patch 重跑 3 次。

| Attempt | 觸發條件 | 可做的事 | 通過標註 |
|---|---|---|---|
| Replay 1 | 第一版 AI patch 產生後 | 驗證第一版 patch | `pass_with_healing` |
| Replay 2 | Replay 1 失敗，但 root cause 仍明確且仍屬低風險 healing | AI 產生第二版 patch 後再驗證 | `pass_with_healing` |
| Replay 3 | Replay 2 失敗，但失敗原因可被具體修正，且未超出 L3 邊界 | AI 產生第三版 patch 後再驗證 | `pass_with_healing` |

若 Replay 3 仍失敗，或中途需要修改 assertion / expected value / major workflow，則停止 L3 healing，標為 `healing_failed` 或 `manual_review_required`。

## Replay Scope

Replay scope 依 patch 影響範圍決定，不一定只跑原本 fail case。

| Patch 類型 | Replay scope | 說明 |
|---|---|---|
| 單一 case locator / wait / micro-flow patch | 原 fail case | 最低成本驗證。 |
| Blocking case immediate healing | 原 fail case，加上必要的 downstream smoke subset | 確認 blocking flow 修復後不會繼續阻斷主流程。 |
| Page object shared locator global update | 原 fail case，加上 impacted case subset | 只有能確認所有使用情境都同步改版時才允許。 |
| Context-specific locator / locator override parameter | 原 fail case；若可取得 shared usage case，額外跑 1 個仍使用 default path 的 case | 確認新 locator 只影響目標 case，沒有破壞原本 shared 行為。 |
| 無法判斷 patch 影響範圍且無法做局部化 patch | 不進 L3 replay | 轉 manual review。 |

## Shared Locator Impact Gate

當 root cause 是 locator drift，且該 locator 位於 shared page object 或 shared helper function 時，patch generation 前必須先進行 shared impact 判斷。

| 判斷結果 | Healing 策略 |
|---|---|
| 確定所有使用情境都同步改版 | 可做 global locator update。 |
| 確定只有特定 screen / feature 改版 | 新增 context-specific locator 或 screen-guarded resolver。 |
| 無法確認其他使用情境是否同步改版 | 不做 global update；新增 optional locator override parameter。 |
| 新 locator 本身不穩定或證據不足 | 不 patch，轉 manual review。 |

## Shared Locator Fallback Rule

若 shared locator 的影響範圍無法確認，AI 仍可進行 L3 healing，但只能使用 locator override parameter 的方式把新 locator 限制在失敗 case。

規則如下：

| 規則 | 說明 |
|---|---|
| 保留 default locator | 原本 shared page function 的預設 locator 不改，避免破壞其他 case。 |
| 新增 optional parameter | 在 page function 增加可選 locator 參數。 |
| 只改 fail case call site | 只有失敗 case 傳入新 locator，其他 case 仍走 default path。 |
| 不允許大規模參數化 | 只有 shared locator impact 不明時才允許此 fallback，不能把所有 locator 都改成由 test case 傳入。 |
| Report 必須標註 | HTML report 要明確寫出「因 shared locator 影響範圍不明，採用 locator override parameter」。 |

概念範例：

```text
原本：
tapExportButton()

Healing 後：
tapExportButton(locatorOverride = A_new_export_button_locator)
```

或：

```text
page function:
tapExportButton(locator = defaultExportButtonLocator)

fail case:
tapExportButton(locator = A_new_export_button_locator)

other cases:
tapExportButton()
```

## Replay 通過條件

Replay 必須同時滿足下列條件，才可標為 `pass_with_healing`。

| 條件 | 說明 |
|---|---|
| Patch 已套用 | Replay 必須使用 AI 產生的 candidate patch。 |
| App build / environment 一致 | 除非 report 明確標註，否則 replay 不應換 App build 或測試環境。 |
| 原 fail step 通過 | 原本 fail 的 step 必須通過。 |
| Final assertion 通過 | case 最後驗證必須通過，且 assertion logic 未被修改。 |
| 無新增高風險 signal | replay 不可新增 app crash、network/server busy、device disconnect、runner crash 等問題。 |
| Shared default path 未被破壞 | 若 patch 涉及 shared locator fallback，default path 不能被改壞。 |
| Evidence 完整 | 必須保存 replay screenshot、replay log、patch attempt、final status candidate。 |

## Replay 失敗處理

| 失敗情境 | 處理方式 |
|---|---|
| Replay fail，但 root cause 仍明確且仍是低風險 healing | 允許 AI 產生下一版 patch，直到最多 3 attempts。 |
| Replay fail，且需要修改 assertion / expected value | 停止 healing，標為 `needs_new_test_case` 或 `manual_review_required`。 |
| Replay fail，且疑似 product bug | 標為 `product_bug_suspected`。 |
| Replay 出現 network/server busy | 不算 patch 驗證失敗；依 retry policy 標註並進 report。 |
| Replay 出現 app crash | 依 app crash retry policy 最多立即重跑一次，仍 crash 則標為 `app_crash`。 |
| Replay evidence 不完整 | 不允許標為 `pass_with_healing`，轉 manual review。 |

## Report 必填資訊

當 case 進入 replay verification，HTML report 至少要呈現：

| 資料 | 說明 |
|---|---|
| Replay attempt count | 總共跑了幾次 patch attempt。 |
| 每次 replay 結果 | pass / fail 與主要失敗原因。 |
| 最終採用的 patch | 最後通過或最後失敗的 patch summary。 |
| Shared locator handling | 若使用 locator override parameter，必須清楚標註原因。 |
| Replay screenshot | 至少包含最終 replay 的關鍵 screenshot。 |
| Replay log summary | 不需要完整 raw log，但要有失敗或通過的摘要。 |
| Final status | `pass_with_healing`、`healing_failed`、`manual_review_required` 等。 |
