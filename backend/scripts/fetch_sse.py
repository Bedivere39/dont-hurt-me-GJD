"""上海证券交易所ETF份额数据采集脚本（Phase 2）。

用法:
    python scripts/fetch_sse.py [days]

参数:
    days: 采集最近多少个工作日的数据（默认 5，覆盖周末/节假日）

环境变量:
    DATABASE_URL: PostgreSQL 连接字符串（默认从 Config 读取）
    FETCH_SSE_DAYS: 默认采集天数（默认 5）

依赖:
    - requests: HTTP 客户端
    - beautifulsoup4 / lxml: 已安装供后续 HTML 解析使用（当前仅解析 JSONP）

数据源:
    SSE commonQuery 接口：
      https://query.sse.com.cn/commonQuery.do?sqlId=COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L
    响应格式: JSONP 包裹 (jsonCallBack=cb)，需去除回调外层。
"""
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

# 允许从任意目录运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.config import Config
from app.models import ETFDailyShare, ETFInfo


# --- 常量 ---
SSE_API_URL = 'https://query.sse.com.cn/commonQuery.do'
SSE_SQL_ID = 'COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L'
PAGE_SIZE = 50  # 每页请求数量（SSE 单次最多返回 ~10 条，分页取满）
REQUEST_TIMEOUT = 15  # 单次 HTTP 超时（秒）
PAGE_SLEEP = 0.1  # 分页间休眠，避免被限流

SSE_HEADERS = {
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Referer': 'https://www.sse.com.cn/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


# --- 工具函数 ---
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


def get_recent_workdays(days: int) -> List[str]:
    """获取最近 N 个工作日（周一至周五）的日期字符串列表。"""
    today = datetime.now().date()
    workdays: List[str] = []
    # 乘 3 留余量（节假日暂用周末判断，实际交易日由 SSE 返回空数据决定）
    for i in range(days * 3 + 5):
        d = today - timedelta(days=i)
        if d.weekday() < 5:
            workdays.append(d.strftime('%Y-%m-%d'))
            if len(workdays) >= days:
                break
    return workdays


def extract_jsonp(text: str) -> Dict[str, Any]:
    """去除 JSONP 回调外层并解析。"""
    text = text.strip()
    if not text:
        raise ValueError('empty response')
    start = text.find('(')
    end = text.rfind(')')
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f'not a JSONP response: {text[:80]}...')
    return json.loads(text[start + 1 : end])


# --- 数据拉取 ---
def fetch_day_data(session: requests.Session, date_str: str) -> List[Dict[str, Any]]:
    """拉取指定日期的全量 ETF 份额数据，自动处理分页。"""
    all_results: List[Dict[str, Any]] = []
    page_no = 1

    while True:
        params = {
            'jsonCallBack': 'cb',
            'isPagination': 'true',
            'pageHelp.pageSize': PAGE_SIZE,
            'pageHelp.pageNo': page_no,
            'pageHelp.beginPage': page_no,
            'pageHelp.cacheSize': 1,
            'pageHelp.endPage': page_no,
            'sqlId': SSE_SQL_ID,
            'STAT_DATE': date_str,
            '_': int(time.time() * 1000),
        }
        try:
            resp = session.get(
                SSE_API_URL, params=params, headers=SSE_HEADERS, timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            data = extract_jsonp(resp.text)
        except requests.exceptions.RequestException as e:
            print(f'  [{date_str}] page {page_no} HTTP error: {e}')
            break
        except (ValueError, json.JSONDecodeError) as e:
            print(f'  [{date_str}] page {page_no} parse error: {e}')
            break
        except Exception as e:  # 网络/解析兜底
            print(f'  [{date_str}] page {page_no} unexpected error: {e}')
            break

        results = data.get('result') or []
        all_results.extend(results)

        page_help = data.get('pageHelp') or {}
        total_pages = int(page_help.get('pageCount', 1))
        total_records = int(page_help.get('total', len(all_results)))
        print(
            f'  [{date_str}] page {page_no}/{total_pages} '
            f'(+{len(results)} records, total={total_records})'
        )

        if page_no >= total_pages:
            break
        page_no += 1
        time.sleep(PAGE_SLEEP)

    return all_results


# --- 数据写入 ---
def upsert_records(records: List[Dict[str, Any]]) -> Tuple[int, int]:
    """使用 db.session.merge 写入 etf_daily_share 和 etf_info。"""
    share_count = 0
    info_count = 0
    seen_codes: set = set()

    for r in records:
        sec_code = (r.get('SEC_CODE') or r.get('sec_code') or '').strip()
        stat_date_raw = r.get('STAT_DATE') or r.get('stat_date') or ''
        if not sec_code or not stat_date_raw:
            continue

        stat_date = parse_date(stat_date_raw)
        if stat_date is None:
            continue

        try:
            tot_vol = float(r.get('TOT_VOL', 0) or 0)
        except (TypeError, ValueError):
            tot_vol = 0.0
        try:
            num = int(r.get('NUM', 0) or 0)
        except (TypeError, ValueError):
            num = 0

        share = ETFDailyShare(
            sec_code=sec_code,
            stat_date=stat_date,
            tot_vol=tot_vol,
            num=num,
            market='SH',
        )
        db.session.merge(share)
        share_count += 1

        # etf_info 每个 sec_code 当日只 upsert 一次
        if sec_code in seen_codes:
            continue
        seen_codes.add(sec_code)

        sec_name = (r.get('SEC_NAME') or r.get('sec_name') or '').strip() or None
        etf_type = (r.get('ETF_TYPE') or r.get('etf_type') or '').strip() or None

        if sec_name or etf_type:
            info = ETFInfo(
                sec_code=sec_code,
                sec_name=sec_name,
                etf_type=etf_type,
            )
            db.session.merge(info)
            info_count += 1

    db.session.commit()
    return share_count, info_count


# --- 入口 ---
def parse_args() -> int:
    """解析命令行 / 环境变量中的 days。"""
    default_days = int(os.environ.get('FETCH_SSE_DAYS', Config.FETCH_SSE_DAYS))
    if len(sys.argv) > 1:
        try:
            return int(sys.argv[1])
        except ValueError:
            print(f'ERROR: invalid days argument: {sys.argv[1]}')
            sys.exit(1)
    return default_days


def main() -> int:
    days = parse_args()
    started_at = datetime.now()

    print('=== SSE ETF 数据采集 (Phase 2) ===')
    print(f'开始时间: {started_at.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'采集最近 {days} 个工作日数据（覆盖周末/节假日）')

    target_dates = get_recent_workdays(days)
    print(f'目标日期: {target_dates}')

    app = create_app()
    total_shares = 0
    total_infos = 0
    success_dates = 0
    failed_dates: List[str] = []

    with app.app_context():
        with requests.Session() as session:
            for d in target_dates:
                print(f'\n--- {d} ---')
                try:
                    records = fetch_day_data(session, d)
                except Exception as e:
                    print(f'  {d} fetch failed: {e}')
                    failed_dates.append(d)
                    continue

                if not records:
                    print(f'  {d} 无数据（可能非交易日）')
                    continue

                try:
                    s, i = upsert_records(records)
                except Exception as e:
                    print(f'  {d} save error: {e}')
                    db.session.rollback()
                    failed_dates.append(d)
                    continue

                total_shares += s
                total_infos += i
                success_dates += 1
                print(f'  {d} 已保存: {s} 条份额 / {i} 条 ETF 信息')

    ended_at = datetime.now()
    elapsed = (ended_at - started_at).total_seconds()

    print('\n=== 采集完成 ===')
    print(f'结束时间: {ended_at.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'耗时: {elapsed:.1f}s')
    print(f'成功日期: {success_dates}/{len(target_dates)}')
    if failed_dates:
        print(f'失败日期: {failed_dates}')
    print(f'写入 etf_daily_share: {total_shares}')
    print(f'写入 etf_info (去重): {total_infos}')

    return 0 if not failed_dates else 1


if __name__ == '__main__':
    sys.exit(main())
