import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getHuijinAnalysis } from '../../services/api'
import { Search, AlertCircle, Info } from 'lucide-react'
import './Huijin.css'

type Mode = 'estimated' | 'actual'

export default function Huijin() {
  const { code } = useParams<{ code: string }>()
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('estimated')
  const [searchCode, setSearchCode] = useState(code || '510330')

  useEffect(() => {
    if (code) {
      setSearchCode(code)
    }
  }, [code])

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['huijin', code, mode],
    queryFn: () => getHuijinAnalysis(code!, mode),
    enabled: !!code,
  })

  const handleSearch = () => {
    const trimmed = searchCode.trim()
    if (trimmed) {
      navigate(`/huijin/${trimmed}`)
    }
  }

  const formatPct = (val?: number) => {
    if (val === undefined || val === null) return '-'
    const sign = val > 0 ? '+' : ''
    return `${sign}${val.toFixed(2)}%`
  }

  const formatVol = (val?: number) => {
    if (val === undefined || val === null) return '-'
    return `${(val / 10000).toFixed(2)}亿`
  }

  const huijinHolders = (data?.holders || []).filter((h) =>
    h.holder_name.includes('汇金') || h.holder_name.includes('中央汇金')
  )

  return (
    <div className="huijin-page">
      <div className="page-header">
        <h1>汇金持仓分析</h1>
        <div className="search-box">
          <input
            value={searchCode}
            onChange={(e) => setSearchCode(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="ETF 代码，如 510330"
          />
          <button onClick={handleSearch}><Search size={16} /></button>
        </div>
      </div>

      <div className="mode-toggle">
        <button
          className={`mode-btn ${mode === 'estimated' ? 'active' : ''}`}
          onClick={() => setMode('estimated')}
        >
          估算
        </button>
        <button
          className={`mode-btn ${mode === 'actual' ? 'active' : ''}`}
          onClick={() => setMode('actual')}
        >
          实际
        </button>
      </div>

      {mode === 'estimated' && (
        <div className="disclaimer">
          <Info size={16} />
          <span>本估算假设持有人占比不变，仅供参考</span>
        </div>
      )}

      {isLoading ? (
        <div className="loading">加载中...</div>
      ) : isError ? (
        <div className="error-card">
          <AlertCircle size={20} />
          <span>加载失败：{String(error)}</span>
        </div>
      ) : data?.error ? (
        <div className="error-card">
          <AlertCircle size={20} />
          <span>{data.error}</span>
        </div>
      ) : (
        <>
          <div className="info-card">
            <div className="info-row">
              <span className="label">ETF 代码</span>
              <span className="value code">{data?.sec_code}</span>
            </div>
            <div className="info-row">
              <span className="label">ETF 名称</span>
              <span className="value">{data?.sec_name}</span>
            </div>
            <div className="info-row">
              <span className="label">模式</span>
              <span className="value">{mode === 'estimated' ? '估算' : '实际'}</span>
            </div>
          </div>

          <div className="comparison-grid">
            <div className="comparison-card">
              <div className="card-label">去年末 ({data?.dec31_holdings !== undefined ? 'Dec 31' : '基准'})</div>
              <div className="card-value">
                {formatVol(data?.dec31_holdings)}
              </div>
            </div>
            <div className="comparison-card">
              <div className="card-label">最新</div>
              <div className="card-value highlight">
                {formatVol(data?.latest_holdings)}
              </div>
            </div>
            <div className="comparison-card">
              <div className="card-label">变化</div>
              <div className={`card-value ${data?.change && data.change > 0 ? 'positive' : 'negative'}`}>
                {data?.change !== undefined ? (data.change / 10000).toFixed(2) + '亿' : '-'}
              </div>
            </div>
            <div className="comparison-card">
              <div className="card-label">变化幅度</div>
              <div className={`card-value ${data?.change_pct && data.change_pct > 0 ? 'positive' : 'negative'}`}>
                {formatPct(data?.change_pct)}
              </div>
            </div>
          </div>

          <div className="holders-section">
            <h2>汇金相关持有人</h2>
            {huijinHolders.length === 0 ? (
              <div className="empty">未发现汇金相关持仓</div>
            ) : (
              <div className="holders-table">
                <table>
                  <thead>
                    <tr>
                      <th>持有人</th>
                      <th>占比</th>
                    </tr>
                  </thead>
                  <tbody>
                    {huijinHolders.map((h, i) => (
                      <tr key={i}>
                        <td>{h.holder_name}</td>
                        <td className="ratio">{h.hold_ratio.toFixed(2)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
