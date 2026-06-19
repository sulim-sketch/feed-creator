import { useState, useEffect } from 'react'
import styles from './SettingsModal.module.css'

interface SettingsModalProps {
  onClose: () => void
}

interface EnvResponse {
  has_key: boolean
  GEMINI_API_KEY_MASKED: string
  NAME_SOURCE: 'api' | 'excel'
}

export default function SettingsModal({ onClose }: SettingsModalProps) {
  const [masked, setMasked]         = useState('')
  const [newKey, setNewKey]         = useState('')
  const [nameSource, setNameSource] = useState<'api' | 'excel'>('api')
  const [msg, setMsg]               = useState('')

  useEffect(() => {
    fetch('/api/env')
      .then(r => r.json())
      .then((d: EnvResponse) => {
        setMasked(d.has_key ? d.GEMINI_API_KEY_MASKED : 'Not set')
        setNameSource(d.NAME_SOURCE ?? 'api')
      })
  }, [])

  const save = async () => {
    const body: Record<string, string> = { NAME_SOURCE: nameSource }
    if (newKey.trim()) body.GEMINI_API_KEY = newKey.trim()

    const res  = await fetch('/api/env', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data: { ok: boolean } = await res.json()
    if (data.ok) {
      setMsg('Saved.')
      setNewKey('')
      fetch('/api/env').then(r => r.json()).then((d: EnvResponse) => setMasked(d.GEMINI_API_KEY_MASKED))
    }
  }

  return (
    <div className={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={styles.modal}>
        <h2>Settings</h2>

        <label>Gemini API Key</label>
        <input
          type="password"
          value={newKey}
          onChange={e => setNewKey(e.target.value)}
          placeholder="Enter new key to replace current"
          autoComplete="off"
          onKeyDown={e => e.key === 'Enter' && save()}
        />
        <p className={styles.hint}>Current: {masked}</p>

        <label style={{ marginTop: 20 }}>Portfolio Source</label>
        <div className={styles.radioGroup}>
          <label className={styles.radioLabel}>
            <input
              type="radio"
              name="nameSource"
              value="api"
              checked={nameSource === 'api'}
              onChange={() => setNameSource('api')}
            />
            Core16 API <span style={{ color: '#8a9ab0', fontSize: 11 }}>(종목명: Yahoo Finance)</span>
          </label>
          <label className={styles.radioLabel}>
            <input
              type="radio"
              name="nameSource"
              value="excel"
              checked={nameSource === 'excel'}
              onChange={() => setNameSource('excel')}
            />
            Excel (xlsx 폴더)
          </label>
        </div>

        {msg && <p className={styles.msg}>{msg}</p>}
        <div className={styles.actions}>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={save}>Save</button>
        </div>
      </div>
    </div>
  )
}
