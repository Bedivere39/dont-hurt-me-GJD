---
name: etf
description: ETF 份额数据分析平台 - 通过 Web API 查询 ETF 份额、排名、持有人、汇金持仓等
user-invocable: true
---

# ETF 份额数据分析平台

基于上海证券交易所数据的 ETF 份额分析与展示平台（Web 版）。

> 在线访问: https://bedivere.space
>
> A 股清算后数据才更新，约晚上 8-10 点后才能查到当天数据。白天查到的"最新"实际是前一天的。

## 平台入口

| 入口 | 用途 |
|---|---|
| https://bedivere.space | Web 前端（公开访问） |
| https://bedivere.space/api/health | 后端健康检查 |
| https://bedivere.space/api/etf/* | REST API 端点（详见 [docs/API.md](../../docs/API.md)） |

## API 速查

所有端点前缀 `/api/etf`，返回 JSON。

| 端点 | 用途 |
|---|---|
| `GET /list?page=N&per_page=N` | ETF 列表（分页） |
| `GET /<sec_code>` | 单只 ETF 详情 |
| `GET /<sec_code>/trend?days=N` | 份额趋势 |
| `GET /ranking?sort_by=tot_vol\|change\|pct&limit=N` | 排行榜（按份额 / 变化 / 增幅） |
| `GET /compare?codes=512880,510300&days=N` | 多只对比 |
| `GET /rising?days=N` | 份额上升的 ETF |
| `GET /securities?sort_by=volume\|change\|pct` | 证券/保险 ETF 专项 |
| `GET /<sec_code>/holders` | 单只 ETF 十大持有人 |
| `GET /holders-by-type?type=汇金&min_pct=0.5` | 按持有人类型查询 |
| `GET /<sec_code>/huijin?mode=estimated\|actual` | 汇金系估算（`estimated` 含免责声明） |
| `GET /stats/summary` | Dashboard 聚合（总数、最新日期、市场变化） |
| `GET /data-status` | 数据完整性（最近 30 天每日记录数 + OK/LOW 状态） |

## 用 curl 查询示例

```bash
# 份额最大前 10
curl 'https://bedivere.space/api/etf/ranking?sort_by=tot_vol&limit=10'

# 512880 证券 ETF 趋势（最近 30 天）
curl 'https://bedivere.space/api/etf/512880/trend?days=30'

# 份额上升的 ETF（最近 126 天）
curl 'https://bedivere.space/api/etf/rising?days=126'

# 持有人中含"汇金"且占比 >= 0.5%
curl 'https://bedivere.space/api/etf/holders-by-type?type=%E6%B1%87%E9%87%91&min_pct=0.5'

# 510330 汇金估算（actual 模式：基于最近 2 期报告期真实数据）
curl 'https://bedivere.space/api/etf/510330/huijin?mode=actual'

# Dashboard 聚合数据
curl 'https://bedivere.space/api/etf/stats/summary'

# 数据完整性（最近 30 天）
curl 'https://bedivere.space/api/etf/data-status'
```

## 数据库字段

详见 [docs/DATASHEET.md](../../docs/DATASHEET.md)。简版：

- `etf_info` — ETF 基本信息（sec_code PK + sec_name + full_name + etf_type + list_date + fund_manager）
- `etf_daily_share` — 每日份额（sec_code + stat_date 联合唯一，tot_vol 单位万份）
- `etf_top_holders` — 十大持有人（sec_code + stat_date + holder_name + hold_volume + hold_ratio，滞后 4-5 月）

## 旧 CLI 工具

CLI 工具已退役，原命令归档在 [docs/legacy-cli.md](../../docs/legacy-cli.md)。新功能请走 Web API。

## 数据更新

计划由 cron 每天 21:00 触发 [backend/scripts/fetch_sse.py](../../backend/scripts/fetch_sse.py)，拉取 SSE 份额数据。
当前数据迁移详见 [backend/scripts/migrate_data.py](../../backend/scripts/migrate_data.py) 和 [backend/scripts/migrate_holders.py](../../backend/scripts/migrate_holders.py)。
