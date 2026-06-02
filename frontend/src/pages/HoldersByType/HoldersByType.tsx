import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getHoldersByType } from '../../services/api'
import './HoldersByType.css'

type SortDir = 'asc' | 'desc'

export default function HoldersByType() {
  const [type, setType] = useState('汇金')
  const [minPct, setMinPct] = useState(0.5)
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [submittedType, setSubmittedType] = useState('汇金')

  const { data, isLoading, isError, error, isFetching, refetch } = useQuery({
    queryKey: ['holders-by-type', submittedType, minPct],
    queryFn: () => getHoldersByType(submittedType, minPct),
  })

  const onSearch = () => {
    if (type.trim()) {
      setSubmittedType(type.trim())
    }
  }

  const toggleSort = () => {
    setSortDir((prev) => (prev === 'desc' ? 'asc' : 'desc'))
  }

  const sorted = (data ?? [])
    .slice()
    .sort((a, b) =>
      sortDir === 'desc'
        ? (b.hold_ratio ?? 0) - (a.hold_ratio ?? 0)
        : (a.hold_ratio ?? 0) - (b.hold_ratio ?? 0)
    )

  return (
    <div className="holders-by-type-page">
      <h1>持有人按类别查询</h1>
      <div className="search-bar">
        <div className="search-field">
          <label>持有人关键字</label>
          <input
            type="text"
            value={type}
            onChange={(e) => setType(e.target.value)}
            placeholder="如：汇金 / 社保 / 保险"
            onKeyDown={(e) => e.key === 'Enter' && onSearch()}
          />
        </div>
        <div className="search-field small">
          <label>最小比例 (%)</label>
          <input
            type="number"
            min={0}
            step={0.1}
            value={minPct}
            onChange={(e) => setMinPct(Number(e.target.value) || 0)}
          />
        </div>
        <button className="search-btn" onClick={onSearch} disabled={isFetching}>
          {isFetching ? '查询中...' : '查询'}
        </button>
      </div>

      {isLoading ? (
        <div className="loading">加载中...</div>
      ) : isError ? (
        <div className="error-state">
          加载失败：{(error as Error)?.message ?? '未知错误'}
          <button className="retry-btn" onClick={() => refetch()}>重试</button>
        </div>
      ) : (
        <div className="data-table">
          <div className="table-meta">
            关键字 "<span className="accent">{submittedType}</span>" 匹配
            <span className="accent"> {sorted.length} </span>
            条记录（最小比例 {minPct}%）
          </div>
          {sorted.length === 0 ? (
            <div className="empty-state">未找到匹配记录</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>ETF 代码</th>
                  <th>简称</th>
                  <th>全称</th>
                  <th>持有人</th>
                  <th
                    className="sortable"
                    onClick={toggleSort}
                    title="点击排序"
                  >
                    持有比例 (%)
                    <span className="sort-indicator">
                      {sortDir === 'desc' ? ' ↓' : ' ↑'}
                    </span>
                  </th>
                  <th>数据日期</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((row, idx) => (
                  <tr key={`${row.sec_code}-${row.holder_name}-${idx}`}>
                    <td className="numeric">{row.sec_code}</td>
                    <td>{row.sec_name}</td>
                    <td className="full-name">{row.full_name}</td>
                    <td className="holder-name">{row.holder_name}</td>
                    <td className="numeric ratio">{(row.hold_ratio ?? 0).toFixed(2)}</td>
                    <td className="numeric">{row.stat_date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
