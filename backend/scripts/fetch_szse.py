"""深圳证券交易所ETF份额数据采集脚本（基于全量列表页循环）。

用法:
    python scripts/fetch_szse.py
"""
import os
import sys
import time
import re
import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

# 允许从任意目录运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import ETFDailyShare, ETFInfo


# --- 常量 ---
SZSE_API_URL = 'https://fund.szse.cn/api/report/ShowReport/data'
REQUEST_TIMEOUT = 15  # 单次 HTTP 超时（秒）
PAGE_SLEEP = 0.1  # 分页间休眠，避免被限流

SZSE_HEADERS = {
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Referer': 'https://fund.szse.cn/marketdata/etf/index.html',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
}


def parse_date(value: Any) -> Optional[date]:
    """兼容字符串或 date 对象。"""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        for fmt in ('%Y-%m-%d', '%Y%m%d'):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
    return None


def fetch_all_szse_etfs() -> Tuple[List[Dict[str, Any]], Optional[date]]:
    """循环爬取深交所 ETF 全页列表，返回所有行数据与解析出的数据日期。"""
    all_rows = []
    page = 1
    total_pages = 1
    stat_date = None

    session = requests.Session()
    print("开始从深交所接口分页拉取数据...")

    while page <= total_pages:
        params = {
            'SHOWTYPE': 'JSON',
            'CATALOGID': 'fund_etf',
            'random': str(time.time()),
            'pageNo': str(page),
            'pageno': str(page),
            'pageSize': '10',
            'pagesize': '10'
        }
        try:
            resp = session.get(SZSE_API_URL, params=params, headers=SZSE_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"第 {page} 页请求失败: {e}")
            break

        if not data or len(data) == 0:
            print(f"第 {page} 页返回空响应")
            break

        metadata = data[0].get('metadata', {})
        total_pages = metadata.get('pagecount', 1)
        
        # 仅第一页解析数据日期
        if page == 1:
            cols = metadata.get('cols', {})
            dqgm_header = cols.get('dqgm', '')
            date_match = re.search(r'[（\(](\d{4}-\d{2}-\d{2})[）\)]', dqgm_header)
            if date_match:
                stat_date = parse_date(date_match.group(1))
                print(f"从 dqgm 表头解析到数据日期: {stat_date}")
            else:
                subname = metadata.get('subname', '')
                stat_date = parse_date(subname)
                if stat_date:
                    print(f"从 subname 解析到数据日期: {stat_date}")
                else:
                    stat_date = datetime.now().date()
                    print(f"未解析到日期，使用当前日期: {stat_date}")

        rows = data[0].get('data', [])
        if not rows:
            print(f"第 {page} 页无 ETF 行数据")
            break

        all_rows.extend(rows)
        if page % 10 == 0 or page == total_pages:
            print(f"已拉取页面 {page}/{total_pages} (已拉取 {len(all_rows)} 条记录)")

        page += 1
        time.sleep(PAGE_SLEEP)

    return all_rows, stat_date


def parse_and_upsert(rows: List[Dict[str, Any]], stat_date: date) -> Tuple[int, int]:
    """解析并入库（优化为基于查询的 Upsert 以防 Unique 冲突）。"""
    if not stat_date:
        return 0, 0

    # 1. 预解析并去重 rows (只保留每个 sec_code 最新的那条)
    parsed_items = {}
    for item in rows:
        sys_key = item.get('sys_key', '')
        code_match = re.search(r'code=(\d+)', sys_key)
        sec_code = code_match.group(1) if code_match else ''
        sec_code = sec_code.strip()
        if not sec_code:
            continue

        kzjcurl = item.get('kzjcurl', '')
        name_match = re.search(r'<u>([^<]+)</u>', kzjcurl)
        sec_name = name_match.group(1) if name_match else ''
        sec_name = sec_name.strip()

        dqgm = item.get('dqgm', '')
        shares_match = re.search(r'>([\d,.]+)<', dqgm)
        shares_str = shares_match.group(1) if shares_match else dqgm
        shares_str = shares_str.replace(',', '').strip()
        try:
            tot_vol = float(shares_str) if shares_str else 0.0
        except ValueError:
            tot_vol = 0.0

        parsed_items[sec_code] = {
            'sec_name': sec_name,
            'tot_vol': tot_vol
        }

    if not parsed_items:
        return 0, 0

    # 2. 查询已有的 records
    sec_codes = list(parsed_items.keys())
    existing_shares = {s.sec_code: s for s in ETFDailyShare.query.filter(
        ETFDailyShare.stat_date == stat_date,
        ETFDailyShare.sec_code.in_(sec_codes)
    ).all()}

    existing_infos = {e.sec_code: e for e in ETFInfo.query.filter(
        ETFInfo.sec_code.in_(sec_codes)
    ).all()}

    share_count = 0
    info_count = 0

    for sec_code, p in parsed_items.items():
        # Upsert Daily Share
        if sec_code in existing_shares:
            share = existing_shares[sec_code]
            share.tot_vol = p['tot_vol']
            share.num = 1
            share.market = 'SZ'
        else:
            share = ETFDailyShare(
                sec_code=sec_code,
                stat_date=stat_date,
                tot_vol=p['tot_vol'],
                num=1,
                market='SZ'
            )
            db.session.add(share)
            share_count += 1

        # Upsert ETF Info
        if sec_code in existing_infos:
            info = existing_infos[sec_code]
            if p['sec_name']:
                info.sec_name = p['sec_name']
        else:
            info = ETFInfo(
                sec_code=sec_code,
                sec_name=p['sec_name'] if p['sec_name'] else None,
                etf_type=None
            )
            db.session.add(info)
            info_count += 1

    db.session.commit()
    return share_count, info_count


def main() -> int:
    started_at = datetime.now()
    print('=== SZSE ETF 数据采集 ===')
    print(f'开始时间: {started_at.strftime("%Y-%m-%d %H:%M:%S")}')

    rows, stat_date = fetch_all_szse_etfs()
    if not rows or not stat_date:
        print("未获取到任何有效的 SZSE ETF 数据或日期错误")
        return 1

    print(f"共获取到 {len(rows)} 条 ETF 行数据。")

    app = create_app()
    with app.app_context():
        try:
            s_cnt, i_cnt = parse_and_upsert(rows, stat_date)
            print(f"数据入库成功: 写入 etf_daily_share={s_cnt} 条, etf_info={i_cnt} 条")
        except Exception as e:
            db.session.rollback()
            print(f"数据入库失败: {e}")
            return 1

    ended_at = datetime.now()
    elapsed = (ended_at - started_at).total_seconds()
    print(f"结束时间: {ended_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"耗时: {elapsed:.1f}s")
    return 0


if __name__ == '__main__':
    sys.exit(main())
