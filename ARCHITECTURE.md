# ETF 份额数据分析平台 - 架构设计文档

> 本文档描述**当前实现**的架构，与代码保持同步。修改代码时请同步更新本文档。

## 1. 项目概述

### 1.1 项目背景
上海证券交易所 ETF 份额历史数据采集与分析平台，提供数据可视化展示和对比分析功能。

### 1.2 项目地址
- 域名: bedivere.space
- 服务器: 45.145.228.58

### 1.3 数据规模
| 指标 | 数值 |
|------|------|
| 总记录数 | 332,184 条 |
| 日增量 | ~300-500 条 |
| 数据大小 | 40MB |

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户浏览器                            │
│                     https://bedivere.space                  │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTPS (Let's Encrypt)
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                         Nginx                               │
│                    (443 / 80 → 443)                        │
│  ┌─────────────────┐    ┌────────────────────────────────┐ │
│  │  静态资源服务    │    │     Flask API 反向代理          │ │
│  │  /              │    │     /api/*                      │ │
│  └─────────────────┘    └────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────┘
                             │
              ┌───────────────┴───────────────┐
              ↓                               ↓
┌─────────────────────────┐     ┌─────────────────────────────┐
│      React 前端          │     │       Flask API            │
│   (Vite 构建产物)        │     │   (Gunicorn 端口: 8000)     │
│   构建时注入 VITE_API_BASE     └─────────────┬───────────────┘
└─────────────────────────┘                   │
                                              ↓
                              ┌─────────────────────────────┐
                              │       PostgreSQL            │
                              │       (端口: 5432)           │
                              └─────────────────────────────┘
```

---

## 3. 技术选型（当前实际）

| 组件 | 技术选型 | 版本 | 说明 |
|------|----------|------|------|
| 前端框架 | React + Vite + TypeScript | 19 / 8 / 6 | 快速构建，热更新 |
| 数据获取 | @tanstack/react-query | 5 | 服务端状态、缓存、自动重试 |
| 图表 | recharts | 3 | 趋势图、对比图 |
| 图标 | lucide-react | 1 | UI 图标 |
| 后端框架 | Flask | 3.x | 轻量，Python 生态 |
| ORM | SQLAlchemy + Flask-SQLAlchemy | 2.0 / 3.1 | 数据模型 |
| 数据库 | PostgreSQL | 16 | 主数据存储 |
| 配置层 | python-dotenv | 1.0 | env 驱动配置（`app/config.py`） |
| WSGI 服务器 | Gunicorn | 23 | 生产级 |
| Web 服务器 | Nginx | apt | 反向代理 + 静态资源 |
| HTTPS | Let's Encrypt (certbot) | | 免费自动续期 |
| 数据采集 | Python requests + beautifulsoup4 | | 上交所/深交所/新浪接口；Phase 2 cron 化 |

---

## 4. 功能模块划分

### 4.1 前端模块（实际）

```
frontend/src/
├── pages/
│   ├── Dashboard/         # 首页 / 概览（最新数据时间、TOP 10）
│   ├── Ranking/           # 排行榜
│   ├── Trend/             # 单只 ETF 趋势图（路由 /trend/:code）
│   ├── Compare/           # ETF 对比分析
│   ├── Holders/           # 单只 ETF 十大持有人（路由 /holders/:code）
│   ├── HoldersByType/     # 按持有人类型查询（/holders-by-type）
│   ├── Securities/        # 证券/保险 ETF 专项（/securities）
│   ├── Huijin/            # 汇金系估算（/huijin/:code）
│   └── Status/            # 数据完整性状态（/status）
├── components/
│   ├── layout/
│   │   └── Layout.tsx     # 侧边栏 + 路由出口
│   ├── charts/            # 图表封装（trend / compare / bar 等）
│   └── ui/                # 基础 UI 原子组件
├── services/
│   └── api.ts             # API 调用层（封装 fetch + VITE_API_BASE）
├── stores/                # zustand 状态
├── hooks/                 # 自定义 hooks
├── App.tsx                # 路由配置
└── main.tsx               # React 入口
```

**当前页面**：

| 页面 | 路由 | 功能描述 |
|------|------|----------|
| 首页 | `/` | 监控 ETF 数 + TOP 10 份额排行（聚合数据来自 `/stats/summary` + `/ranking`） |
| 排行榜 | `/ranking` | 份额排行（`sort_by` 支持 `tot_vol` / `change` / `pct`） |
| 趋势 | `/trend/:code` | 单只 ETF 份额历史走势 |
| 对比 | `/compare` | 多只 ETF 走势对比 |
| 持有人 | `/holders/:code` | 单只 ETF 最新一期十大持有人 |
| 持有人查询 | `/holders-by-type` | 按持有人类型（汇金 / 保险 / 信托 等）查询 |
| 证券 ETF | `/securities` | 证券/保险主题 ETF 专项排行 |
| 汇金估算 | `/huijin/:code` | 中央汇金持仓估算 / 实际差值 |
| 数据状态 | `/status` | 数据完整性监控 |

### 4.2 后端模块（实际）

```
backend/
├── app/
│   ├── __init__.py        # Flask 应用工厂
│   ├── config.py          # Config 类（env-driven）
│   ├── models.py          # ETFInfo / ETFDailyShare / ETFTopHolder
│   ├── services/
│   │   └── etf_service.py # 业务服务层（不依赖 Flask）
│   ├── utils/             # 工具模块
│   └── routes/
│       ├── etf.py         # /api/etf/* （全部业务端点）
│       └── health.py      # /api/health
└── scripts/
    ├── init_db.py         # 建表
    ├── migrate_data.py    # 一次性 SQLite → PostgreSQL 迁移
    ├── migrate_holders.py # 持有人数据补迁移
    └── fetch_sse.py       # 手动 SSE 拉取（cron 未启用时备用）
```

**API 设计**（当前状态：见 [docs/API.md](docs/API.md) 详细字段说明）：

| 方法 | 路由 | 描述 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/etf/list` | ETF 列表（分页） |
| GET | `/api/etf/<sec_code>` | 单只 ETF 详情 |
| GET | `/api/etf/<sec_code>/trend` | 份额趋势 |
| GET | `/api/etf/ranking` | 排行榜（`sort_by`: `tot_vol` / `change` / `pct`） |
| GET | `/api/etf/compare` | 多只对比 |
| GET | `/api/etf/rising` | 份额上升的 ETF |
| GET | `/api/etf/securities` | 证券/保险 ETF 专项 |
| GET | `/api/etf/code/holders/<code>` | 单只持有人 |
| GET | `/api/etf/holders-by-type` | 按持有人类型查询 |
| GET | `/api/etf/code/huijin/<code>` | 汇金系估算（`mode`: `estimated` / `actual`） |
| GET | `/api/etf/stats/summary` | Dashboard 聚合数据 |
| GET | `/api/etf/data-status` | 数据完整性 |

---

## 5. 数据库设计

### 5.1 PostgreSQL 表结构

```sql
-- ETF 基本信息表
CREATE TABLE etf_info (
    sec_code VARCHAR(20) PRIMARY KEY,  -- 证券代码
    sec_name VARCHAR(100),            -- ETF 简称
    full_name VARCHAR(200),            -- ETF 全称
    etf_type VARCHAR(50),              -- ETF 类型（股票/债券/商品/跨境/...）
    list_date DATE,                    -- 上市日期
    fund_manager VARCHAR(100),         -- 基金管理人
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ETF 日度份额数据表
CREATE TABLE etf_daily_share (
    id SERIAL PRIMARY KEY,
    sec_code VARCHAR(20) NOT NULL REFERENCES etf_info(sec_code),
    stat_date DATE NOT NULL,
    tot_vol REAL,                      -- 总份额（万份）
    num INTEGER,                        -- 持有人数
    close_price REAL,                  -- 收盘价
    market VARCHAR(10) DEFAULT 'SH',   -- 市场 (SH/SZ)
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(sec_code, stat_date)
);

-- 索引
CREATE INDEX idx_etf_daily_share_sec_code ON etf_daily_share(sec_code);
CREATE INDEX idx_etf_daily_share_stat_date ON etf_daily_share(stat_date);

-- ETF 十大持有人表（Phase 1 启用数据迁移）
CREATE TABLE etf_top_holders (
    id SERIAL PRIMARY KEY,
    sec_code VARCHAR(20) NOT NULL REFERENCES etf_info(sec_code),
    holder_name VARCHAR(200),
    hold_volume REAL,
    hold_ratio REAL,
    stat_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 5.2 数据迁移

旧 SQLite `data/etf_data.db` → PostgreSQL，使用 [backend/scripts/migrate_data.py](backend/scripts/migrate_data.py)。
- `etf_info` 和 `etf_daily_share` 是基础数据
- `etf_top_holders` 由 [backend/scripts/migrate_holders.py](backend/scripts/migrate_holders.py) 补迁移

---

## 6. 部署方案

详见 [DEPLOY.md](DEPLOY.md)。

要点：
- 服务器：Ubuntu Linux 5.15.0, 7.8GB RAM, 88GB disk
- 后端：Gunicorn 2 worker，端口 8000
- 前端：Vite 构建后由 Nginx 服务
- HTTPS：Let's Encrypt 自动续期
- CI：GitHub Actions（self-hosted runner）→ main 分支推送触发

### 6.1 环境变量（生产）

```env
DATABASE_URL=postgresql://etf_user:CHANGE_ME@localhost:5432/etf_db
SECRET_KEY=<random-string>
VITE_API_BASE=https://bedivere.space/api   # CI 注入
```

---

## 7. 设计风格

实际采用 **深色科技风格**（dark tech UI）——最近 commit `cff44e8` 明确切换。

主色：青蓝色 `#00D4FF`（强调色）、深色背景 `#1a1a2e`（卡片）、深灰 `#8892b0`（辅助文字）。
辅助色：紫 `#7B2CBF`、绿 `#34C759`、橙 `#FF9500`、红 `#FF3B30`（状态指示）。

历史方案（"苹果风格" 蓝色 + 浅灰背景）已废弃，仅作为未来可参考的风格之一。

---

## 8. 已确认决策

| 决策点 | 选择 |
|---|---|
| 项目定位 | 公开访问 + 投研分析 |
| API 鉴权 | 无认证（公开） |
| 数据采集方式 | cron 定时（Phase 2 已完成） |
| 汇金系分析 | 保留 + 加免责声明；同时用最近 2 个报告期实际数据做差作为更准的展示 |
| 旧 SQLite | 保留不删（仅作归档） |
| 旧 CLI / scripts | Phase 4 退役（已删除） |

---

## 9. 开发路线图

- **Phase 0（已完成）**：地基清理、配置抽象、文档对齐
- **Phase 1（已完成）**：补齐核心 API（ranking/holders/securities/huijin/stats/data-status）
- **Phase 2（已完成）**：数据采集 cron 化
- **Phase 3（已完成）**：前端新页面（Holders / HoldersByType / Securities / Huijin / Status）
- **Phase 4（已完成）**：退役 `src/etf/` 和 `scripts/`，归档旧文档，补充 [docs/API.md](docs/API.md) 与 [docs/DATASHEET.md](docs/DATASHEET.md)
