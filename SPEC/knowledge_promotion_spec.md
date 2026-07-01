# Knowledge Promotion 規格

本文件定義 AI Auto-Healing 系統如何把一次性的 analysis / healing / replay / review event，提升成未來 AI 可重複使用的長期 knowledge。

## 核心原則

Knowledge Promotion 的目標不是把所有 AI 分析都存起來，而是只保存已被 reviewer 接受、可被未來安全重用的事實。

| 原則 | 說明 |
|---|---|
| Review 後才 promotion | 未經 reviewer 接受的 event 不可進長期 knowledge。 |
| 事實優先於猜測 | Knowledge 只能來自 evidence + replay + review，不來自 AI 自己的推測。 |
| 不污染測試意圖 | 不能把 assertion change、expected value change、product bug workaround 存成 auto-healing knowledge。 |
| 可追溯 | 每筆 knowledge 必須能追到 source run、case、report、PR 或 review decision。 |
| 可降級 | 後續若發現 knowledge 錯誤或過期，必須能標為 deprecated。 |

## Knowledge 類型

| 類型 | 用途 | 例子 |
|---|---|---|
| App Usage Knowledge | 增加 AI 理解 PHD iOS App 如何使用 | 進入某功能前新增確認 button；Export 前需要等待 generation 完成。 |
| Test Fragility Knowledge | 增加 AI 理解 auto testing 容易 fail 的部分 | 某 page object locator 容易因 A/B screen 差異漂移；某畫面需要 state-based wait。 |
| Coverage Opportunity Knowledge | 增加整個 auto testing coverage 的線索 | workflow change 顯示目前缺少新路徑 test case；某功能新增 optional dialog。 |

## Promotion Eligibility

| Event / Decision 狀態 | 可否 Promotion | 說明 |
|---|---|---|
| `approve_merge_allowed` | 可以 | reviewer 接受 report，PR 可 merge。 |
| `reject_healing` | 不可以 | AI 修補或分析不可信。 |
| `need_more_evidence` | 不可以 | evidence 不足，不能變成長期知識。 |
| `manual_code_review_required` | 不可以 | 除非後續人工 code review 明確 approve，否則不可 promotion。 |
| `product_bug_suspected` | 不進 auto-healing knowledge | 可進 bug trend / product quality report，但不能教 AI 用測試修補掩蓋產品問題。 |
| 單次 flaky | 不可以 | 只能保留在 event history 或 metrics，不能直接 promotion。 |
| network/server busy | 不進 healing knowledge | 放 metrics / infra trend。 |
| generation fail | 不進 healing knowledge | 放 metrics / infra or service trend。 |

## Knowledge Confidence

長期 knowledge 至少分為三個狀態。

| Confidence | 意義 | 使用限制 |
|---|---|---|
| `candidate` | 已通過 review，但只出現一次或影響範圍仍有限 | AI 可參考，但不可單獨作為自動 patch 的唯一依據。 |
| `trusted` | 多次 approved event 支撐，或由 reviewer 明確標記為穩定知識 | AI 可主動使用於分類、healing suggestion、new case generation。 |
| `deprecated` | 後續版本不再適用、被 reviewer 否定、或造成錯誤 healing | AI 不可再使用，只保留歷史追溯。 |

## Promotion Rule

| 條件 | 產生的 Knowledge 狀態 |
|---|---|
| 單次 `approve_merge_allowed` 且 evidence 完整 | `candidate` |
| 同一 pattern 重複出現並被 approve，或 reviewer 明確確認為通用規則 | `trusted` |
| reviewer 指出此 knowledge 不再適用 | `deprecated` |
| 新版 App workflow 改變導致舊 knowledge 誤導 AI | `deprecated` 或改寫成新版 knowledge |

## 每筆 Knowledge 必填欄位

| 欄位 | 說明 |
|---|---|
| Knowledge ID | 長期 knowledge 的唯一 ID。 |
| Knowledge Type | App Usage、Test Fragility、Coverage Opportunity。 |
| Title | 人類可讀的一句話摘要。 |
| Description | 具體內容與適用場景。 |
| Source Event | run id、stable case id、report id、PR id。 |
| Source Evidence | failure evidence、replay evidence、review decision 的摘要。 |
| Confidence | candidate、trusted、deprecated。 |
| Applies To | feature/module、app area/screen、page object、test component。 |
| Avoid / Boundary | 不適用情境與不可用來做什麼。 |
| Created At / Updated At | 建立與更新時間。 |
| Reviewer | 最後確認此 knowledge 的 reviewer。 |

## 不可 Promotion 的內容

| 內容 | 原因 |
|---|---|
| AI 未經 review 的 root cause guess | 容易污染後續判斷。 |
| assertion / expected value 修改 | 已超出 auto-healing 邊界。 |
| product bug workaround | 會掩蓋產品缺陷。 |
| 單次 flaky 現象 | 需要歷史趨勢，不可因一次 pass_after_retry 就變成規則。 |
| network/server busy 單次事件 | 屬 infra / service trend，不是 App usage 或 test fragility。 |
| generation fail 單次事件 | 屬服務或生成流程趨勢，不應進 healing knowledge。 |
| evidence incomplete event | 缺乏可信來源。 |

## Knowledge 使用邊界

| 使用場景 | 可使用 Knowledge |
|---|---|
| Auto-healing classification | trusted App Usage / Test Fragility。 |
| Patch generation | trusted Test Fragility；candidate 只能作輔助參考。 |
| HTML report explanation | candidate / trusted 都可列為參考，但需標 confidence。 |
| Generate new case | trusted App Usage / Coverage Opportunity；candidate 需標註仍待驗證。 |
| Metrics / trend report | event history、infra trend、bug trend，不一定要 promotion 成 knowledge。 |

## Knowledge 與 Event History 的差異

| 類型 | 保存什麼 | 用途 |
|---|---|---|
| Event History | 每次 fail / retry / healing / replay / review 的原始紀錄 | 追溯、debug、metrics、trend。 |
| Knowledge Store | 被 review 接受並萃取後的長期規則或事實 | 幫助未來 AI 分析、healing、new case generation。 |

Event History 可以包含 rejected、need_more_evidence、manual review event；Knowledge Store 不可以。

## Promotion Flow

```text
Approved healing / review event
  |
  v
Extract candidate knowledge
  |
  v
Classify as App Usage / Test Fragility / Coverage Opportunity
  |
  v
Attach source event and evidence
  |
  v
Set confidence = candidate
  |
  v
Promote to trusted only after repeated approval or explicit reviewer confirmation
```

## Network / Server Busy / Generation Fail

Network/server busy 與 generation fail 不進 healing knowledge。它們應另外進 Metrics / Infra Trend。

| 類型 | 保存位置 | 用途 |
|---|---|---|
| network/server busy | Metrics / Infra Trend | 觀察 server busy 頻率、影響 case 數、是否需要 infra 改善。 |
| generation fail | Metrics / Service Trend | 觀察生成服務穩定性與失敗率。 |
| app crash | Product Quality Trend / Crash Trend | 觀察 crash pattern，不作為 healing knowledge。 |

## 與 New Case Generator 的關係

New Case Generator 可以使用 trusted App Usage Knowledge 與 trusted Coverage Opportunity Knowledge。Test Fragility Knowledge 可用來避免生成容易 flaky 的 test step，但不能用來降低 assertion 標準。

詳細讀取邊界由 `new_case_generator_boundary_spec.md` 定義。
