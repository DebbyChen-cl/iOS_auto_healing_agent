# PR Generation Rule 規格

本文件定義 AI Auto-Healing 產生 PR 的規則。此規格採用 run-level PR：一輪 AT run 最多產生一個 Auto-Healing PR，並對應一份 run-level HTML report。

## 核心決策

| 決策 | 規則 |
|---|---|
| PR 粒度 | 一輪 AT run 最多一個 Auto-Healing PR。 |
| Report 對應 | 一個 Auto-Healing PR 對應一份 run-level HTML report。 |
| Merge gate | PR 預設不可 merge，必須等 HTML report decision 為 `approve_merge_allowed`。 |
| 不合格 case | 不合格 case 可以出現在 HTML report，但 patch 不可放進 PR。 |

## PR 產生時機

PR 不在第一個 fail case 發生時立刻建立，而是在 full AT run 與 healing replay 完成後建立。

```text
Full AT run completed
  |
  v
Collect eligible healing patches
  |
  v
Exclude non-mergeable cases
  |
  v
Create one run-level Auto-Healing PR
  |
  v
Generate run-level HTML report
  |
  v
Reviewer checks HTML report
  |
  v
Only approve_merge_allowed can enable merge
```

## 可放進 PR 的 Patch

只有同時符合下列條件的 patch 可以放進 run-level Auto-Healing PR。

| 條件 | 說明 |
|---|---|
| 屬於同一輪 AT run | PR 的 scope 必須對齊單一 Run ID。 |
| L3 low-risk healing | 符合 L3 Healing Eligibility。 |
| Replay pass | 最終 replay 必須通過。 |
| Evidence 完整 | failure evidence、replay evidence、patch summary 足夠支援 HTML report approval。 |
| 沒有禁止修改 | 不可修改 assertion、expected value、comparison rule、test intent。 |
| 可被嚴格 approval checklist 審核 | HTML report 可以清楚呈現 failure、root cause、healing、replay、risk。 |

## 不可放進 PR 的 Case

下列 case 可以留在 HTML report 中，但 patch 不可放進 Auto-Healing PR。

| 情境 | 處理 |
|---|---|
| `need_more_evidence` | 不放進 PR，report 標註缺少哪些 evidence。 |
| `reject_healing` | 不放進 PR，保留原 failure 或重新分析。 |
| `manual_code_review_required` | 不放進 run-level auto-healing PR，改走人工 code review。 |
| Replay 未通過 | 不放進 PR。 |
| 需要修改 assertion / expected value | 不放進 PR，改標 `needs_new_test_case` 或 manual review。 |
| medium / high risk patch | 不放進 PR。 |
| product bug suspected | 不放進 PR。 |
| major workflow change | 不放進 PR，應走 new test case 或人工重構。 |

## 沒有 Eligible Patch 時

若一輪 AT run 中沒有任何 patch 符合 PR eligibility：

1. 不建立 Auto-Healing PR。
2. 仍產生 HTML report。
3. report 需列出 fail case、AI root cause、排除 PR 的原因。
4. final status 依各 case 原因標為 `manual_review_required`、`product_bug_suspected`、`need_more_evidence` 等。

## PR 狀態

| 狀態 | 意義 |
|---|---|
| Draft / merge blocked | PR 已建立，但尚未通過 HTML report approval。 |
| Waiting report approval | HTML report 已產生，等待 reviewer decision。 |
| Merge allowed | HTML report decision 是 `approve_merge_allowed`。 |
| Rejected | HTML report decision 是 `reject_healing`。 |
| Need more evidence | HTML report decision 是 `need_more_evidence`。 |
| Manual review required | HTML report decision 是 `manual_code_review_required`。 |

## PR Title

建議格式：

```text
[AI Healing] Run {run_id} - PHD iOS UI tests
```

範例：

```text
[AI Healing] Run 20260624-1530 - PHD iOS UI tests
```

## PR Body 必填資訊

| 欄位 | 內容 |
|---|---|
| Run ID | 對應哪一輪 AT run。 |
| Branch / Commit | 測試與 patch 對應的 branch / commit。 |
| Included Healing Cases | 哪些 case 的 patch 被放進 PR。 |
| Excluded Cases | 哪些 fail case 沒放進 PR，以及排除原因。 |
| Final Status Summary | pass、fail、pass_with_healing、manual review 等統計。 |
| Healing Summary | 每個 included case 的 root cause 與 healing strategy。 |
| Replay Summary | replay attempt count 與最終 replay 結果。 |
| Risk Flags | shared locator、locator override、dependency、flaky、evidence gap。 |
| HTML Report Link | reviewer 主審核入口。 |
| Merge Gate Status | waiting approval、approved、rejected、need more evidence。 |

## PR 與 HTML Report 的一致性

PR diff 必須與 HTML report 對得上。

| 檢查 | 規則 |
|---|---|
| Changed files | PR 中的 changed files 必須出現在 report patch summary。 |
| Included cases | PR 中的 patch 必須能對應到 report 的 included healing cases。 |
| Excluded cases | 有 fail 但未進 PR 的 case 必須在 report 中說明原因。 |
| Risk flags | report 中的 high-risk flag 不可被 PR body 隱藏。 |
| Merge gate status | PR body 的 merge gate status 必須與 report decision 一致。 |

## Merge Allowed 條件

Run-level Auto-Healing PR 只有在下列條件全部成立時才可 merge。

| 條件 | 說明 |
|---|---|
| HTML report decision 是 `approve_merge_allowed` | 嚴格 approval checklist 全部通過。 |
| PR 內所有 patch 都有 replay pass | 任一 included patch replay fail，都不可 merge。 |
| PR 內沒有禁止修改 | assertion、expected value、comparison rule、test intent 不可被修改。 |
| PR diff 與 report 一致 | reviewer 看到的 report 能完整解釋 PR diff。 |
| Excluded cases 已標註 | 沒放進 PR 的 failure 不能消失，必須留在 report。 |

## 設計理由

採用一輪 run 一個 PR，是因為目前預期 fail case 數量不多。這能讓 reviewer 用一份 HTML report 對應一個 PR，流程簡單、可追蹤，也符合「review report pass 後才 merge」的操作模式。
