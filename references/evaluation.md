# v0.2.0 驗收範圍

- 單元／回歸 124/124。
- 獨立學習案例：同一腳本對照，v0.1.1 6/16 → v0.2.0 16/16。
- 十年量級：365,300 次實際 observe＋同數 compile；0 個檢查失敗。
- 額外 120,000 輪、12 個種子全部通過。
- 36,530 概念時本機 20 次暖快取 default compile P95 0.957 ms；舊版同機重跑 458.439 ms。
- 主負載資料庫 31.31 MiB，保留 731,218 筆完整去重憑證。
- 十年快照由新 Python 程序還原，307 個狀態與 packet 一致。
- 舊十年快照實際遷移，307 狀態與 731,214 憑證相同，原檔 SHA 不變。

## 不得省略的限制

50% 符號翻轉探索測試的 24 組仍有 4 組得到 |stable|>0.5，不是所有噪聲情況都處理好了。
沒有真實 LLM 分類、Skill 啟用或個人化回答的端到端評測。
快照可攜不等於所有模型會使用；十年是模擬時間，不是觀察十年。
exact receipts 仍線性成長；小於50MiB只針對本工作負載。
完整 get 仍列舉 scope；compile 的大量同步 overlay 是另一個尚待壓測的邊界。

## 重跑

```bash
python tests/run_all.py --unit-only
python tests/acceptance_v020.py --root . --out reports/acceptance-new.json
python tests/run_all.py --seeds 12 --steps 10000
python tests/decade_scale.py --root . --out reports/decade-new
python tests/density_bench.py --root . --out reports/density-new
python tests/noise_probe.py --output reports/noise.json
```

結果見 reports/repair-summary.json。原始第一次失敗與修正預期的說明一併保留。
