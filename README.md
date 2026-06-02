# ETF 份额数据分析平台

上海证券交易所 ETF 份额历史数据采集与分析平台（Web 版）。

> 在线访问: https://bedivere.space

## 功能特性

- **全市场 ETF 覆盖**：上交所 / 深交所 800+ 只 ETF 每日份额数据
- **首页概览**：监控 ETF 数、最新交易日、市场总份额变化、TOP 10 排行
- **多维度排行榜**：按份额绝对值、份额变化、份额增幅排序
- **历史趋势图**：单只 ETF 份额 / 收盘价走势可视化
- **多 ETF 对比**：同屏比较多只 ETF 走势
- **证券 ETF 专项**：证券/保险主题 ETF 专项排行（`/securities`）
- **十大持有人分析**：单只 ETF 持有人结构（`/holders/:code`）+ 按持有人类型查询（汇金 / 保险 / 信托 等，`/holders-by-type`）
- **汇金系估算**：基于总份额变化估算国家队持仓变化（`/huijin/:code`，`estimated` / `actual` 两种模式）
- **数据完整性监控**：检测每日数据更新状态（`/status`）

## 技术栈

| 组件 | 技术 | 说明 |
|---|---|---|
| 前端 | React 19 + Vite 8 + TypeScript | 单页应用 |
| 状态/数据 | @tanstack/react-query | 服务端状态管理 |
| 图表 | recharts | 趋势图、对比图 |
| 图标 | lucide-react | UI 图标 |
| 后端 | Flask 3 + SQLAlchemy 2 | REST API |
| 数据库 | PostgreSQL 16 | 主数据存储 |
| 部署 | Gunicorn + Nginx + Let's Encrypt | 反向代理 + HTTPS |
| 数据采集 | Python requests + beautifulsoup4 | 上交所/深交所/新浪接口 |

## 项目结构

```
.
├── backend/        # Flask 后端
│   ├── app/        # 应用代码（config / models / routes / services）
│   └── scripts/    # init_db / migrate_data / migrate_holders / fetch_sse
├── frontend/       # React + Vite + TypeScript
│   └── src/
│       ├── pages/      # Dashboard / Ranking / Trend / Compare / Holders / HoldersByType / Securities / Huijin / Status
│       ├── components/ # layout / charts / ui
│       └── services/   # api.ts
├── data/           # 历史数据（已废弃 SQLite，仅供归档）
├── docs/           # API.md / DATASHEET.md / legacy-cli.md
├── ARCHITECTURE.md # 架构设计
├── DEPLOY.md       # 部署指南
└── CLAUDE.md       # 给 AI 助手的项目说明
```

完整结构、字段定义见 [CLAUDE.md](CLAUDE.md)。

## 本地开发

### 环境要求
- Python 3.13+
- Node.js 20+
- PostgreSQL 14+（可选，本地可用 SQLite 替代 — 但生产为 PostgreSQL）

### 启动后端

```bash
cd backend
cp .env.example .env             # 填 DATABASE_URL
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py        # 建表
python run.py                    # 启动 :8000
```

### 启动前端

```bash
cd frontend
cp .env.example .env             # 配置 VITE_API_BASE
npm install
npm run dev                      # 启动 :5173
```

## 部署

详见 [DEPLOY.md](DEPLOY.md)。

简要流程：
1. 推送 main 分支触发 GitHub Actions
2. CI 自动构建前端、复制到服务器 `/opt/etf-dashboard/`
3. 重启 Gunicorn，Nginx 提供静态资源 + 反向代理

## 数据来源

| 来源 | 用途 | 更新频率 |
|---|---|---|
| 上海证券交易所 (SSE) | 份额、日行情 | 每日 20:00-22:00 |
| 深圳证券交易所 (SZSE) | 份额、日行情 | 每日 20:00-22:00 |
| 新浪财经 | ETF 全称、十大持有人 | 不定期（持有人滞后 4-5 月） |

接口细节：
- SSE 份额：`commonQuery.do?sqlId=COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L`
- SSE 全称：`security/stock/queryExpandName.do`
- SZSE 份额：深交所公开数据接口
- 新浪持有人：基金档案页解析

## 数据更新时机

**重要**：A 股清算完成后数据才更新，约**晚上 8-10 点**。白天查到的"最新"实际是前一天的。

## 文档

- [CLAUDE.md](CLAUDE.md) — 项目说明（AI 助手入口）
- [ARCHITECTURE.md](ARCHITECTURE.md) — 架构设计
- [DEPLOY.md](DEPLOY.md) — 部署运维
- [docs/API.md](docs/API.md) — REST API 参考
- [docs/DATASHEET.md](docs/DATASHEET.md) — 数据库 schema 说明
- [docs/legacy-cli.md](docs/legacy-cli.md) — 旧 CLI 工具归档（已退役）

## License

Private project.
