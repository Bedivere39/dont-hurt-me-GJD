"""ETF 业务服务层。

将 HTTP 层 (Flask 路由) 与数据访问层 (SQLAlchemy 模型) 分离。
- 函数只接受原始类型 (str/int/list/float)
- 返回 dict / list
- 校验失败或数据缺失时抛出 ValueError
- 不导入 Flask
"""
from datetime import datetime, timedelta

from sqlalchemy import func, desc, asc

from app import db
from app.models import ETFInfo, ETFDailyShare, ETFTopHolder


# 证券ETF 标识 (Phase 0 引入的 etf_type 字段取值)
SECURITIES_ETF_TYPE = 'securities'

# 中央汇金 识别关键字 (中文全名含"汇金")
HUIJIN_KEYWORD = '汇金'

# 有效排序字段映射 -> (order_by_clause 构造器, 是否需要日期子查询)
_RANK_SORT_BUILDERS = {
    'tot_vol': lambda q, sub: q.order_by(ETFDailyShare.tot_vol.desc()),
    'change': lambda q, sub: q.order_by((ETFDailyShare.tot_vol - sub.c.prev_vol).desc()),
    'pct': lambda q, sub: q.order_by(
        ((ETFDailyShare.tot_vol - sub.c.prev_vol) / sub.c.prev_vol).desc()
    ),
}


def _serialize_date(d):
    return d.isoformat() if d else None


def get_latest_dates(n):
    """返回最近 n 个交易日期 (降序)。"""
    if n <= 0:
        raise ValueError('n must be positive')
    rows = db.session.query(ETFDailyShare.stat_date).distinct().order_by(
        ETFDailyShare.stat_date.desc()
    ).limit(n).all()
    return [_serialize_date(r[0]) for r in rows]


def get_etf_list(page, per_page):
    """分页获取 ETF 列表。"""
    if page < 1:
        raise ValueError('page must be >= 1')
    if per_page < 1 or per_page > 200:
        raise ValueError('per_page must be between 1 and 200')

    pagination = ETFInfo.query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        'items': [{
            'sec_code': e.sec_code,
            'sec_name': e.sec_name,
            'full_name': e.full_name,
        } for e in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
    }


def get_etf(sec_code):
    """获取单个 ETF 详情。"""
    etf = ETFInfo.query.get(sec_code)
    if not etf:
        raise ValueError(f'ETF {sec_code} not found')
    return {
        'sec_code': etf.sec_code,
        'sec_name': etf.sec_name,
        'full_name': etf.full_name,
        'list_date': _serialize_date(etf.list_date),
        'fund_manager': etf.fund_manager,
    }


def get_etf_trend(sec_code, days):
    """返回 ETF 最近 days 天的份额/价格趋势。"""
    if days <= 0:
        raise ValueError('days must be positive')

    # 校验 sec_code 存在
    if not ETFInfo.query.get(sec_code):
        raise ValueError(f'ETF {sec_code} not found')

    start_date = datetime.now().date() - timedelta(days=days)
    data = ETFDailyShare.query.filter(
        ETFDailyShare.sec_code == sec_code,
        ETFDailyShare.stat_date >= start_date,
    ).order_by(ETFDailyShare.stat_date.asc()).all()

    return [{
        'date': _serialize_date(d.stat_date),
        'tot_vol': d.tot_vol,
        'close_price': d.close_price,
    } for d in data]


def _latest_two_subquery():
    """构造子查询: 每个 sec_code 取最近两个交易日的 tot_vol。

    返回的子查询包含: sec_code, stat_date, tot_vol, prev_vol, prev_date。
    """
    # 最新一天
    latest = db.session.query(
        ETFDailyShare.sec_code.label('sec_code'),
        func.max(ETFDailyShare.stat_date).label('latest_date'),
    ).group_by(ETFDailyShare.sec_code).subquery()

    # 倒数第二天
    prev = db.session.query(
        ETFDailyShare.sec_code.label('sec_code'),
        func.max(ETFDailyShare.stat_date).label('prev_date'),
    ).join(
        latest, ETFDailyShare.sec_code == latest.c.sec_code,
    ).filter(
        ETFDailyShare.stat_date < latest.c.latest_date,
    ).group_by(ETFDailyShare.sec_code).subquery()

    return latest, prev


def get_ranking(sort_by, limit):
    """按指定字段排序的 ETF 排名。

    sort_by 支持:
        - tot_vol: 按最新 tot_vol 降序
        - change: 按 tot_vol 增量降序
        - pct:     按 tot_vol 百分比变化降序
    """
    if sort_by not in _RANK_SORT_BUILDERS:
        raise ValueError(f"sort_by must be one of {list(_RANK_SORT_BUILDERS)}")
    if limit <= 0 or limit > 200:
        raise ValueError('limit must be between 1 and 200')

    latest, prev = _latest_two_subquery()

    base = db.session.query(
        ETFDailyShare.sec_code,
        ETFDailyShare.tot_vol.label('tot_vol'),
        latest.c.latest_date.label('stat_date'),
        prev.c.prev_date.label('prev_date'),
    ).join(
        latest, ETFDailyShare.sec_code == latest.c.sec_code,
    ).join(
        prev, ETFDailyShare.sec_code == prev.c.sec_code,
    ).filter(
        ETFDailyShare.stat_date == latest.c.latest_date,
    )

    # join ETFInfo 拿名称
    base = base.add_columns(ETFInfo.sec_name).join(
        ETFInfo, ETFInfo.sec_code == ETFDailyShare.sec_code,
    )

    rows = base.limit(limit * 3).all()  # 多取以容忍 prev_date 缺失

    # 转为 dict 并计算 change/pct
    enriched = []
    for r in rows:
        # r: (sec_code, tot_vol, stat_date, prev_date, sec_name)
        prev_vol = db.session.query(ETFDailyShare.tot_vol).filter(
            ETFDailyShare.sec_code == r.sec_code,
            ETFDailyShare.stat_date == r.prev_date,
        ).scalar()
        change = (r.tot_vol - prev_vol) if prev_vol is not None else None
        pct = (change / prev_vol * 100.0) if (prev_vol not in (None, 0) and change is not None) else None
        enriched.append({
            'sec_code': r.sec_code,
            'sec_name': r.sec_name,
            'tot_vol': r.tot_vol,
            'change': change,
            'pct': pct,
            'stat_date': _serialize_date(r.stat_date),
        })

    if sort_by == 'tot_vol':
        enriched.sort(key=lambda x: x['tot_vol'] or 0, reverse=True)
    elif sort_by == 'change':
        enriched.sort(key=lambda x: (x['change'] is None, -(x['change'] or 0)))
    elif sort_by == 'pct':
        enriched.sort(key=lambda x: (x['pct'] is None, -(x['pct'] or 0)))

    return enriched[:limit]


def get_compare(codes, days):
    """对比多只 ETF 在最近 days 天的份额走势。"""
    if not codes:
        raise ValueError('codes must not be empty')
    if days <= 0:
        raise ValueError('days must be positive')

    start_date = datetime.now().date() - timedelta(days=days)
    data = ETFDailyShare.query.filter(
        ETFDailyShare.sec_code.in_(codes),
        ETFDailyShare.stat_date >= start_date,
    ).order_by(ETFDailyShare.stat_date.asc()).all()

    result = {c: [] for c in codes}
    for d in data:
        if d.sec_code in result:
            result[d.sec_code].append({
                'date': _serialize_date(d.stat_date),
                'tot_vol': d.tot_vol,
                'close_price': d.close_price,
            })
    return result


def get_rising_etfs(days):
    """返回最近 days 天 tot_vol 上升的 ETF 列表 (按增幅降序)。"""
    if days <= 0:
        raise ValueError('days must be positive')

    cutoff = datetime.now().date() - timedelta(days=days)
    latest, prev = _latest_two_subquery()

    # 取 [cutoff, latest_date] 窗口内最早一天与最新一天
    earliest_in_window = db.session.query(
        ETFDailyShare.sec_code.label('sec_code'),
        func.min(ETFDailyShare.stat_date).label('first_date'),
    ).filter(ETFDailyShare.stat_date >= cutoff
    ).group_by(ETFDailyShare.sec_code).subquery()

    rows = db.session.query(
        ETFInfo.sec_code,
        ETFInfo.sec_name,
        ETFDailyShare.tot_vol.label('latest_vol'),
    ).join(
        ETFInfo, ETFInfo.sec_code == ETFDailyShare.sec_code,
    ).join(
        latest, ETFInfo.sec_code == latest.c.sec_code,
    ).filter(
        ETFDailyShare.stat_date == latest.c.latest_date,
    ).all()

    enriched = []
    for r in rows:
        first_vol = db.session.query(ETFDailyShare.tot_vol).filter(
            ETFDailyShare.sec_code == r.sec_code,
            ETFDailyShare.stat_date == earliest_in_window.c.first_date,
        ).scalar() if False else None
        # 注: SQLAlchemy 跨子查询关联较复杂, 退化为 python 端拉取 (单次, days<=365 可接受)
        first_row = db.session.query(ETFDailyShare.tot_vol).filter(
            ETFDailyShare.sec_code == r.sec_code,
            ETFDailyShare.stat_date >= cutoff,
        ).order_by(ETFDailyShare.stat_date.asc()).first()
        first_vol = first_row[0] if first_row else None

        if first_vol is None or r.latest_vol is None:
            continue
        if r.latest_vol > first_vol:
            change = r.latest_vol - first_vol
            pct = change / first_vol * 100.0 if first_vol else None
            enriched.append({
                'sec_code': r.sec_code,
                'sec_name': r.sec_name,
                'first_vol': first_vol,
                'latest_vol': r.latest_vol,
                'change': change,
                'pct': pct,
            })

    enriched.sort(key=lambda x: x['pct'] or 0, reverse=True)
    return enriched


def get_securities_etfs(sort_by):
    """获取所有证券ETF (etf_type=securities)，按 sort_by 排序。

    sort_by 支持: tot_vol / change / pct
    """
    if sort_by not in _RANK_SORT_BUILDERS:
        raise ValueError(f"sort_by must be one of {list(_RANK_SORT_BUILDERS)}")

    latest, prev = _latest_two_subquery()

    rows = db.session.query(
        ETFInfo.sec_code,
        ETFInfo.sec_name,
        ETFDailyShare.tot_vol.label('tot_vol'),
        latest.c.latest_date.label('stat_date'),
    ).join(
        ETFDailyShare, ETFDailyShare.sec_code == ETFInfo.sec_code,
    ).join(
        latest, ETFInfo.sec_code == latest.c.sec_code,
    ).filter(
        ETFInfo.etf_type == SECURITIES_ETF_TYPE,
        ETFDailyShare.stat_date == latest.c.latest_date,
    ).all()

    enriched = []
    for r in rows:
        prev_vol = db.session.query(ETFDailyShare.tot_vol).filter(
            ETFDailyShare.sec_code == r.sec_code,
            ETFDailyShare.stat_date == prev.c.prev_date,
        ).scalar()
        change = (r.tot_vol - prev_vol) if prev_vol is not None else None
        pct = (change / prev_vol * 100.0) if (prev_vol not in (None, 0) and change is not None) else None
        enriched.append({
            'sec_code': r.sec_code,
            'sec_name': r.sec_name,
            'tot_vol': r.tot_vol,
            'change': change,
            'pct': pct,
            'stat_date': _serialize_date(r.stat_date),
        })

    if sort_by == 'tot_vol':
        enriched.sort(key=lambda x: x['tot_vol'] or 0, reverse=True)
    elif sort_by == 'change':
        enriched.sort(key=lambda x: (x['change'] is None, -(x['change'] or 0)))
    elif sort_by == 'pct':
        enriched.sort(key=lambda x: (x['pct'] is None, -(x['pct'] or 0)))
    return enriched


def get_etf_holders(sec_code):
    """获取 ETF 最新一期的 top holders。"""
    if not ETFInfo.query.get(sec_code):
        raise ValueError(f'ETF {sec_code} not found')

    latest_date = db.session.query(func.max(ETFTopHolder.stat_date)).filter(
        ETFTopHolder.sec_code == sec_code,
    ).scalar()

    if not latest_date:
        return []

    rows = ETFTopHolder.query.filter(
        ETFTopHolder.sec_code == sec_code,
        ETFTopHolder.stat_date == latest_date,
    ).order_by(ETFTopHolder.hold_ratio.desc()).all()

    return [{
        'holder_name': h.holder_name,
        'hold_volume': h.hold_volume,
        'hold_ratio': h.hold_ratio,
        'stat_date': _serialize_date(h.stat_date),
    } for h in rows]


def get_holders_by_type(holder_type, min_pct):
    """按关键字筛选 holder_name, 并按 hold_ratio >= min_pct 过滤。"""
    if min_pct is None or min_pct < 0 or min_pct > 100:
        raise ValueError('min_pct must be between 0 and 100')

    # 取每个 sec_code 最新一期的 holders
    latest = db.session.query(
        ETFTopHolder.sec_code.label('sec_code'),
        func.max(ETFTopHolder.stat_date).label('latest_date'),
    ).group_by(ETFTopHolder.sec_code).subquery()

    rows = db.session.query(
        ETFTopHolder,
        ETFInfo.sec_name,
    ).join(
        latest,
        (ETFTopHolder.sec_code == latest.c.sec_code)
        & (ETFTopHolder.stat_date == latest.c.latest_date),
    ).join(
        ETFInfo, ETFInfo.sec_code == ETFTopHolder.sec_code,
    ).filter(
        ETFTopHolder.holder_name.like(f'%{holder_type}%'),
        ETFTopHolder.hold_ratio >= min_pct,
    ).order_by(ETFTopHolder.hold_ratio.desc()).all()

    return [{
        'sec_code': h.ETFTopHolder.sec_code,
        'sec_name': sec_name,
        'holder_name': h.ETFTopHolder.holder_name,
        'hold_volume': h.ETFTopHolder.hold_volume,
        'hold_ratio': h.ETFTopHolder.hold_ratio,
        'stat_date': _serialize_date(h.ETFTopHolder.stat_date),
    } for h, sec_name in rows]


def get_huijin_analysis(sec_code, mode):
    """中央汇金分析。

    mode:
        - 'history': 返回该 ETF 所有有汇金持仓的期次
        - 'summary': 返回该 ETF 最新一期汇金持仓汇总
    """
    if mode not in ('history', 'summary'):
        raise ValueError("mode must be 'history' or 'summary'")
    if not ETFInfo.query.get(sec_code):
        raise ValueError(f'ETF {sec_code} not found')

    q = ETFTopHolder.query.filter(
        ETFTopHolder.sec_code == sec_code,
        ETFTopHolder.holder_name.like(f'%{HUIJIN_KEYWORD}%'),
    )

    if mode == 'summary':
        latest_date = db.session.query(func.max(ETFTopHolder.stat_date)).filter(
            ETFTopHolder.sec_code == sec_code,
            ETFTopHolder.holder_name.like(f'%{HUIJIN_KEYWORD}%'),
        ).scalar()
        if not latest_date:
            return {'sec_code': sec_code, 'holdings': []}
        q = q.filter(ETFTopHolder.stat_date == latest_date)
        return {
            'sec_code': sec_code,
            'stat_date': _serialize_date(latest_date),
            'holdings': [{
                'holder_name': h.holder_name,
                'hold_volume': h.hold_volume,
                'hold_ratio': h.hold_ratio,
            } for h in q.all()],
        }

    # history
    rows = q.order_by(ETFTopHolder.stat_date.desc()).all()
    return {
        'sec_code': sec_code,
        'history': [{
            'stat_date': _serialize_date(h.stat_date),
            'holder_name': h.holder_name,
            'hold_volume': h.hold_volume,
            'hold_ratio': h.hold_ratio,
        } for h in rows],
    }


def get_stats_summary():
    """整体统计: ETF 数量、记录数、最新日期、覆盖范围。"""
    total_etfs = db.session.query(func.count(ETFInfo.sec_code)).scalar() or 0
    total_records = db.session.query(func.count(ETFDailyShare.id)).scalar() or 0
    latest_date = db.session.query(func.max(ETFDailyShare.stat_date)).scalar()
    earliest_date = db.session.query(func.min(ETFDailyShare.stat_date)).scalar()

    return {
        'total_etfs': total_etfs,
        'total_records': total_records,
        'latest_date': _serialize_date(latest_date),
        'earliest_date': _serialize_date(earliest_date),
    }


def get_data_status():
    """数据状态: 最新日期距今天数、各表是否有数据。"""
    today = datetime.now().date()
    latest_date = db.session.query(func.max(ETFDailyShare.stat_date)).scalar()
    days_stale = (today - latest_date).days if latest_date else None
    has_etf_info = db.session.query(ETFInfo.sec_code).first() is not None
    has_daily = db.session.query(ETFDailyShare.id).first() is not None
    has_holders = db.session.query(ETFTopHolder.id).first() is not None

    return {
        'latest_date': _serialize_date(latest_date),
        'days_stale': days_stale,
        'has_etf_info': has_etf_info,
        'has_daily_share': has_daily,
        'has_top_holders': has_holders,
    }
