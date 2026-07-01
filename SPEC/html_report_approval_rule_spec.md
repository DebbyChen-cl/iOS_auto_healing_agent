# HTML Report Approval Rule 規格

本文件定義 AI Auto-Healing HTML report 作為 merge gate 時的嚴格審核規則。此規格只適用於 L3 healing 產生的 PR；非 L3 的 observation report 可以較寬鬆，但不能作為 merge gate。

## 核心原則

HTML report approval 的目的不是確認「測試變綠」，而是確認：

1. failure root cause 有足夠證據支撐。
2. AI patch 沒有改變測試意圖。
3. replay 證明修補有效。
4. 風險與 shared impact 已清楚揭露。

只有符合嚴格版 approval checklist 的 report，才可以得到 `approve_merge_allowed`。

## Approval Decision

| Decision | 意義 | 後續 |
|---|---|---|
| `approve_merge_allowed` | report 證據完整，AI healing 合法且 replay 通過 | 允許 merge PR |
| `reject_healing` | AI 判斷錯誤、patch 方向錯誤、或修補不應被接受 | 不 merge，保留 failure 或重新分析 |
| `need_more_evidence` | healing 方向可能正確，但 report 缺少必要 evidence | 補 evidence、補 replay 或重新產生 report |
| `manual_code_review_required` | 風險超過 report-only review 能承擔的範圍 | 必須打開 code diff 深入 review |

只有 `approve_merge_allowed` 可以讓 PR 進入 merge allowed 狀態。其他 decision 都不能 merge。

## 嚴格 Approval Checklist

L3 healing report 必須全部符合下列條件，才可以 approve。

| Gate | 必須滿足 | 不滿足時 |
|---|---|---|
| Failure Evidence 完整 | 有 fail screenshot、fail step、error message、stack trace 或 assertion message、fail hierarchy、必要的 step evidence | `need_more_evidence` |
| Root Cause 明確 | 有 failure type、AI root cause、證據來源、排除過的主要可能原因 | `need_more_evidence` 或 `reject_healing` |
| Healing Scope 合法 | 沒有修改 assertion、expected value、comparison rule、測試意圖 | `reject_healing` 或 `manual_code_review_required` |
| Patch 低風險 | patch 屬於 locator、page object locator、state-based wait、micro-flow、locator override parameter 等 L3 允許範圍 | `manual_code_review_required` |
| Shared Impact 有交代 | 若動到 shared page object / helper，必須說明 global update、context-specific 或 locator override parameter | `need_more_evidence` |
| Replay 通過 | 有 replay attempt count、最終 replay result、replay screenshot、replay log summary，且 final assertion 通過 | `need_more_evidence` 或 `reject_healing` |
| Final Status 正確 | 修補成功只能標為 `pass_with_healing`，不能標為一般 `pass` | `reject_healing` |
| PR 對得上 Report | report 的 patch summary、changed files、risk flags 必須與 PR diff 一致 | `manual_code_review_required` |

## 必須出現在 Report 的區塊

| 區塊 | 內容 |
|---|---|
| Run Summary | Run ID、branch、commit、app version、device、iOS version、environment |
| Case Summary | Stable Case ID、case name、feature/module、priority、blocking type、previous result |
| Failure Snapshot | fail screenshot、fail step、error message、failure location |
| Evidence Summary | hierarchy、step evidence、network/app/device/dependency evidence 是否存在 |
| AI Root Cause | failure type、root cause、信心、主要證據、排除原因 |
| Healing Action | AI 修改了什麼、為什麼這樣修、是否使用 locator override parameter |
| Patch Summary | changed files、changed functions、禁止修改項檢查結果 |
| Replay Verification | attempt count、每次 replay 結果、最終 replay screenshot、final status candidate |
| Risk Flags | shared locator、dependency、flaky signal、evidence gap、manual review risk |
| Reviewer Decision | approve / reject / need more evidence / manual code review required |

## Merge Allowed 條件

PR 只有在下列條件全部成立時，才可以 merge。

| 條件 | 說明 |
|---|---|
| Report decision 是 `approve_merge_allowed` | Reviewer 明確 approve。 |
| Final status 是 `pass_with_healing` | 不接受一般 pass 覆蓋原始 failure。 |
| Replay 通過 | 至少最後一次 replay pass，且 evidence 完整。 |
| 沒有禁止修改 | 沒有 assertion、expected value、comparison rule、test intent 修改。 |
| 沒有 unresolved high-risk flag | 例如 product bug suspected、major workflow change、evidence incomplete。 |
| PR diff 與 report 一致 | report 看到的修補內容就是 PR 裡的修補內容。 |

## 自動拒絕條件

只要出現下列任何一項，不可 approve merge。

| 條件 | Decision |
|---|---|
| 修改 assertion / expected value / comparison rule | `reject_healing` |
| Replay 未通過 | `reject_healing` |
| 缺 fail screenshot 或 replay screenshot | `need_more_evidence` |
| root cause 不明確但仍產生 patch | `reject_healing` |
| product bug suspected | `manual_code_review_required` |
| major workflow change，需要重新定義測試意圖 | `manual_code_review_required` |
| shared locator global update 但沒有 impacted scope 說明 | `need_more_evidence` |
| report patch summary 與 PR diff 不一致 | `manual_code_review_required` |

## Report-only Review 邊界

下列情境可以只看 HTML report 做 approval：

| 情境 | 條件 |
|---|---|
| locator drift | evidence 顯示 element 存在，locator 更新或 locator override 合理，replay pass |
| state-based wait | evidence 顯示 timing/readiness 問題，等待條件明確，replay pass |
| small micro-flow | 新增步驟很小，例如進入功能前多一個確認 button，且不改測試意圖 |
| shared locator fallback | 採 locator override parameter，default locator 保留，report 有標註原因 |

下列情境不能只看 HTML report approve，必須進 manual code review：

| 情境 | 原因 |
|---|---|
| assertion logic change | 已超出 auto-healing 邊界 |
| expected value / golden image 更新 | 可能改變驗證標準 |
| comparison tolerance / ignore region 調整 | 可能掩蓋產品問題 |
| major workflow rewrite | 應走 new test case 或人工重構 |
| product bug suspected | 不應用測試修補掩蓋產品缺陷 |

## Knowledge Promotion 前提

只有 `approve_merge_allowed` 的 event 可以進入 Knowledge Promotion Gate。`reject_healing`、`need_more_evidence`、`manual_code_review_required` 只能保留在 event history，不能直接提升為長期知識。
