import { useEffect, useRef, useState, type FormEvent } from 'react'
import LoadingBar from './LoadingBar'
import { request } from './request'

type Change = { id: string; state: string; total_bytes: number; verified_bytes: number; error_message: string | null }
type Store = { path: string; change: Change | null }
export default function StorageSettings({ onAccess }: { onAccess: (value: boolean) => void }) {
  const [session, setSession] = useState<{ configured: boolean; authorized: boolean } | null>(null)
  const [store, setStore] = useState<Store | null>(null)
  const [path, setPath] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [initializing, setInitializing] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const locked = useRef(false)
  const mounted = useRef(true)
  async function json(url: string, options?: RequestInit) {
    const response = await request(url, options)
    const body = await response.json()
    if (!response.ok) {
      if (response.status === 401) { setSession(s => s && { ...s, authorized: false }); onAccess(false) }
      throw new Error(body.error?.message ?? 'Die Anfrage ist fehlgeschlagen.')
    }
    return body
  }
  async function loadStore(resetPath = true) {
    const result = await json('/api/storage') as Store
    if (!mounted.current) return
    setStore(result)
    if (result.change?.state === 'FAILED') setError(result.change.error_message ?? 'Übernahme fehlgeschlagen.')
    if (resetPath) setPath(result.path)
  }
  async function refresh() {
    setError(''); setInitializing(true)
    try {
      const result = await json('/api/media-session')
      if (!mounted.current) return
      setSession(result); onAccess(result.authorized)
      if (result.authorized) await loadStore()
    } catch (e) { if (mounted.current) setError((e as Error).message) }
    finally { if (mounted.current) setInitializing(false) }
  }
  useEffect(() => {
    mounted.current = true
    void refresh()
    return () => { mounted.current = false }
  }, [])
  const copying = Boolean(store?.change && ['QUEUED', 'RUNNING'].includes(store.change.state))
  useEffect(() => {
    if (!copying || !store?.change) return
    let active = true
    let polling = false
    const id = store.change.id
    async function poll() {
      if (polling) return
      polling = true
      try {
        const change = await json(`/api/storage/changes/${id}`) as Change
        if (!active) return
        setStore(s => s && { ...s, change })
        if (change.state === 'COMPLETED') { setMessage('Speicherort übernommen. Die ursprünglichen Dateien bleiben erhalten.'); await loadStore() }
        if (change.state === 'FAILED') setError(change.error_message ?? 'Übernahme fehlgeschlagen.')
      } catch (e) { if (active) setError((e as Error).message) }
      finally { polling = false }
    }
    const timer = window.setInterval(() => void poll(), 1500)
    return () => { active = false; window.clearInterval(timer) }
  }, [copying, store?.change?.id])
  async function unlock(event: FormEvent) {
    event.preventDefault()
    if (locked.current) return
    locked.current = true; setBusy(true); setError('')
    try {
      const result = await json('/api/media-session', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) })
      setPassword(''); setSession(result); onAccess(true); await loadStore()
    } catch (e) { setError((e as Error).message) }
    finally { locked.current = false; setBusy(false) }
  }
  async function change(event: FormEvent) {
    event.preventDefault()
    if (locked.current || !store || copying) return
    locked.current = true; setBusy(true); setError(''); setMessage('')
    try {
      const result = await json('/api/storage/changes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: path.trim(), expected_path: store.path }) }) as Change
      setStore(s => s && { ...s, change: result })
    } catch (e) { setError((e as Error).message) }
    finally { locked.current = false; setBusy(false) }
  }
  async function logout() {
    if (locked.current) return
    locked.current = true; setBusy(true); setError('')
    try { await json('/api/media-session', { method: 'DELETE' }); setSession(s => s && { ...s, authorized: false }); onAccess(false); setStore(null) }
    catch (e) { setError((e as Error).message) }
    finally { locked.current = false; setBusy(false) }
  }
  const done = store?.change?.verified_bytes ?? 0
  const total = store?.change?.total_bytes ?? 0
  return <details className="panel storage-settings" id="storage-settings">
    <summary>Speicher &amp; Videos <span aria-hidden="true">⌄</span></summary>
    <div className="storage-body">
      {initializing && <LoadingBar label="Speichereinstellungen werden geladen …" />}
      {!initializing && !session?.authorized && <form onSubmit={unlock}>
        <h3>{session?.configured ? 'Videos entsperren' : 'Videozugriff einrichten'}</h3>
        <label htmlFor="media-password">{session?.configured ? 'Passwort' : 'Dein Passwort festlegen (mindestens 10 Zeichen)'}</label>
        <input id="media-password" type="password" autoComplete={session?.configured ? 'current-password' : 'new-password'} minLength={10} maxLength={200} required value={password} onChange={e => setPassword(e.target.value)} disabled={busy} />
        <button className="primary-button" disabled={busy}>{session?.configured ? 'Entsperren' : 'Passwort festlegen'}</button>
        {busy && <LoadingBar label="Videozugriff wird entsperrt …" />}
      </form>}
      {session?.authorized && <>
        <div className="saved-header"><h3>Medienspeicher auf diesem Rechner</h3><button type="button" className="text-button" disabled={busy} onClick={() => void logout()}>Sperren</button></div>
        {!store && !initializing && <button type="button" className="secondary-button" onClick={() => void refresh()}>Speicher erneut laden</button>}
        {store && <form onSubmit={change}>
          <p className="storage-current">Aktueller Ordner: <strong>{store.path}</strong></p>
          <label htmlFor="storage-path">Speicherordner ändern</label>
          <input id="storage-path" type="text" required maxLength={4096} value={path} onChange={e => setPath(e.target.value)} disabled={busy || copying} spellCheck={false} autoComplete="off" />
          <p className="field-hint">Vollständigen Pfad eines eigenen Ordners eingeben. Vorhandene Medien werden kopiert und geprüft; der bisherige Ordner bleibt erhalten.</p>
          <button className="primary-button" disabled={busy || copying || !path.trim() || path.trim() === store.path}>Speicherort übernehmen</button>
          {busy && <LoadingBar label="Speicherübernahme wird gestartet …" />}
          {copying && (total > 0 ? <div className="loading-state"><p role="status">Medien werden übernommen und geprüft · {Math.floor(done / total * 100)} %</p><progress aria-label="Geprüfte Medien" max={total} value={done} /></div> : <LoadingBar label={store.change?.state === 'QUEUED' ? 'Speicherübernahme wartet auf den Worker …' : 'Dateien werden geprüft …'} />)}
        </form>}
      </>}
      {message && <p className="script-success" role="status">{message}</p>}
      {error && <><p className="notice-error" role="alert">{error}</p><button type="button" className="secondary-button" disabled={busy || initializing} onClick={() => void refresh()}>Status erneut laden</button></>}
    </div>
  </details>
}
