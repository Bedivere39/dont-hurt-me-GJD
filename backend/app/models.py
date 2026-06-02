from datetime import datetime

from app import db


class ETFInfo(db.Model):
    __tablename__ = 'etf_info'

    sec_code = db.Column(db.String(20), primary_key=True)
    sec_name = db.Column(db.String(100))
    full_name = db.Column(db.String(200))
    etf_type = db.Column(db.String(50))
    list_date = db.Column(db.Date)
    fund_manager = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ETFDailyShare(db.Model):
    __tablename__ = 'etf_daily_share'

    id = db.Column(db.Integer, primary_key=True)
    sec_code = db.Column(db.String(20), db.ForeignKey('etf_info.sec_code'), nullable=False)
    stat_date = db.Column(db.Date, nullable=False)
    tot_vol = db.Column(db.Float)
    num = db.Column(db.Integer)
    close_price = db.Column(db.Float)
    market = db.Column(db.String(10), default='SH')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('sec_code', 'stat_date', name='uqc_sec_code_stat_date'),
        db.Index('idx_etf_daily_share_sec_code', 'sec_code'),
        db.Index('idx_etf_daily_share_stat_date', 'stat_date'),
    )


class ETFTopHolder(db.Model):
    __tablename__ = 'etf_top_holders'

    id = db.Column(db.Integer, primary_key=True)
    sec_code = db.Column(db.String(20), db.ForeignKey('etf_info.sec_code'), nullable=False)
    holder_name = db.Column(db.String(200))
    hold_volume = db.Column(db.Float)
    hold_ratio = db.Column(db.Float)
    stat_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
