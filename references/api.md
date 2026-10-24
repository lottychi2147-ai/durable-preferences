# 本地 CLI 介面

所有指令共同需要 `--db`（或環境變數 `PREFERENCE_MEMORY_DB`）、`--owner`、`--subject`。
可選 `--namespace personal`；共同參數放在子指令之前。
`--now` 只供模擬；正式部署省略，讓工具使用當前 UTC。

| 指令 | 參數 | 用途 |
|---|---|---|
| health | 無 | 檢查資料庫、政策與主體 revision |
| observe | `--input FILE`，預設 `-` 讀 stdin | 驗證並提交一個訊號 |
| get | `--scopes food casual`、`--session ID` | 回傳完整狀態，含未知與候選 |
| compile | 同 get，另 `--max-items 12 --max-chars 6000` | 產生限長 AI 偏好資料包；自動包含 core |
| forget | `--scope food --concept food:chicken-cutlet` | 刪除指定偏好與來源，建立刪除水位 |
| explain | 同 forget | 查看保留的結構化來源，沒有逐字對話 |
| prune-evidence | `--before ISO8601` | 刪掉到期訊號紀錄，保留累積底色 |
| export | `--output FILE` | 匯出單一主體快照 |
| restore-empty | `--input FILE` | 只還原到該身分的全空主體，不覆寫／merge |
| atlas | 同 get，另 `--output FILE.html` | 輸出數值對應的離線色圖 |

JSON 結果在 stdout；錯誤 JSON 在 stderr，exit code 2。測試失敗 exit code 1。
`--expected-revision N` 適用 observe / forget，避免較舊的呼叫蓋掉新的更正。
`max_chars` 是 Unicode 字元預算，不是 token 數，也不是 UTF-8 bytes。

## observe 回傳狀態

- applied：有效寫入。
- consolidated：跨日證據鞏固成新的長期傾向。
- same_day_not_reinforced：熟悉度等中繼資料更新，但沒有再增加該日候選權重。
- duplicate：相同 event/evidence 已處理，不再變更。
- ignored：來源模式不適用、時間過舊、刪除後未允許重學等，依 reason 判斷。

`compile` 不查詢 journal 或 receipts；只讀 states 和 subject revision。
不是零 I/O，也不是零上下文；只是避免重新檢索完整聊天。

## 目前限制

同一概念接受的 observed_at 必須嚴格遞增，來源時區必須明確。
大量離線資料需要先排序、正規化 ID，再獨立回放；不使用假的現在時間略過檢查。
沒有撤回單一已被鞏固／刪除來源之影響的無損重建功能；此時用明確更正或忘記概念。
雜湊去重收據會隨獨立事件增加，不是總儲存量固定；未實作無限容量。
JSON CLI 輸入上限 16 MB；更大資料需分批或使用受控 Python API。


## v0.1.1 新增
`compile(..., concept_ids=["food:chicken-cutlet"])` 或 CLI `compile --scopes food --concepts food:chicken-cutlet` 指定相關概念；不擴大 subject/namespace/scope 授權，未知項目不捏造。`restore-empty --max-snapshot-mib 256` 調整快照讀取預算；只處理可信的本地快照。


## v0.2.0 增補

- Memory 的 db 預期 schema 2/reducer 0.2.0。舊庫以 migrate_v011.py 複製升級。
- get/explain 狀態新增 long_evidence（群組、正負質量、未消費窗口、最後鞏固路徑、legacy_gap）。
- compile 維持介面，新增可選 uncertainty 欄位。狀態篩選改走投影索引，不從 journal 或 receipts 生成答案。
- Memory.last_compile_stats 是本地診斷資訊：解碼狀態數、總狀態數、可用狀態數；不等於模型 token 數。
- exact receipts 由文字轉完整二進位 SHA-256，不改 event_id/evidence_id 的外部契約。
