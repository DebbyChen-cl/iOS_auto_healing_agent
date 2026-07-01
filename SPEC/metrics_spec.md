# Metrics 規格

本文件定義 AI Auto-Healing 系統的成效衡量方式。Metrics 的目標不是證明 pass rate 變高，而是證明系統有省下維護時間，同時沒有蓋掉 product bug、infra issue、flaky 或其他品質訊號。

## 核心原則

| 原則 | 說明 |
|---|---|
| 不以總 pass rate 作為主 KPI | 單純追求 pass rate 會鼓勵系統把 fail 變綠，與品質目標衝突。 |
| `pass_with_healing` 必須獨立統計 | AI 修復後通過不等於一般 pass。 |
| Infra / service issue 要獨立量化 | network/server busy、generation fail、device/runner issue 不可混進 healing success。 |
| 品質訊號保護優先 | product bug suspected、manual review、rejected healing 都是重要訊號，不是系統失敗。 |
| 主管報告要能看趨勢 | 除 run-level 指標外，也要支援 weekly / release-level 趨勢。 |

## Top-Level Metrics

主管報告建議優先呈現下列 6 個 top-level metrics。

| Metric | 定義 | 目的 |
|---|---|---|
| Auto-healing eligible rate | eligible healing cases / failed cases | 看有多少 failure 屬於可安全修補的維護問題。 |
| Healing success rate | successful healing cases / attempted healing cases | 看 AI 修補能力是否穩定。 |
| Report approval rate | approve_merge_allowed / generated healing reports | 看 reviewer 是否信任 AI healing report。 |
| False healing / rejected healing rate | rejected healing or post-merge regression / attempted healing cases | 看 AI 是否有誤修風險。 |
| Network/server busy + generation fail rate | network/server busy 與 generation fail cases / total cases | 把常見 infra / service 問題獨立量化。 |
| Time saved estimate | estimated manual time - AI flow review time | 對主管呈現導入價值。 |

## 核心品質指標

| Metric | 定義 | 為什麼重要 |
|---|---|---|
| `time_saved_estimate` | 原本人工 debug / 修 locator / replay 的估計時間，減去 AI analysis / replay / report review 時間 | 衡量是否真的省時間。 |
| `false_healing_rate` | reviewer reject、merge 後造成 regression、或後續證明 root cause 錯誤的 healing / attempted healing | 衡量誤修風險。 |
| `quality_signal_preserved_rate` | product bug、infra issue、manual review case 沒被誤標成 pass 的比例 | 衡量系統是否保住品質訊號。 |

## Run-Level Metrics

每次 AT run 的 HTML report 應包含 run-level metrics。

| 分類 | 指標 |
|---|---|
| Run Result | total cases、pass、fail、pass_with_healing、pass_after_retry、pass_after_network_retry、pass_after_generation_retry、manual_review_required |
| Failure Mix | locator drift、page object drift、wait/readiness drift、workflow change、network/server busy、generation fail、app crash、product bug suspected、dependency cascade |
| Healing | eligible healing count、attempted healing count、healing success count、healing failed count、replay attempt count、average replay attempts per case |
| Review | approve_merge_allowed、reject_healing、need_more_evidence、manual_code_review_required |
| PR | PR created、PR approved、PR merged、PR rejected、PR blocked |
| Knowledge | candidate knowledge created、trusted knowledge promoted、deprecated knowledge count |
| Time | AT runtime overhead、AI analysis time、replay time、report review time、estimated manual time saved |

## Trend Metrics

Weekly / release-level report 應呈現趨勢，而不是只看單次 run。

| 趨勢 | 目的 |
|---|---|
| Failure type trend | 找出最常發生的 failure 類型。 |
| Healing success trend | 看 L3 healing 是否越來越穩定。 |
| Rejected healing trend | 看 AI 誤判是否增加。 |
| Network/server busy trend | 量化 server busy 對 AT 的影響。 |
| Generation fail trend | 量化生成服務失敗對 AT 的影響。 |
| App crash trend | 量化 crash 對測試穩定性的影響。 |
| Knowledge growth trend | 看 candidate / trusted knowledge 是否持續增加。 |
| Review time trend | 看 HTML report 是否真的降低 review 成本。 |

## Status Counting Rules

| Status | 是否算一般 pass | 是否算 fail | 統計方式 |
|---|---|---|---|
| `pass` | 是 | 否 | 原始測試通過。 |
| `pass_with_healing` | 否 | 原始是 fail | 獨立列為 AI healing success。 |
| `pass_after_retry` | 否 | 原始是 fail | 獨立列為 retry recovery / flaky signal。 |
| `pass_after_network_retry` | 否 | 原始是 fail | 獨立列為 network/server busy trend。 |
| `pass_after_generation_retry` | 否 | 原始是 fail | 獨立列為 generation fail trend。 |
| `manual_review_required` | 否 | 是 | 保留品質訊號。 |
| `product_bug_suspected` | 否 | 是 | 不可算 healing failure，應進 product quality trend。 |
| `blocked_by_upstream` | 否 | 不算獨立 fail | 算 dependency impact。 |

## Time Saved Estimate

`time_saved_estimate` 用估算即可，v1 不需要精準到分鐘級真實工時。

| 項目 | 說明 |
|---|---|
| Estimated manual debug time | 可依 failure type 設定預估值，例如 locator drift 20 分鐘、wait drift 15 分鐘、micro-flow drift 30 分鐘。 |
| AI processing time | AI analysis + patch generation + replay time。 |
| Reviewer time | reviewer 看 HTML report 的時間。 |
| Saved time | estimated manual debug time - AI processing time - reviewer time。 |

若 saved time 為負，代表該類 healing 暫時不划算，應回頭檢查 evidence collection、classification 或 report quality。

## Quality Guardrail Metrics

這些指標比 pass rate 更重要。

| Guardrail | 警訊 |
|---|---|
| false healing rate | 持續上升代表 AI 正在誤修。 |
| rejected healing rate | 持續上升代表 L3 eligibility 太寬或 evidence 不足。 |
| need_more_evidence rate | 持續上升代表 evidence collection 不夠。 |
| manual_code_review_required rate | 持續上升代表 auto-healing 邊界不清或產品流程變動太大。 |
| product_bug_suspected count | 不應被壓低成 pass，應保留並追蹤。 |
| pass_after_retry count | 持續上升代表 flaky 或環境不穩。 |

## Infra / Service Metrics

network/server busy 與 generation fail 必須獨立追蹤。

| Metric | 說明 |
|---|---|
| network_server_busy_rate | network/server busy cases / total cases。 |
| network_retry_success_rate | pass_after_network_retry / network/server busy cases。 |
| generation_fail_rate | generation fail cases / total cases。 |
| generation_retry_success_rate | pass_after_generation_retry / generation fail cases。 |
| app_crash_rate | app crash cases / total cases。 |
| runner_device_issue_count | runner crash、device disconnect、recover flow required 次數。 |

## Metrics Report 週期

| 週期 | 用途 |
|---|---|
| 每次 AT run | 顯示 run-level result、failure mix、healing result、review status、PR status。 |
| 每週 | 顯示趨勢：省時、失敗類型、infra/service 問題、AI healing reliability。 |
| 每個 release | 給主管與團隊看導入成效、風險、coverage / knowledge 增長。 |

## 不建議作為主 KPI 的指標

| 指標 | 原因 |
|---|---|
| Total pass rate increase | 容易鼓勵把 fail 變綠，掩蓋品質訊號。 |
| Number of healed cases only | 只看修了幾個，無法看出誤修風險。 |
| AI patch count | patch 多不代表有效。 |
| PR count | PR 多不代表省時或品質好。 |

## Metrics v1 結論

Metrics v1 的主軸是：

```text
AI 讓可維護型 failure 更快被修掉，
同時不壓掉 product bug、infra issue、flaky signal。
```

因此主管報告應優先呈現：省下多少人工時間、哪些 failure 被安全修復、哪些品質訊號被保留下來、哪些 infra / service issue 需要另外改善。
