import { useState, useEffect, useCallback } from 'react'
import PortfolioTable from './components/PortfolioTable'
import SettingsModal from './components/SettingsModal'
import PipelinePanel from './components/PipelinePanel'
import AlertModal from './components/AlertModal'
import ResultCard, { type PipelineResult } from './components/ResultCard'
import './App.css'

interface RowData {
  ticker: string
  d1: number
  w1: number
}

interface PortfolioData {
  trading_date: string
  latest_date: string
  rows: RowData[]
  names: Record<string, string>
  highlight: string | null
}

export default function App() {
  const [data, setData]                 = useState<PortfolioData | null>(null)
  const [loading, setLoading]           = useState(true)
  const [error, setError]               = useState<string | null>(null)
  const [selectedDate, setSelectedDate] = useState('')
  const [latestDate, setLatestDate]     = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [showPipeline, setShowPipeline] = useState(false)
  const [alertMsg, setAlertMsg]         = useState('')
  const [pipelineResult, setPipelineResult] = useState<PipelineResult | null>(null)

  const loadPortfolio = useCallback(async (dateParam?: string) => {
    setLoading(true)
    setError(null)
    setPipelineResult(null)
    try {
      const url = dateParam ? `/api/portfolio?date=${dateParam}` : '/api/portfolio'
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json: PortfolioData = await res.json()
      setData(json)
      setLatestDate(json.latest_date)
      setSelectedDate(json.trading_date)
      fetchPipelineResult(json.trading_date)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchPipelineResult = useCallback(async (date: string) => {
    try {
      const res = await fetch(`/api/pipeline/result/by-date?date=${date}`)
      setPipelineResult(res.ok ? await res.json() : null)
    } catch {
      setPipelineResult(null)
    }
  }, [])

  useEffect(() => { loadPortfolio() }, [loadPortfolio])

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    if (!val) return
    if (latestDate && val > latestDate) {
      setAlertMsg(`${latestDate} 이후 날짜는 선택할 수 없습니다.`)
      setSelectedDate(latestDate)
      return
    }
    setSelectedDate(val)
    loadPortfolio(val)
  }

  const d1Rows = data ? [...data.rows].sort((a, b) => b.d1 - a.d1) : []
  const w1Rows = data ? [...data.rows].sort((a, b) => b.w1 - a.w1) : []
  const avg    = data && data.rows.length > 0
    ? data.rows.reduce((s, r) => s + r.d1, 0) / data.rows.length
    : 0
  const adv    = data ? data.rows.filter(r => r.d1 >= 0).length : 0

  return (
    <>
      <header className="header">
        <div>
          <div className="brand">Core Sixteen</div>
          <h1>BOBP Portfolio Returns</h1>
        </div>
        <div className="header-right">
          <input
            type="date"
            className="date-input"
            value={selectedDate}
            onChange={handleDateChange}
          />
          <button
            className="btn btn-primary"
            onClick={() => setShowPipeline(true)}
            disabled={loading || !data?.highlight}
            title={!data?.highlight ? '선정 조건을 만족하는 종목이 없습니다' : undefined}
          >
            ▶ Run Pipeline
          </button>
          <button className="btn" onClick={() => setShowSettings(true)}>
            ⚙ Settings
          </button>
        </div>
      </header>

      <div className="stats">
        <div className="stat-card">
          <div className="stat-label">Date</div>
          <div className="stat-value" style={{ fontSize: '15px', letterSpacing: '.01em' }}>
            {loading ? '…' : data ? data.trading_date : '—'}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Holdings</div>
          <div className="stat-value">{loading ? '…' : data ? data.rows.length : '—'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Avg 1D Return</div>
          <div className="stat-value" style={{ color: avg >= 0 ? '#0a9e5c' : '#d93025' }}>
            {loading ? '…' : data ? (avg >= 0 ? '+' : '') + avg.toFixed(2) + '%' : '—'}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Advancing</div>
          <div className="stat-value" style={{ color: '#0a9e5c' }}>{loading ? '…' : data ? adv : '—'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Declining</div>
          <div className="stat-value" style={{ color: '#d93025' }}>{loading ? '…' : data ? data.rows.length - adv : '—'}</div>
        </div>
      </div>

      {loading && <div className="loading">Loading portfolio data…</div>}
      {error   && <div className="loading error">Failed to load: {error}</div>}

      {data && !loading && (
        <div className="tables-row">
          <PortfolioTable
            title="1D Return"
            rows={d1Rows}
            field="d1"
            names={data.names}
            highlight={data.highlight}
          />
          <PortfolioTable
            title="5D Return"
            rows={w1Rows}
            field="w1"
            names={data.names}
            highlight={data.highlight}
          />
        </div>
      )}

      {pipelineResult && <ResultCard result={pipelineResult} />}

      <footer className="footer">
        1D = daily return · 5D = 5-business-day return · BOBP excludes BIL · Data via Yahoo Finance
      </footer>

      {showSettings && (
        <SettingsModal onClose={() => setShowSettings(false)} />
      )}

      {alertMsg && (
        <AlertModal message={alertMsg} onClose={() => setAlertMsg('')} />
      )}

      <PipelinePanel
        open={showPipeline}
        onClose={() => setShowPipeline(false)}
        date={selectedDate}
        ticker={data?.highlight ?? undefined}
        onComplete={fetchPipelineResult}
      />
    </>
  )
}
