# New Case Generator Boundary 規格

本文件定義未來自動產生 test case 的 AI 可以讀取哪些 Auto-Healing 產物，以及哪些資料不可作為正式 test case 生成依據。目標是讓 new case generator 能利用已審核的知識擴充 coverage，同時避免被未審核 healing event、AI guess 或短期環境問題污染。

## 核心原則

| 原則 | 說明 |
|---|---|
| Trusted knowledge 才能作為正式依據 | 正式 test case 生成只能依據 `trusted` knowledge。 |
| Candidate 只能提示，不可直接定規格 | `candidate` knowledge 可以提示 coverage opportunity，但產出的 case 必須標為 draft 並人工 review。 |
| Event history 不等於規格 | Event history 可供背景查詢，但不可直接拿來當產品流程或測試規格。 |
| 不使用 rejected / incomplete evidence | 被 reject、證據不足、需要人工 review 的事件不可用來生成正式 case。 |
| 不降低 assertion 標準 | Test Fragility Knowledge 只能幫助避免 flaky 寫法，不能用來放寬 assertion、expected value 或 comparison rule。 |

## 可讀取資料

| 資料來源 | 可否使用 | 允許用途 |
|---|---|---|
| Trusted App Usage Knowledge | 可以 | 理解 PHD iOS App 的正確操作流程與 screen / workflow。 |
| Trusted Coverage Opportunity Knowledge | 可以 | 產生新 test case 的正式依據。 |
| Trusted Test Fragility Knowledge | 可以，但有限制 | 避免生成容易 flaky 的 locator、wait、step pattern。 |
| Candidate App Usage Knowledge | 可以參考 | 只能產生 draft case idea，需人工 review。 |
| Candidate Coverage Opportunity Knowledge | 可以參考 | 只能產生 draft case idea，不能自動進正式 case。 |
| Candidate Test Fragility Knowledge | 可以參考 | 只能提醒風險，不可單獨決定 test 設計。 |
| Approved HTML Report | 可以 | 查詢 source evidence、root cause、review decision。 |
| Approved PR Diff | 可以 | 理解已被接受的 page object / flow 修補方式。 |
| Test Identity | 可以 | 對齊 feature/module、app area、priority、blocking type。 |

## 不可作為正式生成依據的資料

| 資料來源 | 規則 | 原因 |
|---|---|---|
| Raw Event History | 不可直接使用 | 未必經過審核，可能只是一次性現象。 |
| Rejected Healing | 不可使用 | 已被 reviewer 否定。 |
| `need_more_evidence` event | 不可使用 | 證據不足。 |
| `manual_code_review_required` event | 不可使用，除非後續人工 approve | 風險未釐清。 |
| `product_bug_suspected` | 不可當成正常產品規格 | 可能是產品缺陷，不應生成正常流程 case。 |
| 單次 flaky | 不可使用 | 不足以代表穩定行為。 |
| network/server busy | 不可使用 | 屬 infra / service trend，不是產品流程。 |
| generation fail | 不可使用 | 屬生成服務穩定性，不是 App usage。 |
| Assertion / expected value 修改事件 | 不可使用 | 已超出 auto-healing 邊界。 |

## Knowledge 類型使用邊界

| Knowledge 類型 | New Case Generator 可以做什麼 | 不可以做什麼 |
|---|---|---|
| App Usage Knowledge | 建立操作步驟、前置條件、screen transition、必要等待條件 | 推翻產品規格或改變 expected behavior。 |
| Coverage Opportunity Knowledge | 建議新 case、補 coverage gap、補 workflow branch | 直接把 candidate 當正式 case。 |
| Test Fragility Knowledge | 避免 fragile locator、加入 state-based wait、避開已知 flaky pattern | 降低 assertion、刪除驗證、放寬 comparison tolerance。 |

## Candidate Knowledge 使用規則

`candidate` knowledge 可以被 new case generator 讀取，但只能產生 draft。

| 使用方式 | 規則 |
|---|---|
| 產生 case idea | 可以，但必須標註來源是 candidate。 |
| 產生正式 test case | 不可以。 |
| 自動開 PR | 不可以。 |
| 人工 review 後採用 | 可以，reviewer 需明確接受該 candidate knowledge 或補上產品規格依據。 |
| 升級為 trusted | 需重複 approved event 支撐，或 reviewer 明確確認。 |

## Generated Case 狀態

| 狀態 | 來源 | 後續 |
|---|---|---|
| `case_idea` | candidate knowledge、coverage hint、人工輸入 | 只作為 backlog，不進測試碼。 |
| `draft_case` | trusted knowledge 或 candidate + 人工確認 | 可產生草稿，但需 review。 |
| `review_ready_case` | 基於 trusted knowledge 且 evidence 完整 | 可進 code review。 |
| `approved_case` | reviewer approve | 可 merge。 |
| `rejected_case` | reviewer reject | 不 merge，保留原因。 |

## New Case Generator 必填輸入

| 輸入 | 說明 |
|---|---|
| Target Feature / Module | 要補 coverage 的產品功能。 |
| App Usage Knowledge | 操作流程與必要前置條件。 |
| Coverage Opportunity Knowledge | 為什麼需要新增 case。 |
| Test Identity Template | Stable Case ID、case name、feature/module、priority、blocking type。 |
| Existing Coverage Map | 避免生成重複 case。 |
| Test Fragility Knowledge | 避免已知不穩定寫法。 |
| Source References | knowledge id、report id、PR id 或人工需求來源。 |

## New Case Generator 輸出要求

| 輸出 | 說明 |
|---|---|
| Proposed Case Name | 新 case 名稱。 |
| Purpose | 此 case 補哪個 coverage gap。 |
| Source Knowledge | 使用哪些 trusted / candidate knowledge。 |
| Test Steps | 高層次操作步驟，不包含未確認的 assertion 放寬。 |
| Expected Result | 必須來自 trusted knowledge、產品規格或人工輸入。 |
| Risk Notes | 若引用 candidate knowledge，必須明確標註。 |
| Review Status | case_idea、draft_case、review_ready_case、approved_case、rejected_case。 |

## 自動拒絕條件

只要出現下列任一情境，new case generator 不可產生正式 case。

| 條件 | 結果 |
|---|---|
| 只依賴 raw event history | 只能產生 `case_idea`。 |
| 只依賴 candidate knowledge | 只能產生 `draft_case`，需人工 review。 |
| expected result 來自未審核 AI guess | 不可生成正式 case。 |
| 需要改 assertion 標準才成立 | 不可生成，轉人工討論。 |
| source 是 product bug suspected | 不可生成正常流程 case。 |
| source 是 network/server busy 或 generation fail | 不可生成產品 case，改進 metrics / trend。 |

## 與 Auto-Healing Knowledge 的關係

New Case Generator 使用 Auto-Healing 產物時，邏輯如下：

```text
Trusted App Usage Knowledge
  -> 可定義操作流程

Trusted Coverage Opportunity Knowledge
  -> 可定義新增 case 的理由

Trusted Test Fragility Knowledge
  -> 可改善 test 寫法穩定性

Candidate Knowledge
  -> 只能提出 draft / idea，必須人工 review

Event History / Rejected / Evidence Gap
  -> 不可作為正式生成依據
```

## 最終邊界

New Case Generator 可以幫忙把 trusted knowledge 轉成新的 test case，但不能取代產品規格確認，也不能把 auto-healing 的短期事件自動升級成測試意圖。
