"""部署后端到端验证脚本

用法:
    python scripts/post_deploy_verify.py [--base https://bedivere.space]
    python scripts/post_deploy_verify.py --base http://localhost:8000

校验:
    1. /api/health 返回 ok
    2. /api/etf/stats/summary 数据合理（total_etfs > 0, latest_date <= 今天）
    3. /api/etf/ranking 返回非空列表
    4. /api/etf/rising 端点存在且返回数据
    5. /api/etf/data-status 端点存在
    6. /api/etf/securities 返回非空列表
    7. /api/etf/<code>/holders 抽样 1 个 ETF（512880）有持有人
    8. /api/etf/<code>/huijin 抽样 1 个 ETF（510330）有响应
    9. 前端首页可访问

退出码: 0 全部通过 / 1 至少一项失败
"""
import argparse
import json
import sys
import time
from datetime import date, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class Checker:
    def __init__(self, base: str):
        self.base = base.rstrip('/')
        self.results: list[tuple[str, str, str]] = []  # (status, name, detail)
        self.fail_count = 0

    def add(self, ok: bool, name: str, detail: str = ''):
        status = '✓ PASS' if ok else '✗ FAIL'
        self.results.append((status, name, detail))
        if not ok:
            self.fail_count += 1

    def get(self, path: str, params: dict | None = None, timeout: int = 15):
        url = f'{self.base}{path}'
        if params:
            url += '?' + urlencode(params)
        try:
            req = Request(url, headers={'User-Agent': 'post-deploy-verify/1.0'})
            with urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read().decode('utf-8'))
        except HTTPError as e:
            try:
                body = e.read().decode('utf-8')
            except Exception:
                body = ''
            return e.code, {'error': body}
        except (URLError, TimeoutError, json.JSONDecodeError) as e:
            return 0, {'error': str(e)}

    def head(self, path: str, timeout: int = 10) -> int:
        url = f'{self.base}{path}'
        try:
            req = Request(url, method='HEAD', headers={'User-Agent': 'post-deploy-verify/1.0'})
            with urlopen(req, timeout=timeout) as resp:
                return resp.status
        except HTTPError as e:
            return e.code
        except (URLError, TimeoutError):
            return 0

    def run(self):
        print(f'部署后验证 - 目标: {self.base}')
        print(f'时间: {datetime.now().isoformat(timespec="seconds")}')
        print('=' * 60)

        # 1. Health
        status, body = self.get('/api/health')
        self.add(
            status == 200 and body.get('status') == 'ok',
            '1. /api/health',
            f'status={status}, body={body}',
        )

        # 2. Stats summary
        status, body = self.get('/api/etf/stats/summary')
        if status == 200 and isinstance(body, dict):
            total_etfs = body.get('total_etfs', 0)
            latest_date = body.get('latest_date', '')
            freshness_h = body.get('data_freshness_hours', 999)
            ok = total_etfs > 0
            if latest_date:
                try:
                    ld = datetime.strptime(latest_date, '%Y-%m-%d').date()
                    days_stale = (date.today() - ld).days
                    # A股市场: 周一到周五开盘, 周末/节假日数据不变
                    # 接受 ≤ 7 天的陈旧(覆盖国庆/春节长假)
                    if days_stale > 7:
                        ok = False
                except ValueError:
                    pass
            self.add(ok, '2. /api/etf/stats/summary', f'{total_etfs} 只 ETF, 最新={latest_date}, 陈旧={freshness_h:.1f}h')
        else:
            self.add(False, '2. /api/etf/stats/summary', f'status={status}, body={body}')

        # 3. Ranking
        status, body = self.get('/api/etf/ranking', {'sort_by': 'tot_vol', 'limit': 10})
        if status == 200 and isinstance(body, list):
            self.add(len(body) > 0, '3. /api/etf/ranking', f'{len(body)} 条记录, 首条: {body[0].get("sec_code") if body else "N/A"}')
        else:
            self.add(False, '3. /api/etf/ranking', f'status={status}')

        # 4. Rising
        status, body = self.get('/api/etf/rising', {'days': 126})
        if status == 200 and isinstance(body, list):
            self.add(len(body) > 0, '4. /api/etf/rising', f'{len(body)} 条份额上升的 ETF')
        else:
            self.add(False, '4. /api/etf/rising', f'status={status}')

        # 5. Data status
        status, body = self.get('/api/etf/data-status', {'days': 7})
        if status == 200 and isinstance(body, dict):
            daily = body.get('daily_counts', [])
            ok_count = sum(1 for d in daily if d.get('status') == 'OK')
            self.add(len(daily) > 0, '5. /api/etf/data-status', f'{len(daily)} 天数据, {ok_count} 天 OK')
        else:
            self.add(False, '5. /api/etf/data-status', f'status={status}')

        # 6. Securities
        status, body = self.get('/api/etf/securities', {'sort_by': 'volume', 'limit': 20})
        if status == 200 and isinstance(body, list):
            self.add(len(body) > 0, '6. /api/etf/securities', f'{len(body)} 只证券/保险 ETF')
        else:
            self.add(False, '6. /api/etf/securities', f'status={status}')

        # 7. Holders (sample 512880)
        status, body = self.get('/api/etf/512880/holders')
        if status == 200 and isinstance(body, dict):
            holders = body.get('holders', [])
            self.add(len(holders) > 0, '7. /api/etf/512880/holders', f'{len(holders)} 个持有人, 报告期 {body.get("stat_date")}')
        elif status == 200 and 'error' in body:
            self.add(False, '7. /api/etf/512880/holders', f'返回错误: {body["error"]}')
        else:
            self.add(False, '7. /api/etf/512880/holders', f'status={status}')

        # 8. Huijin (sample 510330)
        for mode in ('estimated', 'actual'):
            status, body = self.get('/api/etf/510330/huijin', {'mode': mode})
            label = f'8. /api/etf/510330/huijin?mode={mode}'
            if status == 200 and isinstance(body, dict):
                holders = body.get('holders', [])
                err = body.get('error')
                if err:
                    # actual 模式在年报数据不足时正确返回 error
                    # （持有人表通常只有最近一期年报），这视为 API 健康
                    if mode == 'actual' and 'Not enough data' in err:
                        self.add(True, label, f'actual 模式数据不足（年报周期）→ API 正确返回 error: {err[:60]}')
                    else:
                        self.add(False, label, f'API 返回 error: {err[:80]}')
                else:
                    self.add(True, label, f'mode={mode}, {len(holders)} 个持有人, change={body.get("change", "N/A")}')
            else:
                self.add(False, label, f'status={status}')

        # 9. Frontend index
        status = self.head('/')
        self.add(status == 200, '9. GET / (frontend)', f'status={status}')

        # 10. Specific Trend page
        status = self.head('/trend/512880')
        self.add(status == 200, '10. GET /trend/512880 (frontend SPA)', f'status={status}')

        return self.report()

    def report(self) -> int:
        print()
        for status, name, detail in self.results:
            line = f'{status}  {name}'
            if detail:
                line += f'  →  {detail}'
            print(line)
        print('=' * 60)
        total = len(self.results)
        passed = total - self.fail_count
        print(f'汇总: {passed}/{total} 通过')
        if self.fail_count == 0:
            print('✅ 部署验证全部通过')
            return 0
        print(f'❌ {self.fail_count} 项失败，请检查日志')
        return 1


def main():
    parser = argparse.ArgumentParser(description='部署后端到端验证')
    parser.add_argument('--base', default='https://bedivere.space', help='API base URL (default: https://bedivere.space)')
    args = parser.parse_args()
    checker = Checker(args.base)
    sys.exit(checker.run())


if __name__ == '__main__':
    main()
