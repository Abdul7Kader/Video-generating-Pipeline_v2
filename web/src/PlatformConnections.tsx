import { useEffect, useRef, useState } from 'react'
import { request } from './request'
import LoadingBar from './LoadingBar'

type Connection = {
  provider: string; label: string; state: string; account_title: string | null;
  can_connect: boolean; can_refresh: boolean; can_disconnect: boolean; can_forget: boolean;
  problems: string[]; review_status: string;
}
const labels: Record<string, string> = {
  CONNECTED: 'Verbunden', LIMITED: 'Berechtigungen fehlen', EXPIRED: 'Zugang abgelaufen',
  REAUTH_REQUIRED: 'Erneut verbinden', REVOKE_FAILED: 'Widerruf ausstehend', DISCONNECTED: 'Nicht verbunden',
}
const results: Record<string, string> = {
  CONNECTED: 'Kontoverbindung gespeichert. Bitte den Kontonamen und die Berechtigungen prüfen.',
  SOCIAL_CONSENT_DENIED: 'Die Kontoverbindung wurde nicht freigegeben.',
  SOCIAL_ACCOUNT_INELIGIBLE: 'Kein berechtigtes Zielkonto gefunden. Bitte Kanal und Kontorechte prüfen.',
  SOCIAL_REAUTH_REQUIRED: 'Die Plattform hat den Zugang abgelehnt. Bitte die App-Rechte prüfen.',
}

export default function PlatformConnections({ authorized, onAccessLost }: {
  authorized: boolean; onAccessLost: () => void;
}) {
  const [connections, setConnections] = useState<Connection[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [removedAtProvider, setRemovedAtProvider] = useState<Record<string, boolean>>({})
  const inFlight = useRef(false)
  const mounted = useRef(true)

  async function json(url: string, init?: RequestInit) {
    const response = await request(url, { cache: 'no-store', ...init })
    const body = await response.json()
    if (!response.ok) {
      if (response.status === 401) onAccessLost()
      throw new Error(body.error?.message ?? 'Die Kontoverbindung konnte nicht geändert werden.')
    }
    return body
  }
  async function load() {
    const body = await json('/api/connections')
    if (mounted.current) setConnections(body.connections)
  }
  useEffect(() => {
    mounted.current = true
    const url = new URL(window.location.href)
    const result = url.searchParams.get('connection_result')
    if (result) {
      setMessage(results[result] ?? 'Die Kontoverbindung ist fehlgeschlagen. Bitte erneut versuchen und die Einrichtung prüfen.')
      url.searchParams.delete('connection_result'); url.searchParams.delete('connections')
      window.history.replaceState(null, '', url)
    }
    return () => { mounted.current = false }
  }, [])
  useEffect(() => {
    let active = true
    if (!authorized) { setConnections([]); return }
    setBusy('Kontoverbindungen werden geladen …'); setError('')
    void json('/api/connections').then(body => { if (active) setConnections(body.connections) })
      .catch(e => { if (active) setError((e as Error).message) })
      .finally(() => { if (active) setBusy(null) })
    return () => { active = false }
  }, [authorized])

  async function action(connection: Connection, operation: 'authorize' | 'refresh' | 'disconnect' | 'forget') {
    if (inFlight.current || busy) return
    inFlight.current = true
    setError(''); setMessage('')
    setBusy(operation === 'authorize' ? 'Kontozustimmung wird vorbereitet …' : operation === 'refresh' ? 'Zugang wird erneuert …' : operation === 'forget' ? 'Lokale Zugangsdaten werden entfernt …' : 'Zugang wird widerrufen …')
    try {
      const path = `/api/connections/${encodeURIComponent(connection.provider)}`
      const result = await json(operation === 'disconnect' ? path : `${path}/${operation}`, {
        method: operation === 'disconnect' ? 'DELETE' : 'POST',
        ...(operation === 'forget' ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ provider_access_removed: true }) } : {}),
      })
      if (!mounted.current) return
      if (operation === 'authorize') {
        const target = new URL(result.authorization_url)
        if (target.protocol !== 'https:' || !['accounts.google.com', 'www.tiktok.com'].includes(target.hostname)) throw new Error('Ungültiges Anmeldeziel.')
        window.location.assign(target.href)
        return
      }
      setMessage(operation === 'disconnect' ? 'Zugang beim Anbieter widerrufen und lokale Tokens entfernt.' : operation === 'forget' ? 'Lokale Zugangsdaten entfernt. Der Widerruf beim Anbieter wurde hier nicht geprüft.' : 'Zugang erneuert und Zielkonto geprüft.')
      setRemovedAtProvider(previous => ({ ...previous, [connection.provider]: false }))
      await load()
    } catch (e) {
      if (mounted.current) {
        setError((e as Error).message)
        try { await load() } catch { /* Retain the original action error. */ }
      }
    } finally {
      inFlight.current = false
      if (mounted.current) setBusy(null)
    }
  }

  return <details className="storage-settings panel platform-connections">
    <summary>Plattformkonten <span>{connections.filter(c => c.state !== 'DISCONNECTED').length} verbunden</span></summary>
    <div className="storage-body">
      <p>Wähle dein Zielkonto. Veröffentlichungen werden erst nach einer eigenen Videofreigabe eingerichtet.</p>
      {!authorized && <p>Bitte zuerst den Zugang unter „Speicher &amp; Videos“ entsperren.</p>}
      {busy && <LoadingBar label={busy} />}
      {error && <p className="field-error" role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {authorized && <>
        <button type="button" className="secondary-button" disabled={Boolean(busy)} onClick={() => {
          setBusy('Kontoverbindungen werden geladen …'); setError('')
          void load().catch(e => setError((e as Error).message)).finally(() => setBusy(null))
        }}>Status neu laden</button>
        <ul className="connection-list">{connections.map(connection => <li key={connection.provider}>
          <h3>{connection.label} <small>{labels[connection.state] ?? connection.state}</small></h3>
          {connection.account_title && <p>Verbundenes Konto: <strong>{connection.account_title}</strong></p>}
          {connection.review_status === 'TEST_ONLY' && <p>Entwickler-App für freigegebene Testkonten.</p>}
          {connection.problems.length > 0 && <ul>{connection.problems.map(problem => <li key={problem}>{problem}</li>)}</ul>}
          <div className="connection-actions">
            <button type="button" className="primary-button" disabled={Boolean(busy) || !connection.can_connect}
              onClick={() => void action(connection, 'authorize')}>{connection.state === 'DISCONNECTED' ? 'Konto verbinden' : 'Neu verbinden'}</button>
            {connection.can_refresh && <button type="button" className="secondary-button" disabled={Boolean(busy)}
              onClick={() => void action(connection, 'refresh')}>Zugang erneuern</button>}
            {connection.can_disconnect && <button type="button" className="text-button" disabled={Boolean(busy)}
              onClick={() => void action(connection, 'disconnect')}>{connection.state === 'REVOKE_FAILED' ? 'Widerruf wiederholen' : 'Verbindung widerrufen'}</button>}
          </div>
          {connection.can_forget && (connection.state === 'REVOKE_FAILED' || !connection.can_disconnect) && <div className="connection-recovery">
            <p>Wenn du den Zugriff bereits in den Kontoeinstellungen des Anbieters entfernt hast, kannst du die verbliebenen lokalen Zugangsdaten löschen.</p>
            <label><input type="checkbox" checked={Boolean(removedAtProvider[connection.provider])} disabled={Boolean(busy)}
              onChange={event => setRemovedAtProvider(previous => ({ ...previous, [connection.provider]: event.target.checked }))} /> Zugriff beim Anbieter bereits entfernt</label>
            <button type="button" className="text-button" disabled={Boolean(busy) || !removedAtProvider[connection.provider]}
              onClick={() => void action(connection, 'forget')}>Lokale Zugangsdaten löschen</button>
          </div>}
        </li>)}</ul>
      </>}
    </div>
  </details>
}
