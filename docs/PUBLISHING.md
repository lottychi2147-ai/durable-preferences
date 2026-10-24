# 發布到 GitHub

本文件是發布操作，不表示遠端已完成。

## 前置條件

在有 Git、GitHub CLI (`gh`) 且已登入你要發布之帳號的終端執行。
不把 token 貼進聊天、README 或腳本；使用 `gh auth login` 的正常登入流程。
原套件尚未指定 LICENSE，本次保留；發布前由維護者選定未來的開源／貢獻授權。

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
- 如既有庫有 LICENSE，停止，先使文件與既有授權一致，不能覆蓋或假稱未授權。
- 推送後讀回 README、SKILL.md、核心檔 Git blob SHA，再確認公開、Issues 與 Discussions 設定。
- 同名 RFC 已存在時不重複新增。
- 若部分步驟失敗，明確停止並保留隔離 checkout；不宣稱全部完成。

## 目前驗證狀態

本輪已驗證文件、manifest、程式語法、本地 dry-run 與寫入環境前置檢查。
目前執行環境沒有 `gh` 與 GitHub 寫入操作，因此**沒有真實推送，也沒有端到端驗證發布腳本的遠端分支**。

## 官方 CLI 參考

- https://cli.github.com/manual/gh_repo_create
- https://cli.github.com/manual/gh_repo_edit
- https://cli.github.com/manual/gh_issue_create
- https://cli.github.com/manual/gh_repo_view
