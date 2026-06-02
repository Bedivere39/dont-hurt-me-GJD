import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getSecurities } from '../../services/api'
import './Securities.css'

type SortBy = 'tot_vol' | 'change' | 'pct'

const TABS: { key: SortBy; label: string }[] = [
  { key: 'tot_vol', label: '按份额' },
  { key: 'change', label: '按变化' },
  { key: 'pct', label: '按增幅' },
]

export default function Securities() {
  const [sortBy, setSortBy] = useState<SortBy>('tot_vol')
  const navigate = useNavigate()

  const { data, isLoading } = useQuery({
    queryKey: ['securities', sortBy],
    queryFn: () => getSecurities(sortBy, 50),
  })

  const showChange = sortBy !== 'tot_vol'

  const formatChange = (val?: number) => {
    if (val === undefined || val === null) return '-'
    const sign = val > 0 ? '+' : ''
    return `${sign}${(val / 10000).toFixed(2)}亿`
  }

  const formatPct = (val?: number) => {
    if (val === undefined || val === null) return '-'
    const sign = val > 0 ? '+' : ''
    return `${sign}${val.toFixed(2)}%`
  }

  return (
    <div className="securities-page">
      <div className="page-header">
        <h1>证券 ETF 份额</h1>
        <span className="update-time">{data?.length || 0} 个标的</span>
      </div>

      <div className="tab-bar">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`tab ${sortBy === tab.key ? 'active' : ''}`}
            onClick={() => setSortBy(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="loading">加载中...</div>
      ) : (
        <div className="securities-table">
          <table>
            <thead>
              <tr>
                <th>排名</th>
                <th>代码</th>
                <th>名称</th>
                <th>总份额(亿)</th>
                {showChange && <th>变化</th>}
                {showChange && <th>增幅</th>}
                <th>最新日期</th>
              </tr>
            </thead>
            <tbody>
              {data?.map((item, index) => (
                <tr key={item.sec_code} onClick={() => navigate(`/huijin/${item.sec_code}`)}>
                  <td><span className="rank-badge">{index + 1}</span></td>
                  <td className="code">{item.sec_code}</td>
                  <td className="name">{item.full_name || item.sec_name}</td>
                  <td className="volume">{(item.tot_vol / 10000).toFixed(2)}</td>
                  {showChange && (
                    <td className={`change ${item.change && item.change > 0 ? 'positive' : 'negative'}`}>
                      {formatChange(item.change)}
                    </td>
                  )}
                  {showChange && (
                    <td className={`pct ${item.change_pct && item.change_pct > 0 ? 'positive' : 'negative'}`}>
                      {formatPct(item.change_pct)}
                    </td>
                  )}
                  <td className="date">{item.stat_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
