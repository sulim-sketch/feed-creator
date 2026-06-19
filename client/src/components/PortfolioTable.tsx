import { useState } from 'react'
import styles from './PortfolioTable.module.css'

const SHOW = 5

interface RowData {
  ticker: string
  d1: number
  w1: number
}

interface PortfolioTableProps {
  title: string
  rows: RowData[]
  field: 'd1' | 'w1'
  names: Record<string, string>
  highlight: string | null
}

interface RowProps {
  rank: number
  row: RowData
  field: 'd1' | 'w1'
  maxAbs: number
  name: string
  isHighlight: boolean
}

export default function PortfolioTable({ title, rows, field, names, highlight }: PortfolioTableProps) {
  const [expanded, setExpanded] = useState(false)

  const maxAbs  = Math.max(...rows.map(r => Math.abs(r[field])), 1)
  const visible = expanded ? rows : rows.slice(0, SHOW)
  const hasMore = rows.length > SHOW

  return (
    <div className={styles.block}>
      <div className={styles.titleRow}>
        <span className={styles.title}>{title}</span>
        {hasMore && expanded && (
          <button className={styles.topBtn} onClick={() => setExpanded(false)}>
            Show less ▴
          </button>
        )}
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th>#</th>
            <th>Ticker</th>
            <th className={styles.right}>{field === 'd1' ? '1D' : '5D'}</th>
            <th className={styles.barCol}></th>
          </tr>
        </thead>
        <tbody>
          {visible.map((r, i) => (
            <Row
              key={r.ticker}
              rank={i + 1}
              row={r}
              field={field}
              maxAbs={maxAbs}
              name={names[r.ticker] || ''}
              isHighlight={r.ticker === highlight}
            />
          ))}
        </tbody>
      </table>

      {hasMore && (
        <button className={styles.expandBtn} onClick={() => setExpanded(e => !e)}>
          {expanded ? 'Show less ▴' : `Show ${rows.length - SHOW} more ▾`}
        </button>
      )}
    </div>
  )
}

function Row({ rank, row, field, maxAbs, name, isHighlight }: RowProps) {
  const val   = row[field]
  const color = val >= 0 ? '#0a9e5c' : '#d93025'
  const sign  = val >= 0 ? '+' : ''
  const barW  = (Math.abs(val) / maxAbs * 100).toFixed(1)
  const barML = val >= 0 ? '50%' : `${50 - parseFloat(barW)}%`

  return (
    <tr className={isHighlight ? styles.highlight : ''}>
      <td className={styles.rank}>{rank}</td>
      <td>
        <div className={styles.tickerName}>
          {row.ticker}
          {isHighlight && <span className={styles.badge}>FEED</span>}
        </div>
        {name && <div className={styles.company}>{name}</div>}
      </td>
      <td className={styles.right}>
        <span style={{ color, fontWeight: 600, fontVariantNumeric: 'tabular-nums', fontSize: 14 }}>
          {sign}{val.toFixed(2)}%
        </span>
      </td>
      <td className={styles.barCol}>
        <div className={styles.barTrack}>
          <div className={styles.barFill} style={{ width: `${barW}%`, background: color, marginLeft: barML }} />
          <div className={styles.barCenter} />
        </div>
      </td>
    </tr>
  )
}
