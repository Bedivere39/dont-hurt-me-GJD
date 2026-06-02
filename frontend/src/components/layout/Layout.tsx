import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  BarChart3,
  GitCompare,
  TrendingUp,
  Briefcase,
  Users,
  Activity,
  Search,
} from 'lucide-react'
import './Layout.css'

const ETF_CODE_REGEX = /^\d{6}$/

export default function Layout() {
  const navigate = useNavigate()
  const [searchValue, setSearchValue] = useState('')

  const onSearchKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter') return
    const value = searchValue.trim()
    if (!value) return
    if (ETF_CODE_REGEX.test(value)) {
      navigate(`/trend/${value}`)
      setSearchValue('')
    }
  }

  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="logo">
          <TrendingUp className="logo-icon" size={28} />
          <span>ETF 分析</span>
        </div>
        <div className="nav-links">
          <div className="nav-group">
            <div className="nav-group-title">数据分析</div>
            <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              <LayoutDashboard size={20} />
              <span>首页</span>
            </NavLink>
            <NavLink to="/ranking" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              <BarChart3 size={20} />
              <span>排行榜</span>
            </NavLink>
            <NavLink to="/securities" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              <Briefcase size={20} />
              <span>证券 ETF</span>
            </NavLink>
            <NavLink to="/compare" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              <GitCompare size={20} />
              <span>对比分析</span>
            </NavLink>
          </div>
          <div className="nav-group">
            <div className="nav-group-title">持有人分析</div>
            <NavLink to="/holders-by-type" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              <Users size={20} />
              <span>持有人查询</span>
            </NavLink>
          </div>
          <div className="nav-group">
            <div className="nav-group-title">系统</div>
            <NavLink to="/status" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              <Activity size={20} />
              <span>数据状态</span>
            </NavLink>
          </div>
        </div>
        <div className="sidebar-footer">
          <span className="version">v1.1.0</span>
        </div>
      </nav>
      <main className="content">
        <div className="content-toolbar">
          <div className="global-search">
            <Search size={16} className="global-search-icon" />
            <input
              type="text"
              className="global-search-input"
              placeholder="输入 6 位 ETF 代码，回车查看趋势"
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              onKeyDown={onSearchKeyDown}
              maxLength={6}
            />
          </div>
        </div>
        <Outlet />
      </main>
    </div>
  )
}
