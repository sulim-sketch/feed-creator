import { useState, useEffect } from 'react'
import styles from './SettingsModal.module.css'

interface SettingsModalProps {
  onClose: () => void
}

interface EnvResponse {
  has_key: boolean
  GEMINI_API_KEY_MASKED: string
}

export default function SettingsModal({ onClose }: SettingsModalProps) {
  const [masked, setMasked] = useState('')
  const [newKey, setNewKey] = useState('')
  const [msg, setMsg]       = useState('')

  useEffect(() => {
    fetch('/api/env')
      .then(r => r.json())
      .then((d: EnvResponse) => setMasked(d.has_key ? d.GEMINI_API_KEY_MASKED : 'Not set'))
  }, [])

  const save = async () => {
    if (!newKey.trim()) { setMsg('Enter a key first.'); return }
    const res  = await fetch('/api/env', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ GEMINI_API_KEY: newKey.trim() }),
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
        {msg && <p className={styles.msg}>{msg}</p>}
        <div className={styles.actions}>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={save}>Save</button>
        </div>
      </div>
    </div>
  )
}
