# 安裝、讀寫與資料遷移

## 安裝成 Skill

把完整 `durable-preferences` 目錄放到你的宿主會掃描的 skills 目錄；不是只複製 SKILL.md。
Agent Skills 規格定義套件內容，不保證所有官方聊天 App 都接受本地安裝。

例如，宿主確定支援 `.agents/skills` 後：

```bash
# macOS / Linux：先預覽，再自行明確套用
python scripts/install_skill.py --target "$HOME/.agents/skills"
python scripts/install_skill.py --target "$HOME/.agents/skills" --apply
```

```powershell
# Windows PowerShell
python scripts/install_skill.py --target "$HOME/.agents/skills"
python scripts/install_skill.py --target "$HOME/.agents/skills" --apply
```

需要 `.claude/skills` 的宿主，可以把 target 換成該路徑；以實際宿主設定為準。
安裝器不編輯平台設定、不自動開啟權限、不新增排程；若已存在同名套件會拒絕覆蓋。
本次只在隔離的暫存目錄驗證複製，不是替你在 ChatGPT 帳號或其他電腦安裝成功。

**初次設定必須由宿主綁定：**

```text
資料庫：技能資料夾之外的私人絕對路徑
owner_id：資料擁有者
subject_id：被描述的使用者／對象
namespace：personal 或特定專案，不能任意跨域共享
session_id：每次聊天不同
scope：core / food / casual / work 或宿主定義的其他領域
```

## 本地 CLI 例子

```bash
# 空庫可直接讀；不會虛構任何偏好
python scripts/memory.py --db ./private-demo/preferences.sqlite3 --owner demo --subject user-a compile --scopes food casual --session chat-001

# 偏好事件由 AI 依 SKILL.md 產生；內容放 JSON 檔，不拼進 shell
python scripts/memory.py --db ./private-demo/preferences.sqlite3 --owner demo --subject user-a observe --input ./assets/example-signal.json

# 新聊天仍讀同一庫
python scripts/memory.py --db ./private-demo/preferences.sqlite3 --owner demo --subject user-a compile --scopes food casual --session chat-002

# 同一份狀態的圖形版本
python scripts/memory.py --db ./private-demo/preferences.sqlite3 --owner demo --subject user-a atlas --scopes food core casual work --output ./private-demo/atlas.html
```

`example-signal.json` 是固定時間與固定 ID 的合成樣本，只能測試，不能用作真實來源。
正式資料請用主機提供的時間與穩定事件 ID，並把資料庫移到專案和 Git 追蹤之外。

## 舊版資料庫升級

核心 schema 已改為 2，請勿直接替換程式後繼續寫舊庫。

```bash
python scripts/migrate_v011.py --source /absolute/private/old.sqlite3 --output /absolute/private/new-v020.sqlite3
```

遷移前先暫停舊庫寫入；驗證輸出後，把宿主的 db 設定改到新檔再恢復寫入。原檔與舊技能包保留，可回滾，但回滾不會自動合併新庫新增的事件。
舊 JSON 快照可先用原 v0.1.1 的 `restore-empty` 還原到舊格式空庫，再執行上面升級。
被舊版過期清掉的季度好評不能從熟悉度猜回來；遷移後慢速證據有 `legacy_gap=true`。


## 接入不是自動完成

這份套件需要宿主提供本地腳本執行、私人持久儲存與每輪呼叫時機。
單純把 SKILL.md 貼進聊天，不等於資料已寫入；也不等於其他平台自動同步。
參見 [宿主接入規格](../references/host-integration.md)。
