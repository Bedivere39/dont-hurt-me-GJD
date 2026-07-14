"""从旧版 SQLite 数据库 (data/etf_data.db) 迁移数据到 PostgreSQL。

用法:
    SOURCE_SQLITE_PATH=/path/to/etf_data.db python scripts/migrate_data.py
或：将 etf_data.db 放在 ../data/etf_data.db 自动检测。
"""
import os
import sqlite3
import sys
from datetime import datetime

# 允许从任意目录运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import ETFInfo, ETFDailyShare

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

print(f'开始数据迁移，源: {sqlite_db}')

conn = sqlite3.connect(sqlite_db)
cur = conn.cursor()

# 获取所有表（仅用于日志）
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cur.fetchall()]
print(f'SQLite 表: {tables}')

with app.app_context():
    # 迁移 etf_info
    # 旧表列顺序: (sec_code, sec_name, full_name, etf_type, created_at)
    cur.execute('SELECT * FROM etf_info')
    rows = cur.fetchall()
    print(f'迁移 {len(rows)} 条 etf_info...')
    for row in rows:
        try:
            etf = ETFInfo(
                sec_code=row[0],
                sec_name=row[1],
                etf_type=row[2] if len(row) > 2 else None,
                full_name=row[4] if len(row) > 4 else None,
                list_date=None,
                fund_manager=None,
            )
            db.session.merge(etf)
        except Exception as e:
            print(f'  Error on {row[0] if row else "?"}: {e}')
    db.session.commit()

    # 迁移 etf_daily_share
    # 旧表列顺序: (sec_code, stat_date, tot_vol, num, close_price, market)
    cur.execute('SELECT * FROM etf_daily_share')
    rows = cur.fetchall()
    print(f'迁移 {len(rows)} 条 etf_daily_share...')
    for i, row in enumerate(rows):
        try:
            share = ETFDailyShare(
                sec_code=row[0],
                stat_date=datetime.strptime(row[1], '%Y-%m-%d').date() if isinstance(row[1], str) else row[1],
                tot_vol=row[2],
                num=row[3] if len(row) > 3 else None,
                close_price=row[4] if len(row) > 4 else None,
                market=row[5] if len(row) > 5 else 'SH',
            )
            db.session.add(share)
            if (i + 1) % 10000 == 0:
                db.session.commit()
                print(f'  已提交 {i + 1} 条...')
        except Exception as e:
            print(f'  Error on row {i}: {e}')
    db.session.commit()

conn.close()
print('数据迁移完成！')

# 验证
with app.app_context():
    info_count = db.session.query(ETFInfo).count()
    share_count = db.session.query(ETFDailyShare).count()
    print(f'PostgreSQL 中: etf_info={info_count}, etf_daily_share={share_count}')
