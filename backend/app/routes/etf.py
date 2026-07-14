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
    try:
        result = etf_service.get_rising_etfs(days)
    except ValueError as e:
        return _bad_request(e)
    return jsonify(result)


@bp.route('/securities', methods=['GET'])
def get_securities():
    sort_by = request.args.get('sort_by', 'volume')
    limit = request.args.get('limit', 50, type=int)
    try:
        result = etf_service.get_securities_etfs(sort_by, limit)
    except ValueError as e:
        return _bad_request(e)
    return jsonify(result)


@bp.route('/<sec_code>/holders', methods=['GET'])
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


@bp.route('/<sec_code>/huijin', methods=['GET'])
def get_huijin(sec_code):
    mode = request.args.get('mode', 'estimated')
    if mode not in ('estimated', 'actual'):
        return _bad_request("mode must be 'estimated' or 'actual'")
    try:
        res = etf_service.get_huijin_analysis(sec_code, mode)
    except ValueError as e:
        return _bad_request(e)
    return jsonify(res)


@bp.route('/stats/summary', methods=['GET'])
def get_stats_summary():
    try:
        res = etf_service.get_stats_summary()
    except Exception as e:
        return _bad_request(e)
    return jsonify(res)


@bp.route('/data-status', methods=['GET'])
def get_data_status():
    days = request.args.get('days', 20, type=int)
    try:
        res = etf_service.get_data_status(days)
    except Exception as e:
        return _bad_request(e)
    return jsonify(res)
