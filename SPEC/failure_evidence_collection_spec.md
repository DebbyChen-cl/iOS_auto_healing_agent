# Failure Evidence Collection 規格

本文件定義 AI Auto-Healing 系統在 test case fail 當下需要收集的 evidence。目標是讓 AI 足夠判斷 root cause，並讓 HTML report 足夠支援人工 review。

## 核心決策

| 決策 | 內容 |
|---|---|
| 收集時機 | test case fail 當下立即收集 |
| 收集目標 | 保存 failure 現場狀態，支援 AI root cause analysis 與 HTML report |
| 收集策略 | 分成必收、條件收、建議收 |
| 不追求全收 | 不因為 fail 就保存所有 raw artifact；只保存 root cause 判斷需要的資料 |

## Failure Evidence Collection v1

| 類別 | 資料 | 建議 |
|---|---|---|
| Test / Run context | Stable Case ID、Run ID、branch、commit、app version、device、iOS version、environment | 必收 |
| Failure location | fail step id、step order、step action name、失敗發生在哪個 test line / function | 必收 |
| Error evidence | error message、stack trace、assertion message、exception type、timeout info | 必收 |
| Visual evidence | fail 當下 screenshot | 必收 |
| UI hierarchy | fail 當下 hierarchy / accessibility tree | 必收 |
| Step evidence | fail step before snapshot / hierarchy、fail step after 或 fail moment snapshot / hierarchy | 必收 |
| Network evidence | request status、HTTP code、timeout、server busy、connection reset | 有 network/server busy signal 時必收 |
| App state | foreground/background、current screen if available、permission state | 建議收 |
| Device state | app crash、device disconnect、memory warning、CPU/resource issue | 條件收 |
| Dependency state | upstream case status、fixture/setup status | 有 dependency 或 setup 失敗時收 |
| Retry evidence | retry count、retry result、是否不改 code 重跑後 pass | 有 retry 時收 |

## 必收最小集

以下資料是每個 fail case 都必須具備的最小 evidence：

| 類別 | 必收內容 |
|---|---|
| Identity | Stable Case ID、Run ID |
| Runtime | branch、commit、app version、device、iOS version、environment |
| Failure location | fail step id、step order、step action name、test line / function |
| Error evidence | error message、stack trace、assertion message、exception type、timeout info |
| Visual evidence | fail 當下 screenshot |
| UI hierarchy | fail 當下 hierarchy / accessibility tree |
| Step evidence | fail step before snapshot / hierarchy、fail step after 或 fail moment snapshot / hierarchy |

## 條件收集規則

| 條件 | 需要額外收集 |
|---|---|
| 有 network/server busy signal | request status、HTTP code、timeout、server busy、connection reset |
| 有 app / device crash signal | app crash、device disconnect、memory warning、CPU/resource issue |
| 有 dependency 或 setup 失敗 | upstream case status、fixture/setup status |
| 有 retry | retry count、retry result、是否不改 code 重跑後 pass |

## 與其他資料的分工

| 資料 | 所屬位置 | 說明 |
|---|---|---|
| Test Identity | `test_identity_spec.md` | 穩定 case metadata，不在 failure evidence 重複定義 |
| Previous Result History | `previous_result_history_spec.md` | 最近 5 次結果，不保存完整 evidence |
| Pass Baseline | `pass_baseline_retention_spec.md` | 需要比較正常流程時才查詢或補抓 |
| Failure Evidence | 本文件 | fail 當下現場狀態 |

## v1 實作規則

1. Fail 當下立即收集本文件定義的必收資料。
2. 條件收資料只在對應 signal 出現時收集。
3. 若必收資料缺失，該 case 不允許進入 L3 auto-healing，應標示 evidence gap 或 `manual_review_required`。
4. Failure Evidence 不負責保存完整 pass baseline；若 AI 需要正常流程比較，改查 `pass_baseline_retention_spec.md` 定義的 step-level baseline。
5. Failure Evidence 不負責保存 previous result history；上一輪狀態由 Previous Result Lookup 提供。

## 待討論

1. fail step id / step order 如何由測試框架 instrumentation 提供。
2. hierarchy / accessibility tree 的保存格式與壓縮方式。
3. screenshot 與 hierarchy 的保存路徑命名規則。
