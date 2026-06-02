# 旧 CLI 工具归档

> ⚠️ **此文档为历史 CLI 工具的命令参考**。CLI 工具已退役，所有功能已迁移到 Web 平台。
> 详见根目录 [README.md](../README.md) 和 [ARCHITECTURE.md](../ARCHITECTURE.md)。
>
> 保留此文档仅作历史参考，**不要在新功能中引用这些命令**。

---

## 历史背景

最初版本是单用户本地使用的 Python CLI 工具，SQLite 单文件存储。
2026 年改造成公开访问的 Web 平台：
- 旧 SQLite (`data/etf_data.db`) 一次性迁移到 PostgreSQL
- CLI 命令和 `scripts/` 下的独立分析脚本功能全部计划迁移到 Web
- Phase 0 完成配置层、文档、模型清理
- Phase 1-3 逐步补齐 Web 端缺失功能
- Phase 4 彻底删除 `src/etf/` 和 `scripts/`

---

## 旧 CLI 命令（已废弃）

```bash
# 数据采集
python -m src.etf.cli fetch 5
python -m src.etf.cli fetch_szse 500

# 数据查询
python -m src.etf.cli query 126         # 份额上升的 ETF
python -m src.etf.cli securities        # 证券/保险 ETF
python -m src.etf.cli top 10            # 份额增加最多
python -m src.etf.cli top_pct 10        # 份额增幅最多
python -m src.etf.cli trend 510330      # 单只趋势
python -m src.etf.cli check             # 数据完整性
python -m src.etf.cli update_names      # 更新 ETF 全称

# 十大持有人
python -m src.etf.cli holders                    # 采集全部
python -m src.etf.cli holders 512370             # 单只持有人
python -m src.etf.cli holders_type 汇金           # 按类型查询
```

## 旧独立脚本（已废弃）

```bash
python scripts/etf_trend.py 512880 500           # HTML 趋势图
python scripts/etf_compare.py 510300 500         # 对比
python scripts/huijin_etf.py 510330               # 汇金系估算
python scripts/huijin_analysis.py                 # 汇金系趋势
```

## 这些功能在 Web 端的对应

| 旧功能 | Web 端对应 | 状态 |
|---|---|---|
| `query` 份额上升 | /ranking?sort_by=change | ⏳ Phase 1 |
| `securities` | /securities 页面 | ⏳ Phase 3 |
| `top` 份额增加 | /ranking?sort_by=change | ⏳ Phase 1 |
| `top_pct` 份额增幅 | /ranking?sort_by=pct | ⏳ Phase 1 |
| `trend` 单只趋势 | /trend/:code | ✅ |
| `check` 数据完整性 | /status 页面 | ⏳ Phase 3 |
| `holders` 单只持有人 | /holders/:code | ⏳ Phase 3 |
| `holders_type` | /holders-by-type | ⏳ Phase 3 |
| `huijin_etf` | /huijin/:code | ⏳ Phase 3 |
| `etf_trend` HTML 图 | /trend/:code | ✅ |
| `etf_compare` | /compare | ✅ |

---

## 数据保留

`data/etf_data.db`（41MB SQLite 文件）已迁移完毕，**保留不删**作为历史归档。
新代码不应再访问此文件。
