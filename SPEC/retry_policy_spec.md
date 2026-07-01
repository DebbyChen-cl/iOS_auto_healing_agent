# Retry Policy 規格

本文件定義 AI Auto-Healing 系統中哪些 failure 可以 retry、最多 retry 幾次、retry 後如何標註，以及 retry 失敗後要進入哪個流程。

## 核心原則

| 原則 | 說明 |
|---|---|
| v1 所有 immediate retry 最多一次 | 避免唯一 iOS device 被重跑占用，造成整份 AT 時間失控 |
| Retry 不修改 code | 只重跑原始 case，不做 AI patch；修改 code 屬於 healing / replay |
| Retry pass 不是普通 pass | 必須標成 `pass_after_*`，保留品質訊號 |
| Retry fail 不無限重跑 | retry 後仍 fail，進入後續分類、auto-healing 或 manual path |
| Smoke / blocking retry fail 要進 auto-healing 環節 | 不直接結束，需再判斷是否可 healing 或是否為 product bug |

## Retry 類型

| 類型 | 是否 retry | 次數 | Retry pass 標註 | Retry fail 後續 |
|---|---:|---:|---|---|
| App crash | 可以 | 1 | `pass_after_app_crash_retry` | `app_crash`，不做 v1 auto recovery |
| Network issue | 可以 | 1 | `pass_after_network_retry` | `network_issue` |
| Server busy | 可以 | 1 | `pass_after_network_retry` | `server_busy` |
| Generation fail | 可以 | 1 | `pass_after_generation_retry` | `generation_fail`，再進 root cause / auto-healing 判斷 |
| Smoke case fail | 可以 | 1 | 依 retry 後結果標註，不可標普通 pass | 進 auto-healing 環節 |
| Blocking case fail | 可以 | 1 | 依 retry 後結果標註，不可標普通 pass | 進 auto-healing 環節 |
| Setup / fixture root failure | 可以 recovery 或 retry | 1 | `pass_after_data_recovery` | `fixture_recovery_required` |
| Flaky suspect | 可以 diagnostic retry | 1 | `pass_after_retry` | 保留原 failure type，並標記 flaky evidence 不足或仍失敗 |
| Locator / page object drift | 不在 main run retry | 0 | 不適用 | deferred healing |
| Compare fail | 不立即 retry | 0 | 不適用 | deferred analysis |
| Product bug suspected | 不 retry | 0 | 不適用 | `product_bug_suspected` |
| Assertion logic change required | 不 retry | 0 | 不適用 | `needs_new_test_case` |

## Generation Fail 定義

`generation_fail` 是指 App 或後端明確回傳「生成失敗」或「產生結果失敗」的業務狀態，與 network/server busy 分開。

| 類型 | 說明 |
|---|---|
| Network / server busy | request timeout、connection reset、HTTP 429 / 503 / 504、server busy |
| Generation fail | request 有完成，但生成任務回傳 failed、result unavailable、generation error、render/generate pipeline failed |

Generation fail 的處理原則：

1. v1 允許 retry 一次。
2. retry pass 時標 `pass_after_generation_retry`。
3. retry 仍 fail 時標 `generation_fail`，並交給 AI Root Cause / auto-healing 環節判斷。
4. 若 root cause 是 locator、wait、micro-flow，可進 deferred healing。
5. 若 root cause 是產品生成邏輯壞掉，標 `product_bug_suspected`。

## Smoke / Blocking Retry Fail 規則

Smoke case fail 或 blocking case fail 允許 immediate retry 一次。若 retry 後仍 fail，不直接結束，必須進入 auto-healing 環節。

```text
smoke / blocking fail
      |
      v
retry once
      |
      +-- pass
      |     -> pass_after_retry 或依具體原因標成 pass_after_*
      |
      +-- fail
            -> AI Root Cause Analysis
            -> Scheduling Decision
            -> deferred healing / product bug / manual review
```

說明：

1. 進入 auto-healing 環節不代表一定會 patch。
2. AI 仍需根據 failure taxonomy 判斷是否可 healing。
3. 若是 product bug、assertion logic change、major workflow change，仍不可 healing。
4. 若是 locator drift、readiness wait drift、micro-flow drift，才可進 healing queue。

## Retry Decision Flow

```text
failure occurs
   |
   v
is retry eligible?
   |
   +-- no
   |     -> no retry
   |
   +-- yes
         |
         v
has retry budget?
   |
   +-- no
   |     -> no retry
   |
   +-- yes
         |
         v
retry once without code change
   |
   +-- pass
   |     -> pass_after_*
   |
   +-- fail
         -> route by failure type
```

## Retry 結果寫入

每次 retry 都需要寫入：

| 資料 | 用途 |
|---|---|
| Retry Count | 確認 v1 沒有超過一次 |
| Retry Reason | 說明為什麼允許 retry |
| Retry Result | pass / fail / crash |
| Status After Retry | `pass_after_*` 或保留 failure type |
| Evidence Delta | retry 前後關鍵差異，供 report 使用 |

Retry 結果需要進 Previous Result History，用於後續判斷 flaky、network pattern、generation failure pattern。

## Final Status 建議

| 狀態 | 意義 |
|---|---|
| `pass_after_app_crash_retry` | App crash 後不改 code 重跑一次通過 |
| `pass_after_network_retry` | network/server busy 類重跑一次通過 |
| `pass_after_generation_retry` | generation fail 重跑一次後通過 |
| `pass_after_retry` | 不屬於上述明確類型，但 diagnostic retry 後通過 |
| `app_crash` | App crash 後重跑仍 crash / fail |
| `network_issue` | network issue 重跑仍失敗 |
| `server_busy` | server busy 重跑仍失敗 |
| `generation_fail` | generation fail 重跑仍失敗 |

## v1 實作規則

1. 所有 immediate retry 最多一次。
2. Retry 期間不可修改測試碼、locator、assertion、expected value。
3. Retry pass 不可標成普通 `pass`。
4. Smoke / blocking case retry fail 後，進 auto-healing 環節。
5. Generation fail 與 network/server busy 分開標註。
6. Retry 結果必須保存到 Previous Result History。

## 待討論

1. `pass_after_generation_retry` 是否要作為正式 final status。
2. `generation_fail` 是否需要細分成 app-side generation fail 與 backend generation fail。
3. Smoke / blocking retry fail 後，是否立即進 healing queue，或等 full AT run 後再 deferred。
