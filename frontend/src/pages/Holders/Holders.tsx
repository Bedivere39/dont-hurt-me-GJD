import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getETFHolders } from '../../services/api'
import './Holders.css'

export default function Holders() {
  const { code } = useParams<{ code: string }>()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['holders', code],
    queryFn: () => getETFHolders(code!),
    enabled: !!code,
  })

  if (isLoading) return <div className="loading">加载中...</div>

  if (isError) {
    return (
      <div className="holders-page">
        <div className="error-state">加载失败：{(error as Error)?.message ?? '未知错误'}</div>
      </div>
    )
  }

  const secName = data?.sec_name ?? `ETF ${code}`
  const statDate = data?.stat_date ?? '-'
  const holders = data?.holders ?? []

  return (
    <div className="holders-page">
      <div className="holders-header">
        <h1>{secName} 十大持有人</h1>
        <div className="holders-subtitle">数据日期：{statDate}</div>
      </div>

      <div className="data-table">
        {holders.length === 0 ? (
          <div className="empty-state">暂无持有人数据</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th style={{ width: 80 }}>排名</th>
                <th>持有人名称</th>
                <th style={{ width: 160 }}>持有比例 (%)</th>
                <th style={{ width: 180 }}>持有份额 (万份)</th>
              </tr>
            </thead>
            <tbody>
              {holders.map((h, idx) => (
                <tr key={`${h.holder_name}-${idx}`}>
                  <td>{idx + 1}</td>
                  <td className="holder-name">{h.holder_name}</td>
                  <td className="numeric">{(h.hold_ratio ?? 0).toFixed(2)}</td>
                  <td className="numeric">{(h.hold_volume ?? 0).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
