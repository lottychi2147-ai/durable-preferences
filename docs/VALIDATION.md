# 驗證證據與重現

## 來源分級

- **既有 v0.2.0 執行資料：**reports/repair-summary.json、acceptance-candidate.json、noise-probe.json。
- **公開整理本輪重跑：**reports/publication-check/unit-tests.json、acceptance.json。
- **提案：**IMAGE_MEMORY.md 中 B/C 路線與完整真實 AI 評測，未被現有分數驗證。

本次公開整理沒有改記憶演算法，也沒有再跑完整 365,300 輪。
核心 SHA-256 應為 `25449344c6889a9bc9d2b8969a8b059ace79cdbb9e128f29010e32aca82b817a`。

## 重跑

```bash
python tests/run_all.py --unit-only
python tests/acceptance_v020.py --root . --out reports/local-run/acceptance.json
python tests/run_all.py --seeds 12 --steps 10000
python tests/decade_scale.py --root . --out reports/local-run/decade
python tests/density_bench.py --root . --out reports/local-run/density
python tests/noise_probe.py --output reports/local-run/noise.json
```

將資料庫及大型輸出留在私人／暫存目錄，不提交至公共 Git。
`tests/migration_large.py` 及 `tests/verify_decade_snapshot.py` 需要相應的大型輸入，
可由 scale runner 生成；本公開來源包不隨附完整快照資料庫或所有大型舊版輸入。
舊版比較用的完整核心不在此包，baseline 結果為既有執行證據，不能在缺少舊版時宣稱已重現比較。

## 已保存數據

124/124 單元／回歸；指定學習案例 16/16；季度負評可將 +0.90 轉成 -0.9885。
既有主負載 365,300 observe + 365,300 compile，另有 120,000 輪。
指定本地暖快取 36,530 概念 compile P95 約 0.96 ms。
主資料庫約 31.31 MiB，731,218 去重憑證；仍隨事件成長。

## 明確限制

- 50% 符號翻轉探索的 24 組中，4 組得到過強偏好。未宣稱抗任意噪聲。
- 分類標籤由測試宿主提供，不是測 LLM 自動辨識玩笑、反諷或指代。
- 沒有測 Skill 自動啟用或模型最後回答有沒有遵循 packet。
- 十年為模擬日曆及實際執行資料量，不是真實十年追蹤。
- 本地單寫模式，不是多裝置同步、正式登入授權或斷電耐久認證。
- hash checksum 可檢查損毀，不驗證外部來源真偽；資料庫不含內建磁碟加密。
- 完整 get 仍列舉 scope；大量並存 overlay 尚待壓測。
- 原文被清理後，只剩摘要的部分不能精確反向撤銷每個舊事件。

## 圖像路線的驗收原則

只有 atlas 能正常顯示，不能宣稱視覺模型會記得。
資料包一致，不能宣稱不同模型的行為一致。
縮圖更小，不能直接宣稱 token 更少。
須使用相同狀態、相同任務與明確預算，測模型的實際讀取與回答。
