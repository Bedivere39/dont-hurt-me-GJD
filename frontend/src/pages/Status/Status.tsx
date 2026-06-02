import { useQuery } from '@tanstack/react-query'
import { getDataStatus } from '../../services/api'
import { Database, CheckCircle2, AlertTriangle } from 'lucide-react'
import './Status.css'

export default function Status() {
  const { data, isLoading } = useQuery({
    queryKey: ['data-status'],
    queryFn: () => getDataStatus(30),
  })

  const okCount = data?.daily_counts.filter((d) => d.status === 'OK').length || 0
  const lowCount = data?.daily_counts.filter((d) => d.status === 'LOW').length || 0

  return (
    <div className="status-page">
      <div className="page-header">
        <h1>数据状态</h1>
        <span className="update-time">数据完整性监控</span>
      </div>

      {isLoading ? (
        <div className="loading">加载中...</div>
      ) : (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-icon blue"><Database size={24} /></div>
              <div className="stat-info">
                <span className="stat-label">最新数据日期</span>
                <span className="stat-value">{data?.latest_date || '-'}</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon green"><CheckCircle2 size={24} /></div>
              <div className="stat-info">
                <span className="stat-label">正常天数</span>
                <span className="stat-value positive">{okCount}</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon red"><AlertTriangle size={24} /></div>
              <div className="stat-info">
                <span className="stat-label">数据偏少</span>
                <span className="stat-value negative">{lowCount}</span>
              </div>
            </div>
          </div>

          <div className="section">
            <h2>每日数据量</h2>
            <div className="status-table">
              <table>
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>记录数</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.daily_counts.map((item) => (
                    <tr key={item.date}>
                      <td className="date">{item.date}</td>
                      <td className="count">{item.count}</td>
                      <td>
                        <span className={`status-pill ${item.status === 'OK' ? 'ok' : 'low'}`}>
                          {item.status === 'OK' ? '正常' : '偏少'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
