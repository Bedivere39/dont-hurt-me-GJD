"""从旧版 SQLite 数据库 (data/etf_data.db) 迁移 etf_top_holders 到 PostgreSQL。

用法:
    SOURCE_SQLITE_PATH=/path/to/etf_data.db python scripts/migrate_holders.py
或：将 etf_data.db 放在 ../data/etf_data.db 自动检测。

字段映射:
    sec_code   -> sec_code
    stat_date  -> stat_date (TEXT -> Date, YYYY-MM-DD)
    rank       -> DROPPED (模型中无该字段)
    holder_name-> holder_name
    holder_share -> hold_volume
    holder_pct -> hold_ratio
    created_at -> 使用模型默认 (datetime.utcnow)
"""
import os
import sqlite3
import sys
from datetime import date, datetime

# 允许从任意目录运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import ETFTopHolder

# 解析 SQLite 源路径：env 优先，回退到 ../data/etf_data.db
sqlite_db = os.environ.get('SOURCE_SQLITE_PATH')
if not sqlite_db:
    default = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'data',
        'etf_data.db',
    )
    sqlite_db = default if os.path.exists(default) else None
if not sqlite_db:
    sys.exit('ERROR: Set SOURCE_SQLITE_PATH env or place etf_data.db at data/etf_data.db')

app = create_app()

print(f'开始迁移 etf_top_holders，源: {sqlite_db}')

conn = sqlite3.connect(sqlite_db)
cur = conn.cursor()

# 确认源表存在
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='etf_top_holders'")
if not cur.fetchone():
    conn.close()
    sys.exit('ERROR: 源数据库中未找到 etf_top_holders 表')

# 旧表列顺序: (id, sec_code, stat_date, rank, holder_name, holder_share, holder_pct, created_at)
cur.execute('SELECT * FROM etf_top_holders')
rows = cur.fetchall()
print(f'待迁移记录: {len(rows)} 条')

migrated = 0
skipped = 0
errors = 0

with app.app_context():
    for i, row in enumerate(rows):
        try:
            source_id = row[0]
            sec_code = row[1]

            # 防御性跳过：缺少 sec_code 的行无法归属
            if not sec_code:
                skipped += 1
                continue

            stat_date_raw = row[2]
            holder_name = row[4]
            holder_share = row[5]
            holder_pct = row[6]

            # stat_date: TEXT (YYYY-MM-DD) -> date
            stat_date_val = None
            if stat_date_raw:
                try:
                    stat_date_val = date.fromisoformat(stat_date_raw)
                except ValueError:
                    # 兼容包含时间部分的格式 (YYYY-MM-DD HH:MM:SS)
                    try:
                        stat_date_val = datetime.strptime(
                            stat_date_raw[:10], '%Y-%m-%d'
                        ).date()
                    except ValueError:
                        print(f'  跳过：无法解析 stat_date={stat_date_raw!r} (id={source_id})')
                        skipped += 1
                        continue

            holder = ETFTopHolder(
                id=source_id,
                sec_code=sec_code,
                stat_date=stat_date_val,
                holder_name=holder_name,
                hold_volume=holder_share,
                hold_ratio=holder_pct,
            )
            db.session.merge(holder)
            migrated += 1

            if (i + 1) % 1000 == 0:
                db.session.commit()
                print(f'  已处理 {i + 1}/{len(rows)} 条...')
        except Exception as e:
            errors += 1
            print(f'  Error on row {i} (id={row[0] if row else "?"}): {e}')

    db.session.commit()

conn.close()

print(
    f'迁移完成: migrated={migrated}, skipped={skipped}, errors={errors}, total={len(rows)}'
)

# 验证
with app.app_context():
    count = db.session.query(ETFTopHolder).count()
    print(f'PostgreSQL 中 etf_top_holders 总数: {count}')
