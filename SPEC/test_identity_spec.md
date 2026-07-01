# Test Identity 規格

本文件定義 AI Auto-Healing 系統中的 Test Identity。Test Identity 是用來追蹤測試案例的穩定索引，不是用來保存完整執行細節。

## 核心原則

| 原則 | 說明 |
|---|---|
| Identity 要穩定 | 不應因 case name 微調、測試碼重構、page function chain 改變而失效 |
| Identity 要輕量 | 不存完整 calling page function chain，不存所有 locator |
| Identity 要能串資料 | 必須能串起上一輪狀態、failure evidence、healing record、HTML report、PR、knowledge |
| Identity 要讓人看得懂 | 除了 stable id，也要保留人類可讀的 case name、feature、priority |

## Test Identity v1 欄位

| 欄位 | 是否必填 | 來源 | 用途 |
|---|---|---|---|
| Stable Case ID | 必填 | Test Registry 分配 | 系統追蹤主 key，避免 case rename 後歷史斷掉 |
| Case Name | 必填 | 現有 test case name | 人類閱讀、report 顯示 |
| Test File Path | 必填 | 掃描測試程式碼 | AI patch / PR 定位 |
| Feature / Product Module | 必填 | 人工標註或從 case name 初步推斷 | coverage、report 分組、new case generator |
| Priority | 必填 | 人工標註 | device queue、immediate/deferred 決策、report 排序 |
| Blocking Type | 必填 | 人工標註 | 判斷是否會造成 downstream cascade |
| App Area / Screen | 建議 | 人工標註或由 failure evidence 補強 | AI 解讀截圖、找 baseline、coverage map |
| Primary Test Component | 建議 | 掃描測試碼或人工標註 | AI 找 page object / helper 的入口 |
| Related Test Components | 可選 | 掃描測試碼 | 協助 AI patch，但不作為 identity 主 key |
| Owner | 可選，初期可預設 | 人工標註 | report / PR review 分派 |
| Dependency Info | 第二階段補 | 人工標註或從執行記錄推斷 | 判斷 `blocked_by_upstream` |
| Fixture Profile | 視情況 | 人工標註 | 標示測試圖片、帳號、專案資料需求 |

## 欄位定義

### Stable Case ID

Stable Case ID 是系統用來追蹤同一個測試案例的穩定 ID。

建議格式：

```text
PHD-IOS-IMPORT-001
PHD-IOS-EDITOR-014
PHD-IOS-EXPORT-003
```

規則：

1. 建立後不要因 case name 改名而改變。
2. 不要直接使用 function name 當 stable id。
3. 若測試意圖被拆分或重寫，才建立新的 stable id。
4. 舊 stable id 的歷史資料應保留，避免 previous result lookup 斷掉。

### Feature / Product Module

Feature / Product Module 是產品功能分類，給人類、coverage、new case generator 使用。

例子：

| Feature / Product Module | 說明 |
|---|---|
| Import | 匯入圖片 |
| Editor | 編輯主流程 |
| Filter | 濾鏡 |
| Crop | 裁切 |
| Text | 文字工具 |
| Sticker | 貼紙 |
| Export | 匯出 |
| Permission | iOS 權限 |

不要把測試程式碼的 page function 或 helper 名稱填在這個欄位。

### App Area / Screen

App Area / Screen 是 UI 畫面位置，回答「測試或失敗大概發生在哪個畫面」。

例子：

| App Area / Screen | 說明 |
|---|---|
| Home | 首頁 |
| Import Picker | 匯入圖片選擇畫面 |
| iOS Permission Dialog | 系統權限彈窗 |
| Editor Canvas | 編輯畫布 |
| Tool Panel | 工具面板 |
| Export Settings | 匯出設定 |
| Export Progress | 匯出進度 |
| Export Result | 匯出結果 |

Feature 和 App Area / Screen 的差異：

| 問題 | 對應欄位 |
|---|---|
| 這個 case 測什麼功能？ | Feature / Product Module |
| 這個 case 或 failure 發生在哪個畫面？ | App Area / Screen |
| 測試碼使用哪個封裝？ | Primary Test Component |

### Primary Test Component

Primary Test Component 是測試程式碼層的主要 page object 或 helper。

例子：

| Primary Test Component | 說明 |
|---|---|
| ImportPage | 匯入流程 page object |
| EditorPage | 編輯畫布 page object |
| ToolPanel | 工具面板 helper |
| ExportPage | 匯出流程 page object |

此欄位只放摘要。完整 calling page function chain 不放在 Test Identity。

### Priority

Priority 是測試處理優先級，不是產品開發優先級。

| Priority | 意義 |
|---|---|
| P0 | App 基本可用能力，例如啟動、權限、匯入圖片、進入 editor |
| P1 | 核心使用流程，例如編輯、套效果、匯出 |
| P2 | 一般功能 |
| P3 | edge case 或低頻路徑 |

Priority 會影響：

1. device queue 排序
2. immediate / deferred 決策
3. HTML report 排序
4. failure impact 評估

### Blocking Type

Blocking Type 用來判斷這個 case 失敗後，是否會讓後續測試結果失真。

| Blocking Type | 定義 | 例子 |
|---|---|---|
| smoke | App 基本能力檢查 | App launch、進入首頁、載入測試圖片 |
| blocking | 後續多數 case 依賴它建立狀態 | 匯入圖片、建立編輯專案、授權相簿 |
| non-blocking | 單一功能失敗，不影響大部分後續 case | 某個濾鏡、某個工具按鈕、特定匯出設定 |

### Dependency Info

Dependency Info 用來描述 case 之間或 setup 之間的前置關係。

例子：

| Case | Dependency Info |
|---|---|
| Apply filter | depends on project created |
| Export image | depends on editor project ready |
| Save to album | depends on album permission granted |

初期可以先不完整填寫，但 blocking case 應優先補上。

## 不放進 Test Identity 的資料

| 資料 | 應放位置 | 原因 |
|---|---|---|
| 完整 page function calling chain | Runtime Execution Trace | 每次執行可能不同，且過於細節 |
| 所有 locator 清單 | Static Code Metadata / Locator Snapshot | locator 會變動，不適合作 identity |
| failure 當下使用的 locator | Failure Evidence | 只跟該次失敗事件有關 |
| AI 修改的 locator | Healing Record / Patch Evidence | 屬於修復紀錄 |
| 完整 log / trace / screenshot | Evidence Store | 體積大，不屬於 identity |

## 相關資料分層

| 層級 | 內容 | 產生時機 |
|---|---|---|
| Test Identity | 穩定索引與治理 metadata | pre-run |
| Static Code Metadata | 測試碼結構、page object、可用 locator registry | 掃描 code 時 |
| Runtime Execution Trace | 實際跑到哪些 function、哪些 locator、在哪一步 fail | 測試執行時 |
| Failure Evidence | 失敗當下畫面、log、network、accessibility tree | 測試失敗時 |
| Healing Record | AI 分析、修補、replay、review | fail handling 後 |
| Knowledge Item | review 後萃取的 app usage / test fragility / coverage opportunity | post-review |

## Bootstrap 流程

目前已有 case name，但沒有 stable case id。第一版建議這樣建立：

```text
掃描現有 test files
      |
      v
取得 case name 與 test file path
      |
      v
依 feature / folder / case name 初步分組
      |
      v
產生 Stable Case ID
      |
      v
人工補 Feature、Priority、Blocking Type、App Area / Screen
      |
      v
形成 Test Registry
```

## 第一版最小欄位

第一版至少完成以下欄位：

| 欄位 | 取得方式 |
|---|---|
| Stable Case ID | 系統產生，人工確認 |
| Case Name | 自動掃描 |
| Test File Path | 自動掃描 |
| Feature / Product Module | 人工標註或半自動推斷 |
| Priority | 人工標註 |
| Blocking Type | 人工標註 |
| App Area / Screen | 人工標註 |
| Primary Test Component | 可先人工標註，之後由 code scanner 補強 |

## 待討論

1. Stable Case ID 的命名規則是否採 `PHD-IOS-{FEATURE}-{NUMBER}`。
2. Feature / Product Module 的固定選項清單。
3. App Area / Screen 的固定選項清單。
4. Priority 的初始標準。
5. Blocking Type 的初始標準與誰負責標註。
