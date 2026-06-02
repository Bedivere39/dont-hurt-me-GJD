# 数据库 Schema

ETF 份额数据分析平台 PostgreSQL 数据库说明。

> **驱动**：SQLAlchemy 2.0（Flask-SQLAlchemy 3.1）
> **生产数据库**：PostgreSQL 16
> **本地默认**：`postgresql://etf_user:EtfPass2026!@localhost:5432/etf_db`（由 `DATABASE_URL` 注入）
> **模型定义**：[`backend/app/models.py`](../backend/app/models.py)
> **建表**：`python backend/scripts/init_db.py`

## 目录

- [总览](#总览)
- [etf_info](#etf_info)
- [etf_daily_share](#etf_daily_share)
- [etf_top_holders](#etf_top_holders)
- [关系图](#关系图)
- [索引与约束](#索引与约束)
- [常用查询模式](#常用查询模式)
- [数据规模与保留策略](#数据规模与保留策略)

---

## 总览

| 表 | 用途 | 写入频率 | 大致行数 |
|----|------|----------|----------|
| `etf_info` | ETF 基本信息（静态） | 增量（新 ETF 上市/老 ETF 退市） | ~800 行 |
| `etf_daily_share` | 每日份额、价格 | 每日 1 次/ETF | ~30 万行/年 |
| `etf_top_holders` | 十大持有人 | 报告期（每 ETF 年报/中报/年报） | 1-2 万行/年 |

---

## etf_info

ETF 基本信息表。每个 ETF 一行，主键 `sec_code`。

| 字段 | 类型 | NULL | 默认 | 说明 |
|------|------|------|------|------|
| `sec_code` | `VARCHAR(20)` | NO | — | **PK**。6 位证券代码（`510xxx`/`511xxx` 沪市；`159xxx` 深市） |
| `sec_name` | `VARCHAR(100)` | YES | — | ETF 简称（如"证券ETF"） |
| `full_name` | `VARCHAR(200)` | YES | — | ETF 全称（含管理人，如"证券ETF国泰"） |
| `etf_type` | `VARCHAR(50)` | YES | — | ETF 分类（`stock` / `bond` / `commodity` / `cross-border` / `securities` 等；`securities` 用于"证券/保险"专项） |
| `list_date` | `DATE` | YES | — | 上市日期 |
| `fund_manager` | `VARCHAR(100)` | YES | — | 基金管理人 |
| `created_at` | `TIMESTAMP` | NO | `NOW()` | 记录创建时间（UTC） |
| `updated_at` | `TIMESTAMP` | NO | `NOW()` | 最近更新时间（UTC，`onupdate` 自动维护） |

**业务说明**

- `sec_code` 是 6 位字符串，确保与交易所代码保持原样（带前导 0）。
- `etf_type` 由 Phase 0 引入，用于 `etf_securities` 路由过滤"证券/保险"主题。
- 同一只 ETF 在不同管理人下有独立代码（`full_name` 不同），行不合并。

---

## etf_daily_share

ETF 每日份额/价格数据。每个 (sec_code, stat_date) 一行。

| 字段 | 类型 | NULL | 默认 | 说明 |
|------|------|------|------|------|
| `id` | `INTEGER`（SERIAL） | NO | auto | **PK** |
| `sec_code` | `VARCHAR(20)` | NO | — | **FK → etf_info.sec_code** |
| `stat_date` | `DATE` | NO | — | 统计日期（交易日，**不是**自然日） |
| `tot_vol` | `REAL` | YES | — | 总份额（**万份**） |
| `num` | `INTEGER` | YES | — | 持有人数 |
| `close_price` | `REAL` | YES | — | 收盘价（元） |
| `market` | `VARCHAR(10)` | NO | `'SH'` | 市场：`SH`（沪市）/ `SZ`（深市） |
| `created_at` | `TIMESTAMP` | NO | `NOW()` | 入库时间（UTC） |

**业务说明**

- `tot_vol` 单位是**万份**。如 `1234567.0` 代表约 12.34 亿份。
- 数据更新时机：A 股清算完成后，约**晚上 8-10 点**。
- 交易日不连续（周末、节假日无行），不要用 `DATEDIFF` 计算行数。
- `num`（持有人数）来自上交所/深交所，间隔一段时间才更新一次。

---

## etf_top_holders

ETF 十大持有人表。报告期粒度（按 `stat_date` 一期一组）。

| 字段 | 类型 | NULL | 默认 | 说明 |
|------|------|------|------|------|
| `id` | `INTEGER`（SERIAL） | NO | auto | **PK** |
| `sec_code` | `VARCHAR(20)` | NO | — | **FK → etf_info.sec_code** |
| `holder_name` | `VARCHAR(200)` | YES | — | 持有人名称（如"中央汇金资产管理有限责任公司"） |
| `hold_volume` | `REAL` | YES | — | 持有份额（份，非万份） |
| `hold_ratio` | `REAL` | YES | — | 占总份额比例（**%**） |
| `stat_date` | `DATE` | YES | — | 报告期（年报/中报/年报的截止日） |
| `created_at` | `TIMESTAMP` | NO | `NOW()` | 入库时间（UTC） |

**业务说明**

- 报告期滞后：持有人数据通常滞后约 4-5 个月才公开。
- 一只 ETF 一个报告期通常有 10 个持有人，但本表不限 10 条历史期。
- 关键字"汇金"用于汇金系专项分析（`/etf/code/huijin/{code}` 接口）。

---

## 关系图

```
┌──────────────────┐
│   etf_info       │
│  (PK sec_code)   │
└────────┬─────────┘
         │ 1
         │
         │ N
┌────────┴───────────┐         ┌─────────────────────┐
│ etf_daily_share    │         │  etf_top_holders    │
│ (sec_code,         │         │  (sec_code,         │
│  stat_date) UNIQUE │         │   holder_name,      │
│                    │         │   stat_date)        │
└────────────────────┘         └─────────────────────┘
        N:1                              N:1
        └──────────► etf_info ◄──────────┘
```

- `etf_daily_share.sec_code` → `etf_info.sec_code`（外键）
- `etf_top_holders.sec_code` → `etf_info.sec_code`（外键）
- 删除 `etf_info` 行会因外键失败（除非先删除子表）—— 默认不级联删除。

---

## 索引与约束

### 主键

| 表 | PK |
|----|----|
| `etf_info` | `sec_code` |
| `etf_daily_share` | `id` |
| `etf_top_holders` | `id` |

### 唯一约束

| 表 | 约束 | 列 |
|----|------|-----|
| `etf_daily_share` | `uqc_sec_code_stat_date` | (`sec_code`, `stat_date`) |

### 索引

| 索引名 | 表 | 列 | 用途 |
|--------|----|----|------|
| `idx_etf_daily_share_sec_code` | `etf_daily_share` | `sec_code` | 单只趋势查询 |
| `idx_etf_daily_share_stat_date` | `etf_daily_share` | `stat_date` | 排行榜最新交易日 |

> 提示：排行榜接口大量使用 `func.max(stat_date)` + `GROUP BY sec_code`，`idx_etf_daily_share_sec_code` 是关键。如发现慢查询，考虑在该表上增加 `CREATE INDEX ... ON etf_daily_share (sec_code, stat_date DESC)` 复合索引（待性能验证后再加）。

---

## 常用查询模式

### 最新交易日

```sql
SELECT MAX(stat_date) FROM etf_daily_share;
```

### 排行榜（按份额）

```sql
SELECT d.sec_code, i.sec_name, d.tot_vol, d.stat_date
FROM etf_daily_share d
JOIN etf_info i ON i.sec_code = d.sec_code
WHERE d.stat_date = (SELECT MAX(stat_date) FROM etf_daily_share)
ORDER BY d.tot_vol DESC
LIMIT 10;
```

### 单只持有人

```sql
SELECT holder_name, hold_volume, hold_ratio, stat_date
FROM etf_top_holders
WHERE sec_code = :code
  AND stat_date = (SELECT MAX(stat_date) FROM etf_top_holders WHERE sec_code = :code)
ORDER BY hold_ratio DESC
LIMIT 10;
```

### 汇金持仓

```sql
SELECT *
FROM etf_top_holders
WHERE sec_code = :code
  AND holder_name LIKE '%汇金%'
ORDER BY stat_date DESC;
```

---

## 数据规模与保留策略

- `etf_daily_share` 是最大表，年增长 ~25 万行（800 ETF × 250 交易日）。
- 当前规模约 33 万行（参考 [ARCHITECTURE.md §1.3](../ARCHITECTURE.md)）。
- 当前**不**做归档/分区；如未来单表 > 1 亿行建议按年分区。
- 旧 SQLite `data/etf_data.db` 已废弃，**保留不删**作为历史归档，新代码不应再读写。
