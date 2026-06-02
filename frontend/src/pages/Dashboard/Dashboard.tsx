import { useQuery } from '@tanstack/react-query'
import {
  getETFRanking,
  getStatsSummary,
  getRisingETFs,
  type ETFRankingItem,
  type StatsSummary,
  type RisingETF,
} from '../../services/api'
import { TrendingUp, Activity, BarChart3, AlertTriangle, ArrowUpRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import './Dashboard.css'

function formatPercent(value?: number): string {
  if (value === undefined || value === null || Number.isNaN(value)) return '--'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function formatNumber(value?: number): string {
  if (value === undefined || value === null) return '--'
  return value.toLocaleString('zh-CN')
}

function formatFreshness(hours?: number): string {
  if (hours === undefined || hours === null) return ''
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))} 分钟前`
  if (hours < 24) return `${Math.round(hours)} 小时前`
  return `${Math.round(hours / 24)} 天前`
}

export default function Dashboard() {
  const navigate = useNavigate()

  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useQuery<StatsSummary>({
    queryKey: ['stats', 'summary'],
    queryFn: () => getStatsSummary(),
  })

  const { data: ranking, isLoading: rankingLoading } = useQuery<ETFRankingItem[]>({
    queryKey: ['ranking', 'tot_vol', 10],
    queryFn: () => getETFRanking('tot_vol', 10),
  })

  const { data: rising, isLoading: risingLoading } = useQuery<RisingETF[]>({
    queryKey: ['rising', 126],
    queryFn: () => getRisingETFs(126),
  })

  const isStale = (stats?.data_freshness_hours ?? 0) > 24
  const isLoading = statsLoading || rankingLoading
  const hasError = !!statsError

  return (
    <div className="dashboard">
      <div className="page-header">
        <h1>ETF 份额概览</h1>
        <div className="header-meta">
          {stats?.latest_date && (
            <span className="update-time">
              数据更新于 {stats.latest_date} · {formatFreshness(stats.data_freshness_hours)}
            </span>
          )}
          {!stats?.latest_date && !statsLoading && (
            <span className="update-time">实时数据</span>
          )}
        </div>
      </div>

      {hasError && (
        <div className="banner banner-error">
          <AlertTriangle size={18} />
          <span>数据加载失败，请稍后重试。</span>
        </div>
      )}

      {isStale && (
        <div className="banner banner-warning">
          <AlertTriangle size={18} />
          <span>数据已超过 24 小时未更新，统计可能滞后，请以官方数据为准。</span>
        </div>
      )}

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon blue"><Activity size={24} /></div>
          <div className="stat-info">
            <span className="stat-label">监控ETF</span>
            {isLoading ? (
              <span className="stat-value skeleton" />
            ) : (
              <span className="stat-value">{formatNumber(stats?.total_etfs)}</span>
            )}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon green"><TrendingUp size={24} /></div>
          <div className="stat-info">
            <span className="stat-label">市场整体变化</span>
            {isLoading ? (
              <span className="stat-value skeleton" />
            ) : (
              <span
                className={`stat-value ${
                  (stats?.market_change_pct ?? 0) >= 0 ? 'positive' : 'negative'
                }`}
              >
                {formatPercent(stats?.market_change_pct)}
              </span>
            )}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon purple"><BarChart3 size={24} /></div>
          <div className="stat-info">
            <span className="stat-label">总份额(亿)</span>
            {isLoading ? (
              <span className="stat-value skeleton" />
            ) : (
              <span className="stat-value">
                {stats?.total_market_cap !== undefined
                  ? (stats.total_market_cap / 1e8).toFixed(2)
                  : '--'}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="section">
        <h2>份额排行 TOP 10</h2>
        <div className="ranking-table">
          {rankingLoading && !ranking ? (
            <div className="skeleton-table">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="skeleton-row" />
              ))}
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>排名</th>
                  <th>代码</th>
                  <th>名称</th>
                  <th>总份额(亿)</th>
                  <th>最新日期</th>
                </tr>
              </thead>
              <tbody>
                {ranking?.map((item, index) => (
                  <tr key={item.sec_code} onClick={() => navigate(`/trend/${item.sec_code}`)}>
                    <td><span className="rank-badge">{index + 1}</span></td>
                    <td className="code">{item.sec_code}</td>
                    <td className="name">{item.sec_name}</td>
                    <td className="volume">{(item.tot_vol / 1e4).toFixed(2)}</td>
                    <td className="date">{item.stat_date}</td>
                  </tr>
                ))}
                {!ranking?.length && !rankingLoading && (
                  <tr>
                    <td colSpan={5} className="empty">暂无数据</td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="section">
        <div className="section-header">
          <h2>份额上升 TOP 10</h2>
          <span className="section-meta">近 126 个交易日</span>
        </div>
        <div className="ranking-table">
          {risingLoading && !rising ? (
            <div className="skeleton-table">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="skeleton-row" />
              ))}
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>排名</th>
                  <th>代码</th>
                  <th>名称</th>
                  <th>起点份额(亿)</th>
                  <th>最新份额(亿)</th>
                  <th>区间涨幅</th>
                  <th>区间</th>
                </tr>
              </thead>
              <tbody>
                {rising?.map((item, index) => (
                  <tr key={item.sec_code} onClick={() => navigate(`/trend/${item.sec_code}`)}>
                    <td><span className="rank-badge">{index + 1}</span></td>
                    <td className="code">{item.sec_code}</td>
                    <td className="name">{item.sec_name}</td>
                    <td className="volume">{(item.start_vol / 1e4).toFixed(2)}</td>
                    <td className="volume">{(item.latest_vol / 1e4).toFixed(2)}</td>
                    <td>
                      <span className={`pct-pill ${item.change_pct >= 0 ? 'positive' : 'negative'}`}>
                        <ArrowUpRight size={12} />
                        {formatPercent(item.change_pct)}
                      </span>
                    </td>
                    <td className="date">{item.start_date} → {item.end_date}</td>
                  </tr>
                ))}
                {!rising?.length && !risingLoading && (
                  <tr>
                    <td colSpan={7} className="empty">暂无数据</td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
