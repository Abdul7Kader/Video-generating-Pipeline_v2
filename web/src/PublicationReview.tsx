import { useEffect, useRef, useState } from 'react'
import { request } from './request'
import VideoPreview from './VideoPreview'
import LoadingBar from './LoadingBar'

type Metadata = { title: string; description: string; made_for_kids: boolean; synthetic_media: boolean;
  paid_partnership: boolean; own_brand: boolean; allow_comments: boolean; allow_duet: boolean; allow_stitch: boolean;
  tiktok_music_confirmed: boolean; tiktok_brand_policy_confirmed: boolean; targets: Record<string, { visibility: string }> }
type Data = { revision: number; checksum_sha256: string; metadata: Metadata; release_id: string | null;
  provenance: { mode: string; credits: string; controlled_test: boolean }; platforms: { provider: string; label: string; ready: boolean; problems: string[]; account_title: string | null }[];
  jobs: { id: string; platform: string; state: string }[] }
const visibilityLabels: Record<string, string> = { private: 'Privat', unlisted: 'Nicht gelistet', public: 'Öffentlich',
  SELF_ONLY: 'Nur ich', MUTUAL_FOLLOW_FRIENDS: 'Gegenseitige Freunde', FOLLOWER_OF_CREATOR: 'Follower', PUBLIC_TO_EVERYONE: 'Alle' }

export default function PublicationReview({ projectId, artifactId, authorized, videoApproved }: {
  projectId: string; artifactId: string; authorized: boolean; videoApproved: boolean;
}) {
  const [data, setData] = useState<Data | null>(null)
  const [metadata, setMetadata] = useState<Metadata | null>(null)
  const [choices, setChoices] = useState<Record<string, string[]>>({})
  const [interactions, setInteractions] = useState<Record<string, boolean>>({})
  const [accountNames, setAccountNames] = useState<Record<string, string>>({})
  const [dirty, setDirty] = useState(false)
  const [checks, setChecks] = useState([false, false, false])
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const inFlight = useRef(false)
  const mounted = useRef(false)
  const path = `/api/projects/${encodeURIComponent(projectId)}/videos/${encodeURIComponent(artifactId)}/publication`

  async function json(url: string, init?: RequestInit) {
    const response = await request(url, { cache: 'no-store', ...init })
    const body = await response.json()
    if (!response.ok) throw new Error(body.error?.message ?? 'Veröffentlichungsdaten konnten nicht geladen werden.')
    return body
  }
  function apply(body: Data) { setData(body); setMetadata(body.metadata); setDirty(false); setChecks([false, false, false]) }
  useEffect(() => {
    mounted.current = authorized
    let active = true
    if (!authorized) { setData(null); setMetadata(null); setBusy(''); return () => { mounted.current = false } }
    setBusy('Veröffentlichungsdaten werden geladen …'); setError('')
    void json(path).then(body => { if (active) apply(body) })
      .catch(e => { if (active) setError((e as Error).message) })
      .finally(() => { if (active) setBusy('') })
    return () => { active = false; mounted.current = false }
  }, [path, authorized])

  function edit(changes: Partial<Metadata>) {
    setMetadata(current => current && { ...current, ...changes }); setDirty(true); setChecks([false, false, false]); setMessage('')
  }
  async function action(operation: 'save' | 'approve' | 'reload' | string) {
    if (inFlight.current || busy) return
    inFlight.current = true; setBusy('Angaben werden geprüft …'); setError(''); setMessage('')
    try {
      if (operation.startsWith('options:')) {
        const provider = operation.slice(8)
        const body = await json(`${path}/options/${encodeURIComponent(provider)}`, { method: 'POST' })
        if (mounted.current) {
          setChoices(current => ({ ...current, [provider]: body.choices }))
          setAccountNames(current => ({ ...current, [provider]: body.account_title }))
          if (provider === 'tiktok') setInteractions(body.interactions)
        }
      } else if (operation === 'save' && data && metadata) {
        const body = await json(path, { method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ expected_revision: data.revision, checksum_sha256: data.checksum_sha256, metadata }) })
        if (mounted.current) { apply(body); setMessage('Entwurf gespeichert. Bitte die gespeicherten Angaben prüfen und freigeben.') }
      } else if (operation === 'approve' && data) {
        await json(`${path}/approval`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ expected_revision: data.revision, checksum_sha256: data.checksum_sha256,
            reviewed_metadata: true, reviewed_sources: true, consent_to_publish: true }) })
        const body = await json(path)
        if (mounted.current) { apply(body); setMessage('Freigabe gespeichert. Die Plattformaufträge warten auf die Upload-Anbindung.') }
      } else if (operation === 'reload') {
        const body = await json(path)
        if (mounted.current) { apply(body); setChoices({}); setAccountNames({}); setInteractions({}) }
      }
    } catch (e) { if (mounted.current) setError((e as Error).message) }
    finally { inFlight.current = false; if (mounted.current) setBusy('') }
  }
  const selected = Object.keys(metadata?.targets ?? {})
  const eligible = selected.length > 0 && selected.every(provider => data?.platforms.find(p => p.provider === provider)?.ready
    && choices[provider]?.includes(metadata!.targets[provider].visibility)) && !data?.provenance.controlled_test

  return <details className="panel publication-review">
    <summary>Veröffentlichung vorbereiten</summary>
    <div className="storage-body">
      <p>Prüfe Zielkonten, Sichtbarkeit und Angaben für dieses Video. Die Upload-Anbindungen folgen; hier wird noch nichts hochgeladen.</p>
      {!authorized && <p>Bitte zuerst unter „Speicher &amp; Videos“ anmelden.</p>}
      {busy && <LoadingBar label={busy} />}
      {error && <p className="field-error" role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {authorized && <button className="secondary-button" type="button" disabled={Boolean(busy)} onClick={() => void action('reload')}>Gespeicherten Stand laden{dirty ? ' (Entwurf verwerfen)' : ''}</button>}
      {authorized && data && metadata && <>
        <VideoPreview artifactId={artifactId} authorized={authorized} onReady={setReady} />
        <fieldset disabled={Boolean(busy)} className="publication-fields">
          <legend>Veröffentlichungsdaten</legend>
          <label>Titel<input value={metadata.title} maxLength={100} onChange={e => edit({ title: e.target.value })} /></label>
          <label>Beschreibung<textarea value={metadata.description} maxLength={2000} rows={4} onChange={e => edit({ description: e.target.value })} /></label>
          <label><input type="checkbox" checked={metadata.made_for_kids} onChange={e => edit({ made_for_kids: e.target.checked })} />Für Kinder erstellt (YouTube)</label>
          <label><input type="checkbox" checked={metadata.synthetic_media || data.provenance.mode === 'CLOUD'} disabled={data.provenance.mode === 'CLOUD'} onChange={e => edit({ synthetic_media: e.target.checked })} />KI-generierte oder wesentlich veränderte Inhalte kennzeichnen</label>
          <label><input type="checkbox" checked={metadata.paid_partnership} onChange={e => edit({ paid_partnership: e.target.checked })} />Bezahlte Partnerschaft für eine fremde Marke</label>
          <label><input type="checkbox" checked={metadata.own_brand} onChange={e => edit({ own_brand: e.target.checked })} />Werbung für die eigene Marke</label>
          {metadata.paid_partnership && <p>Das Video wird als bezahlte Partnerschaft gekennzeichnet. Bei TikTok darf es nicht „Nur ich“ sein.</p>}
          {!metadata.paid_partnership && metadata.own_brand && <p>Das Video wird als werblicher Inhalt für die eigene Marke gekennzeichnet.</p>}
          <ul className="connection-list">{data.platforms.map(platform => <li key={platform.provider}>
            <label><input type="checkbox" checked={Boolean(metadata.targets[platform.provider])} disabled={!platform.ready && !metadata.targets[platform.provider]}
              onChange={e => { const targets = { ...metadata.targets }; if (e.target.checked) targets[platform.provider] = { visibility: '' }; else delete targets[platform.provider]; edit({ targets }) }} />{platform.label}{(accountNames[platform.provider] ?? platform.account_title) ? ` · ${accountNames[platform.provider] ?? platform.account_title}` : ''}</label>
            {platform.problems.map(problem => <p key={problem}>{problem}</p>)}
            {metadata.targets[platform.provider] && <>
              <button type="button" className="secondary-button" disabled={!platform.ready} onClick={() => void action(`options:${platform.provider}`)}>Aktuelle Kontooptionen prüfen</button>
              <label>Sichtbarkeit<select value={metadata.targets[platform.provider].visibility} onChange={e => edit({ targets: { ...metadata.targets, [platform.provider]: { visibility: e.target.value } } })}>
                <option value="">Bitte wählen</option>{choices[platform.provider]?.map(value => <option value={value} key={value} disabled={value === 'SELF_ONLY' && metadata.paid_partnership}>{visibilityLabels[value] ?? value}</option>)}
              </select></label>
            </>}
          </li>)}</ul>
          {metadata.targets.tiktok && <>
            {(['allow_comments', 'allow_duet', 'allow_stitch'] as const).map((key, index) => <label key={key}><input type="checkbox" checked={metadata[key]} disabled={!interactions[key]}
              onChange={e => edit({ [key]: e.target.checked })} />{['Kommentare erlauben', 'Duette erlauben', 'Stitch erlauben'][index]}</label>)}
            <label><input type="checkbox" checked={metadata.tiktok_music_confirmed} onChange={e => edit({ tiktok_music_confirmed: e.target.checked })} />TikTok: <a href="https://www.tiktok.com/legal/page/global/music-usage-confirmation/en" target="_blank" rel="noreferrer">Music Usage Confirmation</a> gelesen und zugestimmt</label>
            {metadata.paid_partnership && <label><input type="checkbox" checked={metadata.tiktok_brand_policy_confirmed} onChange={e => edit({ tiktok_brand_policy_confirmed: e.target.checked })} />TikTok: <a href="https://www.tiktok.com/legal/page/global/bc-policy/en" target="_blank" rel="noreferrer">Branded Content Policy</a> gelesen und zugestimmt</label>}
          </>}
        </fieldset>
        <p className="publication-sources">Diese Herkunftsangaben werden übernommen:<br />{data.provenance.credits}</p>
        <button type="button" className="secondary-button" disabled={Boolean(busy) || !metadata.title.trim() || selected.some(p => !metadata.targets[p].visibility)} onClick={() => void action('save')}>Entwurf speichern</button>
        {dirty && <p>Ungespeicherte Änderungen. Zuerst speichern, danach erneut freigeben.</p>}
        {!videoApproved && <p>Bitte zuerst oben Bild und Ton des Videos freigeben.</p>}
        {data.provenance.controlled_test && <p>Dieses Video enthält kontrollierte Testclips und kann nicht für Veröffentlichung freigegeben werden.</p>}
        <fieldset disabled={Boolean(busy) || dirty || !ready || !videoApproved || !eligible || !data.revision} className="review-checks">
          <legend>Gespeicherte Angaben freigeben</legend>
          {['Titel, Beschreibung, Zielkonto und Sichtbarkeit geprüft', 'Quellen, Rechte, Zielgruppe und Kennzeichnungen geprüft', 'Diese konkrete Videodatei mit diesen Angaben für die gewählten Plattformen freigeben'].map((label, index) => <label key={label}><input type="checkbox" checked={checks[index]} onChange={e => setChecks(previous => previous.map((value, i) => i === index ? e.target.checked : value))} />{label}</label>)}
        </fieldset>
        <button type="button" className="primary-button" disabled={Boolean(busy) || dirty || !videoApproved || !ready || !eligible || !checks.every(Boolean) || Boolean(data.release_id)} onClick={() => void action('approve')}>Veröffentlichungsfreigabe speichern</button>
        {data.release_id && !dirty && <p role="status">Freigabe für Version {data.revision} gespeichert.</p>}
        {data.jobs.length > 0 && <ul>{data.jobs.map(job => <li key={job.id}>{job.platform}: {job.state === 'QUEUED' ? 'Vorbereitet · Upload-Anbindung ausstehend' : job.state}</li>)}</ul>}
      </>}
    </div>
  </details>
}
