import { useState } from 'react'
import styles from './ResultCard.module.css'

interface Article {
  title: string
  url: string
  publisher: string
  published_et?: string
  body?: string
}

export interface PipelineResult {
  ticker: string
  trading_date: string
  return_pct: number
  summary_x: string
  summary_linkedin: string
  articles: Article[]
}

interface ResultCardProps {
  result: PipelineResult
}

export default function ResultCard({ result }: ResultCardProps) {
  const [copied, setCopied] = useState<'x' | 'linkedin' | null>(null)
  const [articlesOpen, setArticlesOpen] = useState(false)

  const copy = (text: string, key: 'x' | 'linkedin') => {
    navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
  }

  const formatTime = (iso?: string) => {
    if (!iso) return ''
    try {
      return new Date(iso).toLocaleTimeString('en-US', {
        hour: '2-digit', minute: '2-digit', timeZone: 'America/New_York',
      }) + ' ET'
    } catch { return '' }
  }

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.ticker}>${result.ticker}</span>
        <span className={styles.returnBadge}>+{result.return_pct.toFixed(2)}%</span>
        <span className={styles.label}>Feed Summary</span>
      </div>

      <div className={styles.sections}>
        <div className={styles.section}>
          <div className={styles.sectionHead}>
            <span className={styles.platform}>X / Twitter</span>
            <div className={styles.sectionActions}>
              <span className={styles.charCount}>{(result.summary_x ?? '').length} chars</span>
              <button className={styles.copyBtn} onClick={() => copy(result.summary_x, 'x')}>
                {copied === 'x' ? '✓ Copied' : 'Copy'}
              </button>
            </div>
          </div>
          <p className={styles.summaryText}>{result.summary_x ?? ''}</p>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionHead}>
            <span className={styles.platform}>LinkedIn</span>
            <div className={styles.sectionActions}>
              <span className={styles.charCount}>{(result.summary_linkedin ?? '').length} chars</span>
              <button className={styles.copyBtn} onClick={() => copy(result.summary_linkedin ?? '', 'linkedin')}>
                {copied === 'linkedin' ? '✓ Copied' : 'Copy'}
              </button>
            </div>
          </div>
          <p className={styles.summaryText}>{result.summary_linkedin ?? ''}</p>
        </div>
      </div>

      <button className={styles.articlesToggle} onClick={() => setArticlesOpen(o => !o)}>
        {articlesOpen ? '▴' : '▾'} Articles ({result.articles.length})
      </button>

      {articlesOpen && (
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
      )}
    </div>
  )
}
