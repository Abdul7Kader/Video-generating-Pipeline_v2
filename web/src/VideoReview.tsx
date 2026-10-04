import { useEffect, useRef, useState } from 'react'
import type { Script } from './ScriptEditor'
import VideoPreview from './VideoPreview'
import LoadingBar from './LoadingBar'
import { request } from './request'

type Props = {
  projectId: string; artifactId: string; idea: string; script: Script; authorized: boolean;
  approved: boolean; duplicateClips: boolean; onApproved: () => void; onEdit: () => void;
  sceneStarts?: { scene_position: number; seconds: number }[];
  busy: boolean;
}

export default function VideoReview(props: Props) {
  const [checksum, setChecksum] = useState('')
  const [ready, setReady] = useState(false)
  const [narration, setNarration] = useState(false)
  const [visuals, setVisuals] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [seek, setSeek] = useState<{ seconds: number }>()
  const inFlight = useRef(false)
  useEffect(() => {
    let active = true
    setChecksum(''); setError('')
    if (props.authorized) void (async () => {
      try {
        const response = await request(`/api/artifacts/${encodeURIComponent(props.artifactId)}`, { cache: 'no-store' })
        const body = await response.json()
        if (!response.ok || !body.content_available) throw new Error(body.error?.message || 'Das fertige Video ist noch nicht verfügbar.')
        if (active) setChecksum(body.checksum_sha256)
      } catch (failure) { if (active) setError(failure instanceof Error ? failure.message : 'Videodaten konnten nicht geladen werden.') }
    })()
    return () => { active = false }
  }, [props.artifactId, props.authorized, retry])

  async function approve() {
    if (inFlight.current || props.busy || !ready || !checksum || !narration || !visuals || !props.authorized || props.duplicateClips) return
    inFlight.current = true; setSaving(true); setError('')
    try {
      const response = await request(`/api/projects/${encodeURIComponent(props.projectId)}/videos/${encodeURIComponent(props.artifactId)}/approval`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ checksum_sha256: checksum, reviewed_narration: true, reviewed_visuals: true }),
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.error?.message || 'Die Videofreigabe konnte nicht gespeichert werden.')
      props.onApproved()
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Freigabe fehlgeschlagen. Bitte erneut versuchen.') }
    finally { inFlight.current = false; setSaving(false) }
  }
  let elapsed = 0
  return <section className="video-review" aria-labelledby="review-title">
    <h3 id="review-title">Video prüfen · Version {props.script.version}</h3>
    <div className="review-input"><span className="data-label">DEINE EINGABE</span><p>{props.idea}</p></div>
    <VideoPreview artifactId={props.artifactId} authorized={props.authorized} seek={seek} onReady={setReady} />
    <details className="review-comparison">
      <summary>Sprechertext und Bildvorgaben vergleichen</summary>
      <ol>{props.script.scenes.map(scene => {
        const start = props.sceneStarts?.find(item => item.scene_position === scene.position)?.seconds ?? elapsed
        elapsed += scene.duration_seconds ?? 0
        return <li key={scene.position}>
          <button type="button" className="secondary-button" disabled={!props.authorized || !ready} onClick={() => setSeek({ seconds: start })}>Ab {start} s ansehen</button>
          <p><strong>Sprechertext</strong><br />{scene.narration}</p>
          <p><strong>Bildvorgabe</strong><br />{scene.visual_description}</p>
        </li>
      })}</ol>
    </details>
    {props.duplicateClips && <p className="notice-error" role="alert">Dieses Video verwendet Clips mehrfach. Bitte die Bildvorgaben bearbeiten und eine neue Version produzieren.</p>}
    {props.approved ? <p className="review-approved" role="status">✓ Video freigegeben · Version {props.script.version}</p> : <fieldset className="review-checks" disabled={saving || !props.authorized || !ready || props.duplicateClips}>
      <legend>Deine Prüfung</legend>
      <label><input type="checkbox" checked={narration} onChange={event => setNarration(event.target.checked)} />Erzählung, Stimme und Untertitel passen.</label>
      <label><input type="checkbox" checked={visuals} onChange={event => setVisuals(event.target.checked)} />Bilder passen zum Text; keine störenden Wiederholungen.</label>
    </fieldset>}
    {props.authorized && !checksum && !error && <LoadingBar label="Videodaten werden geprüft …" />}
    {error && <><p className="notice-error" role="alert">{error}</p>{!checksum && <button type="button" className="secondary-button" onClick={() => setRetry(value => value + 1)}>Videodaten erneut laden</button>}</>}
    <div className="review-actions">
      {!props.approved && <button type="button" className="primary-button" disabled={props.busy || saving || !ready || !checksum || !props.authorized || !narration || !visuals || props.duplicateClips} onClick={() => void approve()} aria-busy={saving}>Video freigeben</button>}
      <button type="button" className="secondary-button" disabled={props.busy || saving} onClick={props.onEdit}>Skript für neue Version bearbeiten</button>
    </div>
    {saving && <LoadingBar label="Videofreigabe wird gespeichert …" />}
    <p className="field-hint">Die Freigabe gilt für genau dieses Video. Eine Veröffentlichung folgt erst nach Einrichtung und Auswahl der Plattformen.</p>
  </section>
}
