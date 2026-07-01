# Previous Result History 規格

本文件定義 AI Auto-Healing 系統如何保存與查詢上一輪 case 狀態。Previous Result History 是輕量歷史索引，用於 flaky 初判、regression 初判、scheduling decision 與 HTML report 趨勢說明。

## 核心決策

| 決策 | 內容 |
|---|---|
| 查詢 key | 使用 Stable Case ID |
| 保存筆數 | 每個 Stable Case ID 保存最近 5 次結果 |
| 資料型態 | 輕量結果摘要，不保存完整 evidence |
| 詳細資料查詢 | 需要細查時，用 Run ID 回查完整 report / artifact / healing record |
| 不保存內容 | 不保存 Duration、Blocking Impacted、HTML Report Link、PR Link、Artifact Link |

## 為什麼不是最近 10 次

v1 的目標是支援：

1. 上一輪狀態查詢
2. 新失敗 / 回歸初判
3. flaky suspect 初判
4. AI root cause analysis 的歷史上下文
5. HTML report 的簡單趨勢說明

最近 5 次已足夠支援上述用途。若要做長期趨勢分析，應另外建立 aggregate metrics，不應把每個 case 的 history record 無限制變大。

## 每筆 History Record 欄位

| 欄位 | 是否必填 | 說明 |
|---|---|---|
| Stable Case ID | 必填 | 對應 Test Identity 的 stable id |
| Run ID | 必填 | 回查完整 run、report、artifact、healing record 的入口 |
| Timestamp | 必填 | 此次執行時間 |
| Branch | 必填 | 分辨 main、release、feature branch |
| Commit | 必填 | 此次測試對應的程式碼版本 |
| App Version / Build | 必填 | iOS App 版本或 build number |
| Environment | 必填 | 測試環境，例如 staging、QA、nightly |
| Device / iOS Version | 建議 | iOS UI 測試受 device 與 OS 影響，建議保留 |
| Original Status | 必填 | 原始 test runner 結果 |
| Final Status | 必填 | reconciler 後的最終標註 |
| Failure Type | fail 類必填 | 對應 failure taxonomy |
| Root Cause Summary | fail 類必填 | 簡短 root cause 摘要 |
| Action Taken | 有 retry / healing / recovery 時必填 | 說明系統採取的處理 |
| Healing Status | 有 healing 時必填 | healing succeeded、failed、skipped |
| Reviewer Decision | 有 review 時必填 | approved、rejected、manual review required |

## 不保存的欄位

| 欄位 | 不保存原因 | 替代方式 |
|---|---|---|
| Duration | v1 不做效能退化分析 | 未來若需要，放到 metrics |
| Blocking Impacted | 可由 dependency analysis / final report 推導 | 不放在 history |
| HTML Report Link | 可由 Run ID 回查 | 不重複保存 |
| PR Link | 應放在 healing record / review record | 不放在 history |
| Artifact Link | 可由 Run ID 回查 artifact store | 不重複保存 |
| 完整 screenshot / trace / log | 體積過大，不屬於 history | 放在 evidence store |

## History Summary

除了最近 5 筆輕量結果，每個 Stable Case ID 可以保留一份小型摘要，方便 classifier 與 AI 快速使用。

| Summary 欄位 | 說明 |
|---|---|
| Last 5 Status Pattern | 最近 5 次 final status 序列，例如 pass、pass、fail、pass_after_retry、fail |
| Recent Failure Count | 最近 5 次有幾次非 pass |
| Recent Flaky Signal | 最近 5 次是否出現 pass/fail 交替 |
| Last Trusted Status | 最近一次可信狀態，例如原始 pass 或 reviewer approved 的 pass_with_healing |
| Last Failure Type | 最近一次 failure type |
| Last Root Cause Summary | 最近一次 root cause 摘要 |

## 使用情境

| 使用者 | 如何使用 |
|---|---|
| Previous Result Lookup Gate | 用 Stable Case ID 查最近 5 次結果，輸出上一輪狀態與趨勢摘要 |
| Preliminary Classifier | 判斷是否是新失敗、重複失敗、疑似 flaky |
| AI Root Cause Gate | 提供歷史上下文，避免只看單次 failure |
| Scheduling Decision Gate | 若過去多次 network/server busy 或 flaky，可避免立即做 healing |
| Final Reconciliation Gate | 產生狀態變化說明，例如 new failure、repeated failure、recovered |
| HTML Report Gate | 顯示簡單歷史趨勢，不需要塞完整 artifact |

## 狀態判斷範例

| 最近 5 次模式 | 可能判斷 |
|---|---|
| pass、pass、pass、pass、fail | 新失敗 / regression candidate |
| fail、fail、fail、fail、fail | 持續失敗，需要 root cause grouping |
| pass、fail、pass、fail、pass | flaky suspect |
| pass_with_healing、pass_with_healing、pass_with_healing | healing 可能已變成穩定修補，應確認 PR 是否已 merge |
| server_busy、pass_after_network_retry、server_busy、pass_after_network_retry | network/server busy pattern |

## v1 實作規則

1. 每次 test run 結束後，由 Final Reconciliation Gate 寫入每個 case 的 history record。
2. 每個 Stable Case ID 最多保留最近 5 筆。
3. 寫入新 record 後，超過 5 筆的舊 record 可以移到長期 archive 或刪除。
4. 查詢時必須使用 Stable Case ID；若缺少 Stable Case ID，回傳 history unavailable。
5. Previous Result History 不保存完整 evidence，只保存可快速判斷趨勢的摘要。

## 待討論

1. 最近 5 次是以同 branch 為主，還是跨 branch 混合保存。
2. Last Trusted Status 的定義是否只接受原始 `pass` 與 reviewer approved 的 `pass_with_healing`。
3. History archive 是否需要長期保存，或 v1 只保留最近 5 筆即可。
