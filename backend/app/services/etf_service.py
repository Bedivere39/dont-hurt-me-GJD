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

    start_date = datetime.now().date() - timedelta(days=days)
    
    # 查找最新日期
    latest_row = db.session.query(func.max(ETFDailyShare.stat_date)).first()
    latest = latest_row[0] if latest_row else None
    if not latest:
        return []

    latest_shares = {r.sec_code: r.tot_vol for r in db.session.query(
        ETFDailyShare.sec_code, ETFDailyShare.tot_vol
    ).filter(ETFDailyShare.stat_date == latest).all()}

    earliest_subq = db.session.query(
        ETFDailyShare.sec_code.label('sec_code'),
        func.min(ETFDailyShare.stat_date).label('first_date')
    ).filter(ETFDailyShare.stat_date >= start_date
    ).group_by(ETFDailyShare.sec_code).subquery()

    earliest_rows = db.session.query(
        ETFDailyShare.sec_code,
        ETFDailyShare.tot_vol,
        ETFDailyShare.stat_date
    ).join(
        earliest_subq,
        (ETFDailyShare.sec_code == earliest_subq.c.sec_code)
        & (ETFDailyShare.stat_date == earliest_subq.c.first_date)
    ).all()

    earliest_shares = {r.sec_code: (r.tot_vol, r.stat_date) for r in earliest_rows}

    etf_infos = {e.sec_code: e for e in ETFInfo.query.all()}

    result = []
    for sec_code, latest_vol in latest_shares.items():
        if sec_code not in earliest_shares:
            continue
        start_vol, start_date_val = earliest_shares[sec_code]
        if not start_vol or latest_vol <= start_vol:
            continue
        change_pct = ((latest_vol - start_vol) * 100.0) / start_vol
        etf = etf_infos.get(sec_code)
        result.append({
            'sec_code': sec_code,
            'sec_name': etf.sec_name if etf else None,
            'etf_type': etf.etf_type if etf else None,
            'start_vol': start_vol,
            'latest_vol': latest_vol,
            'change_pct': change_pct,
            'start_date': str(start_date_val),
            'end_date': str(latest)
        })

    result.sort(key=lambda x: x['change_pct'], reverse=True)
    return result


def get_securities_etfs(sort_by, limit=50):
    """获取所有证券/保险 ETF，按 sort_by 排序。"""
    if sort_by not in ('volume', 'change', 'pct'):
        raise ValueError("sort_by must be 'volume', 'change', or 'pct'")

    latest_row = db.session.query(func.max(ETFDailyShare.stat_date)).first()
    latest = latest_row[0] if latest_row else None
    if not latest:
        return []

    base = db.session.query(
        ETFInfo.sec_code,
        ETFInfo.sec_name,
        ETFInfo.full_name,
        ETFDailyShare.tot_vol,
        ETFDailyShare.stat_date
    ).join(ETFDailyShare, ETFInfo.sec_code == ETFDailyShare.sec_code
    ).filter(
        db.or_(
            ETFInfo.full_name.ilike('%证券%'),
            ETFInfo.full_name.ilike('%保险%'),
            ETFInfo.sec_name.ilike('%证券%'),
            ETFInfo.sec_name.ilike('%保险%'),
        ),
        ETFDailyShare.stat_date == latest
    )
    rows = base.all()

    if sort_by == 'volume':
        rows = sorted(rows, key=lambda r: r.tot_vol or 0, reverse=True)
        return [{
            'sec_code': r.sec_code,
            'sec_name': r.sec_name,
            'full_name': r.full_name,
            'tot_vol': r.tot_vol,
            'stat_date': str(r.stat_date)
        } for r in rows[:limit]]

    # 查最近两个交易日算 change/pct
    latest_dates = [r[0] for r in db.session.query(ETFDailyShare.stat_date
    ).distinct().order_by(ETFDailyShare.stat_date.desc()
    ).limit(2).all()]

    if len(latest_dates) < 2:
        return []
    prev_date = latest_dates[1]

    prev_shares = {r.sec_code: r.tot_vol for r in db.session.query(
        ETFDailyShare.sec_code, ETFDailyShare.tot_vol
    ).filter(ETFDailyShare.stat_date == prev_date).all()}

    items = []
    for r in rows:
        prev_vol = prev_shares.get(r.sec_code, 0)
        change = r.tot_vol - prev_vol
        change_pct = (change * 100.0 / prev_vol) if prev_vol else 0
        items.append({
            'sec_code': r.sec_code,
            'sec_name': r.sec_name,
            'full_name': r.full_name,
            'tot_vol': r.tot_vol,
            'stat_date': str(r.stat_date),
            'change': change,
            'change_pct': change_pct
        })

    if sort_by == 'change':
        items.sort(key=lambda x: x['change'], reverse=True)
    else:
        items.sort(key=lambda x: x['change_pct'], reverse=True)

    return items[:limit]


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
    """中央汇金持仓分析（包含估算与实际模式）。"""
    etf = ETFInfo.query.get(sec_code)
    if not etf:
        raise ValueError(f'ETF {sec_code} not found')

    latest_dates = [r[0] for r in db.session.query(ETFTopHolder.stat_date
    ).filter(ETFTopHolder.sec_code == sec_code
    ).distinct().order_by(ETFTopHolder.stat_date.desc()
    ).limit(2).all()]

    response = {
        'sec_code': sec_code,
        'sec_name': etf.sec_name,
        'mode': mode,
        'holders': [],
        'dec31_holdings': None,
        'latest_holdings': None,
        'change': None,
        'change_pct': None,
        'disclaimer': None,
        'error': None
    }

    if mode == 'actual':
        if len(latest_dates) < 2:
            response['error'] = 'Not enough data for actual mode'
            return response

        dec31_date = latest_dates[1]
        latest_date = latest_dates[0]

        dec31_holdings = db.session.query(func.sum(ETFTopHolder.hold_volume)
        ).filter(ETFTopHolder.sec_code == sec_code, ETFTopHolder.stat_date == dec31_date
        ).scalar() or 0

        latest_holdings = db.session.query(func.sum(ETFTopHolder.hold_volume)
        ).filter(ETFTopHolder.sec_code == sec_code, ETFTopHolder.stat_date == latest_date
        ).scalar() or 0

        change = latest_holdings - dec31_holdings
        change_pct = (change * 100.0 / dec31_holdings) if dec31_holdings else 0

        response['dec31_holdings'] = dec31_holdings
        response['latest_holdings'] = latest_holdings
        response['change'] = change
        response['change_pct'] = change_pct

        return response

    if not latest_dates:
        response['error'] = 'No holder data available'
        return response

    latest_date = latest_dates[0]

    # 获取最新两个交易日
    share_dates = get_latest_dates(2)
    if len(share_dates) < 2:
        response['error'] = 'Not enough share data for estimation'
        return response

    latest_share = db.session.query(ETFDailyShare.tot_vol
    ).filter(ETFDailyShare.sec_code == sec_code, ETFDailyShare.stat_date == share_dates[0]
    ).scalar()
    prev_share = db.session.query(ETFDailyShare.tot_vol
    ).filter(ETFDailyShare.sec_code == sec_code, ETFDailyShare.stat_date == share_dates[1]
    ).scalar()

    if not latest_share or not prev_share:
        response['error'] = 'Insufficient share data'
        return response

    scale = latest_share / prev_share

    latest_holders = ETFTopHolder.query.filter(
        ETFTopHolder.sec_code == sec_code,
        ETFTopHolder.stat_date == latest_date
    ).all()

    holders = []
    dec31_holdings = 0
    latest_holdings = 0
    for h in latest_holders:
        estimated_volume = h.hold_volume * scale
        holders.append({
            'holder_name': h.holder_name,
            'hold_ratio': h.hold_ratio,
            'reported_volume': h.hold_volume,
            'estimated_volume': estimated_volume
        })
        dec31_holdings += h.hold_volume
        latest_holdings += estimated_volume

    change = latest_holdings - dec31_holdings
    change_pct = (change * 100.0 / dec31_holdings) if dec31_holdings else 0

    response['holders'] = holders
    response['dec31_holdings'] = dec31_holdings
    response['latest_holdings'] = latest_holdings
    response['change'] = change
    response['change_pct'] = change_pct
    response['disclaimer'] = 'Estimated based on latest known holdings and total share changes'

    return response


def get_stats_summary():
    """整体统计: ETF 数量、记录数、最新日期、总市值/变化、数据新鲜度。"""
    total_etfs = db.session.query(func.count(ETFInfo.sec_code)).scalar() or 0
    total_records = db.session.query(func.count(ETFDailyShare.id)).scalar() or 0

    latest_dates = get_latest_dates(2)
    latest_date = datetime.strptime(latest_dates[0], '%Y-%m-%d').date() if latest_dates else None
    prev_date = datetime.strptime(latest_dates[1], '%Y-%m-%d').date() if len(latest_dates) > 1 else None

    total_market_cap = 0
    if latest_date:
        total_market_cap = db.session.query(func.sum(ETFDailyShare.tot_vol)
        ).filter(ETFDailyShare.stat_date == latest_date
        ).scalar() or 0

    total_market_cap_prev = 0
    if prev_date:
        total_market_cap_prev = db.session.query(func.sum(ETFDailyShare.tot_vol)
        ).filter(ETFDailyShare.stat_date == prev_date
        ).scalar() or 0

    total_market_cap_change = total_market_cap - total_market_cap_prev
    market_change_pct = (total_market_cap_change * 100.0 / total_market_cap_prev) if total_market_cap_prev else 0

    data_freshness_hours = None
    if latest_date:
        delta = datetime.now().date() - latest_date
        data_freshness_hours = round(delta.total_seconds() / 3600, 1)

    return {
        'total_etfs': total_etfs,
        'total_records': total_records,
        'latest_date': str(latest_date) if latest_date else None,
        'prev_date': str(prev_date) if prev_date else None,
        'total_market_cap': total_market_cap,
        'total_market_cap_change': total_market_cap_change,
        'market_change_pct': market_change_pct,
        'data_freshness_hours': data_freshness_hours
    }


def get_data_status(days=20):
    """数据完整性: 获取最近若干天每日记录数与状态。"""
    start_date = datetime.now().date() - timedelta(days=days)
    
    # 查找最新日期
    latest_row = db.session.query(func.max(ETFDailyShare.stat_date)).first()
    latest_date = latest_row[0] if latest_row else None

    daily_counts = db.session.query(
        ETFDailyShare.stat_date,
        func.count(ETFDailyShare.id).label('count')
    ).filter(ETFDailyShare.stat_date >= start_date
    ).group_by(ETFDailyShare.stat_date
    ).order_by(ETFDailyShare.stat_date.desc()
    ).all()

    result = [{
        'date': str(r.stat_date),
        'count': r.count,
        'status': 'OK' if r.count > 800 else 'LOW'
    } for r in daily_counts]

    return {
        'latest_date': str(latest_date) if latest_date else None,
        'daily_counts': result
    }
