from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from app.config import Config

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from app.routes import etf, health

    # 健康检查挂在 /api/health，匹配 Nginx 反代规则和文档
    app.register_blueprint(health.bp, url_prefix='/api')
    app.register_blueprint(etf.bp, url_prefix='/api/etf')

    return app
