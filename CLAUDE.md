# ETF 份额数据分析平台

上海证券交易所 ETF 份额历史数据采集与分析平台（Web 版）。

> 公开访问的 ETF 数据展示 + 投研分析工具。生产地址: https://bedivere.space

## 项目结构

```
e:/dont_hurt_me_GJD/
├── backend/                 # Flask + SQLAlchemy + PostgreSQL
│   ├── app/
│   │   ├── __init__.py      # Flask 应用工厂
│   │   ├── config.py        # 配置层（env-driven）
│   │   ├── models.py        # ETFInfo / ETFDailyShare / ETFTopHolder
│   │   ├── services/
│   │   │   └── etf_service.py # 业务服务层
│   │   ├── utils/           # 工具模块
│   │   └── routes/
│   │       ├── etf.py       # /api/etf/*
│   │       └── health.py    # /api/health
│   ├── scripts/
│   │   ├── init_db.py       # 建表
│   │   ├── migrate_data.py  # 一次性 SQLite → PostgreSQL 迁移
│   │   ├── migrate_holders.py # 持有人数据补迁移
│   │   └── fetch_sse.py     # 手动 SSE 拉取
│   ├── .env.example
│   ├── requirements.txt
│   ├── run.py               # 开发入口
│   └── wsgi.py              # 生产入口
│
├── frontend/                # React + Vite + TypeScript
│   ├── src/
│   │   ├── App.tsx          # 路由
│   │   ├── components/
│   │   │   ├── layout/Layout.tsx
│   │   │   ├── charts/      # 图表封装
│   │   │   └── ui/          # 基础 UI 原子
│   │   ├── pages/
│   │   │   ├── Dashboard/   # 首页 / 概览
│   │   │   ├── Ranking/     # 排行榜
│   │   │   ├── Trend/       # 单只趋势图
│   │   │   ├── Compare/     # 对比分析
│   │   │   ├── Holders/     # 单只持有人
│   │   │   ├── HoldersByType/ # 按类型查询
│   │   │   ├── Securities/  # 证券 ETF 专项
│   │   │   ├── Huijin/      # 汇金系估算
│   │   │   └── Status/      # 数据状态
│   │   ├── services/
│   │   │   └── api.ts       # API 调用层
│   │   ├── stores/          # zustand 状态
│   │   └── hooks/           # 自定义 hooks
│   ├── .env.example
│   └── package.json
│
├── data/
│   └── etf_data.db          # 历史 SQLite（已废弃，保留不删）
│
├── docs/
│   ├── API.md               # REST API 参考
│   ├── DATASHEET.md         # 数据库 schema 说明
│   └── legacy-cli.md        # 旧 CLI 命令归档（历史参考）
│
├── ARCHITECTURE.md          # 架构设计文档
├── DEPLOY.md                # 部署文档
└── README.md
```

## 本地开发

### 后端

```bash
cd backend
cp .env.example .env           # 编辑 DATABASE_URL
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python scripts/init_db.py      # 建表
python run.py                  # 启动 :8000
```

### 前端

```bash
cd frontend
cp .env.example .env           # VITE_API_BASE
npm install
npm run dev                    # 启动 :5173
```

## 常用命令

```bash
# 后端生产启动
cd backend && source venv/bin/activate
gunicorn -w 2 -b 127.0.0.1:8000 'wsgi:app'

# 前端构建
cd frontend && npm run build

# 健康检查
curl https://bedivere.space/api/health
```

## 数据更新

**重要**：A股清算后数据才更新，约晚上 8-10 点后才能查到当天数据。

数据采集计划由 cron 触发（Phase 2 实现）。当前数据迁移详见 [backend/scripts/migrate_data.py](backend/scripts/migrate_data.py)。

## 数据库字段

### etf_info — ETF 基本信息
| 字段 | 类型 | 说明 |
|------|------|------|
| sec_code | TEXT | ETF 代码 (PK) |
| sec_name | TEXT | ETF 简称 |
| full_name | TEXT | ETF 全称（含公司） |
| etf_type | TEXT | ETF 类型 |
| list_date | DATE | 上市日期 |
| fund_manager | TEXT | 基金管理人 |

### etf_daily_share — 每日份额
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| sec_code | TEXT | ETF 代码 (FK → etf_info) |
| stat_date | DATE | 统计日期 |
| tot_vol | REAL | 总份额（万份） |
| num | INTEGER | 持有人数 |
| close_price | REAL | 收盘价 |
| market | TEXT | 市场（SH / SZ） |

### etf_top_holders — 十大持有人（在用）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| sec_code | TEXT | ETF 代码 (FK → etf_info) |
| holder_name | TEXT | 持有人名称 |
| hold_volume | REAL | 持有份额（份） |
| hold_ratio | REAL | 占总份额比（%） |
| stat_date | DATE | 报告期 |

> 报告期数据来自新浪财经基金档案页，约滞后 4-5 个月。持有人数据已迁移到 PostgreSQL（`backend/scripts/migrate_holders.py`），并在 `/holders/:code` / `/holders-by-type` / `/huijin/:code` 接口使用。

## 注意事项

- **数据来源**：[README.md](README.md) 标注了上交所 / 深交所 / 新浪财经接口
- **不要**修改 `data/etf_data.db`：已废弃但保留，本地交叉验证用
- **不要**引入未在 ARCHITECTURE.md 出现的依赖：先讨论再装
- 任何用户数据、API 改动前先看 [ARCHITECTURE.md](ARCHITECTURE.md)
