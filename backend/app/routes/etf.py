from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from sqlalchemy import func

from app import db
from app.models import ETFInfo, ETFDailyShare, ETFTopHolder
from app.services import etf_service

bp = Blueprint('etf', __name__)


def _bad_request(msg):
    return jsonify({'error': str(msg)}), 400


def get_latest_dates(n=2):
    """Return the latest n distinct stat_dates as date objects, descending."""
    date_strs = etf_service.get_latest_dates(n)
    return [datetime.strptime(d, '%Y-%m-%d').date() for d in date_strs if d]


def get_latest_date():
    """Return the most recent stat_date as a date object, or None."""
    dates = get_latest_dates(1)
    return dates[0] if dates else None


@bp.route('/list', methods=['GET'])
def get_etf_list():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    try:
        result = etf_service.get_etf_list(page, per_page)
    except ValueError as e:
        return _bad_request(e)
    return jsonify(result)


@bp.route('/<sec_code>', methods=['GET'])
def get_etf(sec_code):
    try:
        result = etf_service.get_etf(sec_code)
    except ValueError as e:
        return _bad_request(e)
    return jsonify(result)


@bp.route('/<sec_code>/trend', methods=['GET'])
def get_etf_trend(sec_code):
    days = request.args.get('days', 30, type=int)
    try:
        result = etf_service.get_etf_trend(sec_code, days)
    except ValueError as e:
        return _bad_request(e)
    return jsonify(result)


@bp.route('/ranking', methods=['GET'])
def get_ranking():
    sort_by = request.args.get('sort_by', 'tot_vol')
    limit = request.args.get('limit', 10, type=int)
    try:
        result = etf_service.get_ranking(sort_by, limit)
    except ValueError as e:
        return _bad_request(e)

    sec_codes = [r['sec_code'] for r in result]
    etf_infos = {}
    if sec_codes:
        etf_infos = {e.sec_code: e for e in ETFInfo.query.filter(
            ETFInfo.sec_code.in_(sec_codes)
        ).all()}

    transformed = [{
        'sec_code': r['sec_code'],
        'sec_name': r['sec_name'],
        'etf_type': etf_infos[r['sec_code']].etf_type if r['sec_code'] in etf_infos else None,
        'tot_vol': r['tot_vol'],
        'stat_date': r['stat_date'],
        'change': r['change'],
        'change_pct': r['pct'],
    } for r in result]
    return jsonify(transformed)


@bp.route('/compare', methods=['GET'])
def compare_etf():
    codes_param = request.args.get('codes', '')
    codes = [c for c in codes_param.split(',') if c]
    days = request.args.get('days', 30, type=int)
    try:
        result = etf_service.get_compare(codes, days)
    except ValueError as e:
        return _bad_request(e)
    return jsonify(result)


@bp.route('/rising', methods=['GET'])
def get_rising():
    days = request.args.get('days', 126, type=int)
    if days <= 0:
        return _bad_request('days must be positive')

    start_date = datetime.now().date() - timedelta(days=days)
    latest = get_latest_date()
    if not latest:
        return jsonify([])

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
    return jsonify(result)


@bp.route('/securities', methods=['GET'])
def get_securities():
    sort_by = request.args.get('sort_by', 'volume')
    if sort_by not in ('volume', 'change', 'pct'):
        return _bad_request("sort_by must be 'volume', 'change', or 'pct'")

    latest = get_latest_date()
    if not latest:
        return jsonify([])

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
            # 兼容老数据 full_name 字段被截断/错位的情况
            ETFInfo.sec_name.ilike('%证券%'),
            ETFInfo.sec_name.ilike('%保险%'),
        ),
        ETFDailyShare.stat_date == latest
    )
    rows = base.all()

    if sort_by == 'volume':
        rows = sorted(rows, key=lambda r: r.tot_vol or 0, reverse=True)
        return jsonify([{
            'sec_code': r.sec_code,
            'sec_name': r.sec_name,
            'full_name': r.full_name,
            'tot_vol': r.tot_vol,
            'stat_date': str(r.stat_date)
        } for r in rows])

    dates = get_latest_dates(2)
    if len(dates) < 2:
        return jsonify([])
    prev_date = dates[1]

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

    return jsonify(items)


@bp.route('/code/holders/<sec_code>', methods=['GET'])
def get_etf_holders(sec_code):
    try:
        holders = etf_service.get_etf_holders(sec_code)
    except ValueError as e:
        return _bad_request(e)

    if not holders:
        return jsonify({'sec_code': sec_code, 'holders': [], 'stat_date': None})

    stat_date = holders[0].get('stat_date')
    return jsonify({
        'sec_code': sec_code,
        'holders': [{
            'holder_name': h['holder_name'],
            'hold_volume': h['hold_volume'],
            'hold_ratio': h['hold_ratio']
        } for h in holders[:10]],
        'stat_date': stat_date
    })


@bp.route('/holders-by-type', methods=['GET'])
def get_holders_by_type():
    holder_type = request.args.get('type', '', type=str)
    min_pct = request.args.get('min_pct', 0.5, type=float)
    try:
        result = etf_service.get_holders_by_type(holder_type, min_pct)
    except ValueError as e:
        return _bad_request(e)

    sec_codes = list({r['sec_code'] for r in result})
    etf_infos = {}
    if sec_codes:
        etf_infos = {e.sec_code: e for e in ETFInfo.query.filter(
            ETFInfo.sec_code.in_(sec_codes)
        ).all()}

    enriched = [{
        'sec_code': r['sec_code'],
        'full_name': etf_infos[r['sec_code']].full_name if r['sec_code'] in etf_infos else None,
        'sec_name': r['sec_name'],
        'holder_name': r['holder_name'],
        'hold_ratio': r['hold_ratio'],
        'stat_date': r['stat_date']
    } for r in result]
    return jsonify(enriched)


@bp.route('/code/huijin/<sec_code>', methods=['GET'])
def get_huijin(sec_code):
    mode = request.args.get('mode', 'estimated')
    if mode not in ('estimated', 'actual'):
        return _bad_request("mode must be 'estimated' or 'actual'")

    etf = ETFInfo.query.get(sec_code)
    if not etf:
        return _bad_request(f'ETF {sec_code} not found')

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
            return jsonify(response)

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

        return jsonify(response)

    if not latest_dates:
        response['error'] = 'No holder data available'
        return jsonify(response)

    latest_date = latest_dates[0]

    share_dates = get_latest_dates(2)
    if len(share_dates) < 2:
        response['error'] = 'Not enough share data for estimation'
        return jsonify(response)

    latest_share = db.session.query(ETFDailyShare.tot_vol
    ).filter(ETFDailyShare.sec_code == sec_code, ETFDailyShare.stat_date == share_dates[0]
    ).scalar()
    prev_share = db.session.query(ETFDailyShare.tot_vol
    ).filter(ETFDailyShare.sec_code == sec_code, ETFDailyShare.stat_date == share_dates[1]
    ).scalar()

    if not latest_share or not prev_share:
        response['error'] = 'Insufficient share data'
        return jsonify(response)

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

    return jsonify(response)


@bp.route('/stats/summary', methods=['GET'])
def get_stats_summary():
    total_etfs = db.session.query(func.count(ETFInfo.sec_code)).scalar() or 0
    total_records = db.session.query(func.count(ETFDailyShare.id)).scalar() or 0

    dates = get_latest_dates(2)
    latest_date = dates[0] if dates else None
    prev_date = dates[1] if len(dates) > 1 else None

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

    return jsonify({
        'total_etfs': total_etfs,
        'total_records': total_records,
        'latest_date': str(latest_date) if latest_date else None,
        'prev_date': str(prev_date) if prev_date else None,
        'total_market_cap': total_market_cap,
        'total_market_cap_change': total_market_cap_change,
        'market_change_pct': market_change_pct,
        'data_freshness_hours': data_freshness_hours
    })


@bp.route('/data-status', methods=['GET'])
def get_data_status():
    start_date = datetime.now().date() - timedelta(days=20)
    latest_date = get_latest_date()

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

    return jsonify({
        'latest_date': str(latest_date) if latest_date else None,
        'daily_counts': result
    })
