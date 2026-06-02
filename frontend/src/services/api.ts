// Vite 在构建时注入 VITE_API_BASE；本地开发默认走 :8000
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || 'http://localhost:8000/api'

interface FetchOptions {
  method?: string
  body?: unknown
}

interface ETFItem {
  sec_code: string
  sec_name: string
  full_name?: string
  etf_type?: string
}

interface ETFListResponse {
  items: ETFItem[]
  total: number
}

export interface ETFRankingItem {
  sec_code: string
  sec_name: string
  etf_type?: string
  tot_vol: number
  stat_date: string
  change?: number
  change_pct?: number
}

interface ETFTrendItem {
  date: string
  tot_vol: number
  close_price: number
}

interface ETFHolderItem {
  holder_name: string
  hold_volume: number
  hold_ratio: number
}

interface ETFHoldersResponse {
  sec_code: string
  sec_name?: string
  holders: ETFHolderItem[]
  stat_date: string
}

interface HoldersByTypeItem {
  sec_code: string
  full_name: string
  sec_name: string
  holder_name: string
  hold_ratio: number
  stat_date: string
}

interface HuijinHolder {
  holder_name: string
  hold_ratio: number
}

interface HuijinAnalysis {
  sec_code: string
  sec_name: string
  mode: 'estimated' | 'actual'
  holders: HuijinHolder[]
  dec31_holdings?: number
  latest_holdings?: number
  change?: number
  change_pct?: number
  disclaimer?: string
  error?: string
}

export interface StatsSummary {
  total_etfs: number
  total_records: number
  latest_date: string
  prev_date: string
  total_market_cap: number
  total_market_cap_change: number
  market_change_pct: number
  data_freshness_hours: number
}

export interface RisingETF {
  sec_code: string
  sec_name: string
  etf_type?: string
  start_vol: number
  latest_vol: number
  change_pct: number
  start_date: string
  end_date: string
}

interface SecuritiesItem {
  sec_code: string
  sec_name: string
  full_name: string
  tot_vol: number
  stat_date: string
  change?: number
  change_pct?: number
}

interface DataStatus {
  latest_date: string
  daily_counts: Array<{
    date: string
    count: number
    status: 'OK' | 'LOW'
  }>
}

export async function fetchAPI<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { method = 'GET', body } = options

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`)
  }

  return response.json()
}

export async function getETFList(page = 1, perPage = 20): Promise<ETFListResponse> {
  return fetchAPI<ETFListResponse>(`/etf/list?page=${page}&per_page=${perPage}`)
}

export async function getETFRanking(
  sortBy: 'tot_vol' | 'change' | 'pct' = 'tot_vol',
  limit = 10
): Promise<ETFRankingItem[]> {
  return fetchAPI<ETFRankingItem[]>(`/etf/ranking?sort_by=${sortBy}&limit=${limit}`)
}

export async function getETFTrend(code: string, days = 30): Promise<ETFTrendItem[]> {
  return fetchAPI<ETFTrendItem[]>(`/etf/${code}/trend?days=${days}`)
}

export async function compareETF(codes: string[], days = 30): Promise<Record<string, ETFTrendItem[]>> {
  return fetchAPI<Record<string, ETFTrendItem[]>>(`/etf/compare?codes=${codes.join(',')}&days=${days}`)
}

export async function getETFHolders(code: string): Promise<ETFHoldersResponse> {
  return fetchAPI<ETFHoldersResponse>(`/etf/${code}/holders`)
}

export async function getHoldersByType(
  type: string,
  minPct = 0.5
): Promise<HoldersByTypeItem[]> {
  const encoded = encodeURIComponent(type)
  return fetchAPI<HoldersByTypeItem[]>(
    `/etf/holders-by-type?type=${encoded}&min_pct=${minPct}`
  )
}

export async function getHuijinAnalysis(
  code: string,
  mode: 'estimated' | 'actual' = 'estimated'
): Promise<HuijinAnalysis> {
  return fetchAPI<HuijinAnalysis>(`/etf/${code}/huijin?mode=${mode}`)
}

export async function getSecurities(
  sortBy: 'tot_vol' | 'change' | 'pct' = 'tot_vol',
  limit = 50
): Promise<SecuritiesItem[]> {
  return fetchAPI<SecuritiesItem[]>(`/etf/securities?sort_by=${sortBy}&limit=${limit}`)
}

export async function getDataStatus(days = 30): Promise<DataStatus> {
  return fetchAPI<DataStatus>(`/etf/data-status?days=${days}`)
}

export async function getStatsSummary(): Promise<StatsSummary> {
  return fetchAPI<StatsSummary>(`/etf/stats/summary`)
}

export async function getRisingETFs(days = 126): Promise<RisingETF[]> {
  return fetchAPI<RisingETF[]>(`/etf/rising?days=${days}`)
}
