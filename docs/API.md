# API 参考

ETF 份额数据分析平台后端 REST API 参考。

> **Base URL**：开发 `http://localhost:8000/api`；生产 `https://bedivere.space/api`
>
> 所有响应均为 JSON。错误时返回 `{"error": "<message>"}` 与 HTTP 4xx/5xx。
>
> 实现见 [`backend/app/routes/etf.py`](../backend/app/routes/etf.py) 与 [`backend/app/services/etf_service.py`](../backend/app/services/etf_service.py)。

## 目录

- [ETF 数据](#etf-数据)
  - [`GET /etf/list`](#get-etflist)
  - [`GET /etf/{sec_code}`](#get-etfsec_code)
  - [`GET /etf/{sec_code}/trend`](#get-etfsec_codetrend)
  - [`GET /etf/ranking`](#get-etfranking)
  - [`GET /etf/compare`](#get-etfcompare)
  - [`GET /etf/rising`](#get-etfrising)
  - [`GET /etf/securities`](#get-etfsecurities)
- [Holders](#holders)
  - [`GET /etf/{sec_code}/holders`](#get-etfsec_codeholders)
  - [`GET /etf/holders-by-type`](#get-etfholders-by-type)
- [Huijin](#huijin)
  - [`GET /etf/{sec_code}/huijin`](#get-etfsec_codehuijin)
- [System](#system)
  - [`GET /health`](#get-health)
  - [`GET /etf/stats/summary`](#get-etfstatssummary)
  - [`GET /etf/data-status`](#get-etfdata-status)

---

## ETF 数据

### `GET /etf/list`

分页获取 ETF 列表（按 `sec_code` 升序）。

**Query params**

| 名称 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `page` | int | 1 | 页码（≥ 1） |
| `per_page` | int | 20 | 每页条数（1-200） |

**Response 200**

```json
{
  "items": [
    {
      "sec_code": "510300",
      "sec_name": "沪深300ETF",
      "full_name": "沪深300ETF华泰柏瑞"
    }
  ],
  "total": 832,
  "page": 1,
  "per_page": 20
}
```

**Example**

```bash
curl http://localhost:8000/api/etf/list?page=1&per_page=20
```

---

### `GET /etf/{sec_code}`

获取单只 ETF 详情。

**Path params**

| 名称 | 说明 |
|------|------|
| `sec_code` | 6 位 ETF 代码 |

**Response 200**

```json
{
  "sec_code": "510300",
  "sec_name": "沪深300ETF",
  "full_name": "沪深300ETF华泰柏瑞",
  "list_date": "2012-05-28",
  "fund_manager": "华泰柏瑞基金"
}
```

**Response 400**

```json
{ "error": "ETF 510300 not found" }
```

**Example**

```bash
curl http://localhost:8000/api/etf/510300
```

---

### `GET /etf/{sec_code}/trend`

返回 ETF 最近 N 天的份额/价格序列（升序）。

**Path params**

| 名称 | 说明 |
|------|------|
| `sec_code` | 6 位 ETF 代码 |

**Query params**

| 名称 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `days` | int | 30 | 天数（> 0） |

**Response 200**

```json
[
  { "date": "2025-12-01", "tot_vol": 1234567.0, "close_price": 4.123 },
  { "date": "2025-12-02", "tot_vol": 1235000.0, "close_price": 4.135 }
]
```

字段说明：

- `tot_vol`：总份额（万份）
- `close_price`：收盘价（元）

---

### `GET /etf/ranking`

ETF 排行榜（按 `sec_code` 各自最新两期 `tot_vol` 计算变化）。

**Query params**

| 名称 | 类型 | 默认 | 可选值 |
|------|------|------|--------|
| `sort_by` | string | `tot_vol` | `tot_vol` / `change` / `pct` |
| `limit` | int | 10 | 1-200 |

**Response 200**

```json
[
  {
    "sec_code": "510300",
    "sec_name": "沪深300ETF",
    "etf_type": "stock",
    "tot_vol": 1234567.0,
    "stat_date": "2025-12-05",
    "change": 12000.0,
    "change_pct": 0.98
  }
]
```

字段说明：

- `change`：最新 tot_vol 与上一交易日 tot_vol 之差（万份）
- `change_pct`：百分比变化（%）

---

### `GET /etf/compare`

对比多只 ETF 的份额走势，返回 `code -> series` 字典。

**Query params**

| 名称 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `codes` | string | 必填 | 逗号分隔 ETF 代码 |
| `days` | int | 30 | 天数（> 0） |

**Response 200**

```json
{
  "510300": [
    { "date": "2025-12-01", "tot_vol": 1234567.0, "close_price": 4.123 }
  ],
  "510500": [
    { "date": "2025-12-01", "tot_vol": 567890.0, "close_price": 6.234 }
  ]
}
```

**Response 400**

```json
{ "error": "codes must not be empty" }
```

**Example**

```bash
curl 'http://localhost:8000/api/etf/compare?codes=510300,510500&days=30'
```

---

### `GET /etf/rising`

返回指定窗口内份额上升的 ETF 列表（按 `change_pct` 降序）。

**Query params**

| 名称 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `days` | int | 126 | 窗口天数（> 0） |

**Response 200**

```json
[
  {
    "sec_code": "512880",
    "sec_name": "证券ETF",
    "etf_type": "securities",
    "start_vol": 800000.0,
    "latest_vol": 950000.0,
    "change_pct": 18.75,
    "start_date": "2025-08-01",
    "end_date": "2025-12-05"
  }
]
```

---

### `GET /etf/securities`

证券/保险 ETF 专项排行。`full_name` 含"证券"或"保险"的 ETF。

**Query params**

| 名称 | 类型 | 默认 | 可选值 |
|------|------|------|--------|
| `sort_by` | string | `volume` | `volume` / `change` / `pct` |

**Response 200**

```json
[
  {
    "sec_code": "512880",
    "sec_name": "证券ETF",
    "full_name": "证券ETF国泰",
    "tot_vol": 950000.0,
    "stat_date": "2025-12-05",
    "change": 12000.0,
    "change_pct": 1.28
  }
]
```

> 内部实现通过 `etf_type='securities'` 过滤 `etf_info` 表，仅返回基础 ETF。
> 对深市/沪市"证券ETF"同主题多只的并集由前端在 `/securities` 页面聚合展示。

---

## Holders

### `GET /etf/{sec_code}/holders`

获取单只 ETF 最新的十大持有人。

**Path params**

| 名称 | 说明 |
|------|------|
| `sec_code` | 6 位 ETF 代码 |

**Response 200**

```json
{
  "sec_code": "510300",
  "holders": [
    {
      "holder_name": "中央汇金资产管理有限责任公司",
      "hold_volume": 123456789.0,
      "hold_ratio": 12.34
    }
  ],
  "stat_date": "2025-09-30"
}
```

> 实际接口从数据库读取，限制返回前 10 名。无数据时返回：
> ```json
> { "sec_code": "510300", "holders": [], "stat_date": null }
> ```

---

### `GET /etf/holders-by-type`

按持有人关键字（如"汇金"、"保险"、"信托"）查询所有 ETF 的最新一期持仓。

**Query params**

| 名称 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `type` | string | `""` | 持有人名称模糊匹配关键字 |
| `min_pct` | float | 0.5 | 最小持仓占比（%），0-100 |

**Response 200**

```json
[
  {
    "sec_code": "510300",
    "full_name": "沪深300ETF华泰柏瑞",
    "sec_name": "沪深300ETF",
    "holder_name": "中央汇金资产管理有限责任公司",
    "hold_ratio": 12.34,
    "stat_date": "2025-09-30"
  }
]
```

**Example**

```bash
curl 'http://localhost:8000/api/etf/holders-by-type?type=%E6%B1%87%E9%87%91&min_pct=1.0'
```

---

## Huijin

### `GET /etf/{sec_code}/huijin`

中央汇金持仓分析。

**Path params**

| 名称 | 说明 |
|------|------|
| `sec_code` | 6 位 ETF 代码 |

**Query params**

| 名称 | 类型 | 默认 | 可选值 |
|------|------|------|--------|
| `mode` | string | `estimated` | `estimated` / `actual` |

- `estimated`（默认）：用最近两期 `tot_vol` 的比例系数，把最新一期 `etf_top_holders` 里的汇金持仓缩放到当前日期（disclaimer 说明此为估算）
- `actual`：取最近两期 `etf_top_holders` 的汇金实际持仓做差（精度更高，需要 2 期数据）

**Response 200（estimated）**

```json
{
  "sec_code": "510330",
  "sec_name": "沪深300ETF华夏",
  "mode": "estimated",
  "holders": [
    {
      "holder_name": "中央汇金资产管理有限责任公司",
      "hold_ratio": 12.34,
      "reported_volume": 100000000.0,
      "estimated_volume": 105000000.0
    }
  ],
  "dec31_holdings": 100000000.0,
  "latest_holdings": 105000000.0,
  "change": 5000000.0,
  "change_pct": 5.0,
  "disclaimer": "Estimated based on latest known holdings and total share changes"
}
```

**Response 200（actual）**

```json
{
  "sec_code": "510330",
  "sec_name": "沪深300ETF华夏",
  "mode": "actual",
  "holders": [],
  "dec31_holdings": 100000000.0,
  "latest_holdings": 108000000.0,
  "change": 8000000.0,
  "change_pct": 8.0
}
```

---

## System

### `GET /health`

健康检查。挂载在 `/api/health`（不属于 `/api/etf` 命名空间）。

**Response 200**

```json
{ "status": "ok", "service": "ETF Dashboard API" }
```

**Example**

```bash
curl http://localhost:8000/api/health
```

---

### `GET /etf/stats/summary`

Dashboard 顶部聚合数据。

**Response 200**

```json
{
  "total_etfs": 832,
  "total_records": 332184,
  "latest_date": "2025-12-05",
  "prev_date": "2025-12-04",
  "total_market_cap": 12345678.9,
  "total_market_cap_change": 12345.6,
  "market_change_pct": 0.1,
  "data_freshness_hours": 14.5
}
```

字段说明：

- `total_etfs`：`etf_info` 数量
- `total_records`：`etf_daily_share` 总行数
- `latest_date` / `prev_date`：最近两个交易日
- `total_market_cap`：所有 ETF 最新一日 `tot_vol` 之和（万份）
- `data_freshness_hours`：最新数据距现在的小时数

---

### `GET /etf/data-status`

数据完整性状态，用于 `/status` 页面。

**Response 200**

```json
{
  "latest_date": "2025-12-05",
  "daily_counts": [
    { "date": "2025-12-05", "count": 832, "status": "OK" },
    { "date": "2025-12-04", "count": 829, "status": "OK" }
  ]
}
```

字段说明：

- `daily_counts`：近 20 个交易日每日有数据的 ETF 数量；`status='OK'` 当 `count > 800`，否则 `LOW`
