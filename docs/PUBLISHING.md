# 發布到 GitHub

本文件是發布操作，不表示遠端已完成。

## 前置條件

在有 Git、GitHub CLI (`gh`) 且已登入你要發布之帳號的終端執行。
不把 token 貼進聊天、README 或腳本；使用 `gh auth login` 的正常登入流程。
維護者已於 2026-10-25 選定 MIT 授權；發布時須包含根目錄 LICENSE，並使 README、貢獻說明與清單保持一致。

```bash
# 本地預覽，不連網、不建立儲存庫
python tools/publish_github.py --repo YOUR_ACCOUNT/durable-preferences

# 建立新的公開儲存庫、推送清單中檔案、啟用討論並開 RFC issue
python tools/publish_github.py --repo YOUR_ACCOUNT/durable-preferences --apply

# 已有相同專案且本來就是公開時，明確允許更新
python tools/publish_github.py --repo YOUR_ACCOUNT/durable-preferences --apply --update-existing
```

## 保護措施

- 核對登入帳號與目標 owner，驗證 MANIFEST 檔案雜湊，先跑核心與學習測試。
- 僅上傳經檢查清單中的檔案，不用無差別的 `git add .`。
- 在獨立目錄 clone 後更新，不刪除其他檔案、不 force push、不繞過保護分支。
- 更新既有 `.gitignore` 時保留既有規則，並重算該檔清單雜湊。
- **拒絕自動把既有私人儲存庫改公開**，避免連同舊歷史曝光。這需要單獨審查。
- 如既有庫有授權檔，僅在根目錄 LICENSE 與待發布套件完全一致且沒有其他授權檔時繼續；不一致時停止，先由維護者協調，不能自動換授權。
- 推送後讀回 README、SKILL.md、核心檔 Git blob SHA，再確認公開、Issues 與 Discussions 設定。
- 同名 RFC 已存在時不重複新增。
- 若部分步驟失敗，明確停止並保留隔離 checkout；不宣稱全部完成。

## 目前驗證狀態

v0.2.0 已於 2026-10-24 實際上傳至 [公開儲存庫](https://github.com/lottychi2147-ai/durable-preferences)，並下載遠端版本驗證 62 個檔案雜湊。
當次使用已登入的 GitHub 網頁上傳；這不代表 `gh` 發布腳本的遠端流程已完成端到端驗證。
2026-10-25 的授權更新加入 MIT LICENSE，並重新計算發布清單。

## 官方 CLI 參考

- https://cli.github.com/manual/gh_repo_create
- https://cli.github.com/manual/gh_repo_edit
- https://cli.github.com/manual/gh_issue_create
- https://cli.github.com/manual/gh_repo_view
