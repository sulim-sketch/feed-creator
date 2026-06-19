import { useState, useRef, useEffect } from 'react'
import styles from './PipelinePanel.module.css'

interface PipelinePanelProps {
  open: boolean
  onClose: () => void
  date?: string
  ticker?: string
  onComplete?: (date: string) => void
}

type LineType = 'info' | 'done' | 'error' | 'default'

interface LogLine {
  text: string
  type: LineType
}

interface Article {
  title: string
  url: string
  publisher: string
  published_et?: string
  body?: string
}

interface PipelineResult {
  ticker: string
  trading_date: string
  return_pct: number
  summary_x: string
  summary_linkedin: string
  articles: Article[]
}

export default function PipelinePanel({ open, onClose, date, ticker, onComplete }: PipelinePanelProps) {
  const [lines, setLines]     = useState<LogLine[]>([])
  const [running, setRunning] = useState(false)
  const [result, setResult]   = useState<PipelineResult | null>(null)
  const [copied, setCopied]   = useState<'x' | 'linkedin' | null>(null)
  const logRef                = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [lines])

  useEffect(() => {
    if (!open) return
    setLines([{ text: 'Starting pipeline…', type: 'info' }])
    setResult(null)
    setRunning(true)

    fetch('/api/pipeline/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...(date && { date }), ...(ticker && { ticker }) }),
    }).then(res => {
      const reader = res.body!.getReader()
      const dec    = new TextDecoder()
      let allLines: LogLine[] = []

      const read = () => reader.read().then(({ done, value }) => {
        if (done) { setRunning(false); return }
        dec.decode(value).split('\n').forEach(line => {
          if (!line.startsWith('data: ')) return
          const msg = line.slice(6)
          if (!msg) return
          const type: LineType = msg.startsWith('[EXIT:0]') ? 'done'
                               : msg.startsWith('[EXIT:')   ? 'error'
                               : 'default'
          const entry: LogLine = { text: msg, type }
          allLines = [...allLines, entry]
          setLines([...allLines])

          if (msg.startsWith('[EXIT:0]')) {
            const completeLine = allLines.find(l => l.text.startsWith('완료: '))
            const match = completeLine?.text.match(/완료:\s+(\S+\.json)/)
            if (match) {
              fetch(`/api/pipeline/result?file=${encodeURIComponent(match[1])}`)
                .then(r => r.json())
                .then((data: PipelineResult) => {
                  setResult(data)
                  onComplete?.(data.trading_date)
                })
                .catch(() => {})
            }
          }
        })
        read()
      })
      read()
    }).catch((e: Error) => {
      setLines(prev => [...prev, { text: `Error: ${e.message}`, type: 'error' }])
      setRunning(false)
    })
  }, [open])

  const copy = (text: string, key: 'x' | 'linkedin') => {
    navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
  }

  const formatTime = (iso?: string) => {
    if (!iso) return ''
    try {
      const d = new Date(iso)
      return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'America/New_York' }) + ' ET'
    } catch { return '' }
  }

  return (
    <div className={`${styles.panel} ${open ? styles.open : ''}`}>
      <div className={styles.header}>
        <span>Pipeline Output {running && <span className={styles.dot}>●</span>}</span>
        <button className={styles.close} onClick={onClose}>✕</button>
      </div>

      <div className={result ? styles.logSmall : styles.log} ref={logRef}>
        {lines.map((l, i) => (
          <div key={i} className={styles[l.type] || ''}>
            {l.text}
          </div>
        ))}
      </div>

      {result && (
        <div className={styles.result}>
          <div className={styles.resultHeader}>
            <span className={styles.tickerBadge}>${result.ticker}</span>
            <span className={styles.returnBadge}>+{result.return_pct.toFixed(2)}%</span>
            <span className={styles.dateBadge}>{result.trading_date}</span>
          </div>

          <div className={styles.section}>
            <div className={styles.sectionLabel}>
              <span>X / Twitter</span>
              <button className={styles.copyBtn} onClick={() => copy(result.summary_x, 'x')}>
                {copied === 'x' ? '✓ Copied' : 'Copy'}
              </button>
            </div>
            <p className={styles.summaryText}>{result.summary_x}</p>
          </div>

          <div className={styles.section}>
            <div className={styles.sectionLabel}>
              <span>LinkedIn</span>
              <button className={styles.copyBtn} onClick={() => copy(result.summary_linkedin, 'linkedin')}>
                {copied === 'linkedin' ? '✓ Copied' : 'Copy'}
              </button>
            </div>
            <p className={styles.summaryText}>{result.summary_linkedin}</p>
          </div>

          <div className={styles.section}>
            <div className={styles.sectionLabel}>
              <span>Articles ({result.articles.length})</span>
            </div>
            <ul className={styles.articleList}>
              {result.articles.map((a, i) => (
                <li key={i} className={styles.articleItem}>
                  <a href={a.url} target="_blank" rel="noreferrer" className={styles.articleTitle}>
                    {a.title}
                  </a>
                  <span className={styles.articleMeta}>
                    {a.publisher}{a.published_et ? ` · ${formatTime(a.published_et)}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
