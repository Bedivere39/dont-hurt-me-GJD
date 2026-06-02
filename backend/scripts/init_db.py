"""数据库初始化脚本：建表 + 报告当前记录数。

用法: python scripts/init_db.py
要求: backend/.env 中已设置 DATABASE_URL（或使用 Config 默认值）
"""
import os
import sys

# 允许从任意目录运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import ETFInfo, ETFDailyShare

app = create_app()

with app.app_context():
    db.create_all()
    print('数据库表创建完成')

    info_count = ETFInfo.query.count()
    share_count = ETFDailyShare.query.count()
    print(f'当前数据: etf_info={info_count}, etf_daily_share={share_count}')
