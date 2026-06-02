import { useQuery } from '@tanstack/react-query'
import { getETFRanking, type ETFRankingItem } from '../../services/api'
import { useNavigate, useSearchParams } from 'react-router-dom'
import './Ranking.css'

type SortKey = 'tot_vol' | 'change' | 'pct'

const TABS: { key: SortKey; label: string }[] = [
  { key: 'tot_vol', label: '份额最大' },
  { key: 'change', label: '份额增加最多' },
  { key: 'pct', label: '份额增幅最多' },
]

function formatVol(vol: number): string {
  return `${(vol / 1e4).toFixed(2)}亿`
}

function formatSigned(value?: number, digits = 2): string {
  if (value === undefined || value === null || Number.isNaN(value)) return '--'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(digits)}`
}

function isValidSort(value: string | null): value is SortKey {
  return value === 'tot_vol' || value === 'change' || value === 'pct'
}

export default function Ranking() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const sortParam = searchParams.get('sort')
  const sortBy: SortKey = isValidSort(sortParam) ? sortParam : 'tot_vol'

  const { data, isLoading, error } = useQuery<ETFRankingItem[]>({
    queryKey: ['ranking', sortBy, 50],
    queryFn: () => getETFRanking(sortBy, 50),
  })

  const handleTabChange = (next: SortKey) => {
    const params = new URLSearchParams(searchParams)
    if (next === 'tot_vol') {
      params.delete('sort')
    } else {
      params.set('sort', next)
    }
    setSearchParams(params, { replace: true })
  }

  const showChange = sortBy !== 'tot_vol'

  return (
    <div className="ranking-page">
      <h1>ETF 份额排行榜</h1>

      <div className="tab-bar" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={sortBy === tab.key}
            className={`tab-button ${sortBy === tab.key ? 'active' : ''}`}
            onClick={() => handleTabChange(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="ranking-error">数据加载失败，请稍后重试。</div>
      )}

      {isLoading && !data ? (
        <div className="ranking-grid">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="ranking-card skeleton-card" />
          ))}
        </div>
      ) : (
        <div className="ranking-grid">
          {data?.map((item, index) => (
            <div
              key={item.sec_code}
              className="ranking-card"
              onClick={() => navigate(`/trend/${item.sec_code}`)}
            >
              <div className="rank">#{index + 1}</div>
              <div className="info">
                <div className="name">{item.sec_name}</div>
                <div className="code">{item.sec_code}</div>
                {showChange && (
                  <div className="change-row">
                    <span className="vol-text">{formatVol(item.tot_vol)}</span>
                    {item.change_pct !== undefined && (
                      <span
                        className={`change-pill ${
                          item.change_pct >= 0 ? 'positive' : 'negative'
                        }`}
                      >
                        {formatSigned(item.change_pct)}
                      </span>
                    )}
                  </div>
                )}
              </div>
              {!showChange && (
                <div className="vol">{formatVol(item.tot_vol)}</div>
              )}
            </div>
          ))}
          {!data?.length && !isLoading && (
            <div className="ranking-empty">暂无数据</div>
          )}
        </div>
      )}
    </div>
  )
}
