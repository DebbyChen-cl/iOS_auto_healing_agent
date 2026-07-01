# AI Auto-Healing 系統待決策 TODO

本文件記錄大架構已定後，仍需要逐項討論並決定的實作細節。

## 優先討論

| 優先 | 待決策項目 | 要決定什麼 | 影響範圍 |
|---|---|---|---|
| 1 | Test Identity | 如何定義穩定 case id、feature、owner、priority、dependency | Previous result lookup、coverage、knowledge、report |
| 2 | Previous Result Lookup | 上一輪 case 狀態從哪裡自動取得 | flaky 判斷、regression 判斷、report 趨勢 |
| 3 | Pass Baseline Retention | 已定義 step-level baseline、fail step 含前 5 step window、補抓條件 | AI 比對能力、storage 成本 |
| 4 | Failure Evidence Collection | 已定義必收、條件收與建議收 evidence | AI root cause 準確度、HTML report 品質 |
| 5 | Failure Taxonomy Priority | 已定義以 fail screenshot + Error Step 為起點的分類優先順序 | 分類一致性、是否誤 healing |
| 6 | Immediate vs Deferred Policy | 已定義四個 lane、app crash 立即重跑一次、其他 recover flow v1 先不做 | AT 執行時間、device queue |
| 7 | Retry Policy | 已定義所有 immediate retry 最多一次、generation fail、smoke/blocking retry fail 後進 auto-healing 環節 | 測試時間、false fail、flaky 判斷 |
| 8 | L3 Healing Eligibility | 已定義 blocking impact、healing risk、L3 matrix、immediate healing eligibility | AI 修改範圍、風險邊界 |
| 9 | Replay Verification | 已定義 replay 上限、replay scope、shared locator fallback 與通過條件 | `pass_with_healing` 可信度 |
| 10 | HTML Report Approval Rule | 已定義嚴格版 approval checklist、decision 類型與 merge allowed 條件 | 人工審核品質、merge gate |
| 11 | PR Generation Rule | 已定義一輪 AT run 最多一個 Auto-Healing PR、included / excluded case 規則與 merge gate | review 成本、修補可追蹤性 |
| 12 | Knowledge Promotion | 已定義 promotion eligibility、三類 knowledge、confidence 與不可 promotion 內容 | future AI 準確度、錯誤知識污染 |
| 13 | New Case Generator Boundary | 已定義可讀 trusted knowledge、candidate 限制、禁止資料來源與 generated case 狀態 | 測試生成品質、規格污染 |
| 14 | Metrics | 已定義 run-level / trend-level metrics、status counting rules、品質 guardrail 與主管報告核心指標 | 導入成效、主管報告 |

## 目前討論順序

所有目前規劃中的 TODO 已完成。

## 已定案原則摘要

1. 目標成熟度是 L3：AI 可自動套用低風險修補並建立 PR，但不能自動 merge。
2. AI 不能修改 assertion 程式碼、expected value 或驗證邏輯。
3. Assertion failure 是表象，要追 root cause；不能看到 assertion 就直接排除 healing。
4. AI 修復後通過的 case 必須標成 `pass_with_healing`，不可標成一般 `pass`。
5. HTML report 是主要人工審核介面，report approve 後才允許 merge PR。
6. Knowledge 需要等 review 後才可 promotion，不可把未審核 healing event 直接寫入長期知識庫。
7. Replay Verification 預設最多 3 個 patch attempts；同一份 patch 不重複 replay。Shared locator 影響範圍不明時，不做 global update，改用 locator override parameter 限制在失敗 case。
8. L3 healing 的 HTML report approval 採嚴格版；只有 `approve_merge_allowed` 可以允許 PR merge，其餘 `reject_healing`、`need_more_evidence`、`manual_code_review_required` 都不可 merge。
9. PR Generation 採 run-level PR；一輪 AT run 最多一個 Auto-Healing PR，PR 只包含 replay pass、L3 low-risk、可被嚴格 HTML report approval 審核的 healing patches。其他 fail case 只出現在 report，不進 PR。
10. Knowledge Promotion 只允許 reviewer 接受的事實進長期知識；`approve_merge_allowed` 可進 candidate，重複 approved 或 reviewer 明確確認後才可成為 trusted。Network/server busy、generation fail、單次 flaky 不進 healing knowledge，改進 metrics / trend。
11. New Case Generator 只能使用 trusted knowledge 作為正式 test case 生成依據；candidate knowledge 只能產生 draft / idea，event history、rejected healing、need_more_evidence、manual_code_review_required、product_bug_suspected、network/server busy、generation fail 不可作為正式生成依據。
12. Metrics 不以總 pass rate 作為主 KPI；核心衡量是 time saved、healing success、report approval、false healing / rejected healing、quality signal preserved，以及 network/server busy 與 generation fail 的獨立趨勢。
