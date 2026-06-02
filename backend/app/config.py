"""应用配置 - 优先从环境变量读取，提供合理默认值"""
import os

from dotenv import load_dotenv

# 自动加载 backend/.env（不存在则跳过）
load_dotenv()


class Config:
    """Flask 应用配置类。

    所有配置项优先从环境变量读取；未设置时使用与现有生产行为一致的默认值。
    """

    # 数据库
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://etf_user:EtfPass2026!@localhost:5432/etf_db',
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-not-for-prod')

    # 数据采集（Phase 2 启用）
    FETCH_ENABLED = os.environ.get('FETCH_ENABLED', 'false').lower() == 'true'
    FETCH_SSE_DAYS = int(os.environ.get('FETCH_SSE_DAYS', '5'))
