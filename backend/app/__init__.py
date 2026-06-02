from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from app.config import Config

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from app.routes import etf, health

    app.register_blueprint(health.bp)
    app.register_blueprint(etf.bp, url_prefix='/api/etf')

    return app
