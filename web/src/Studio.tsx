import { useEffect, useRef, useState, type FormEvent } from 'react'
import ScriptEditor, { type Script } from './ScriptEditor'
import LoadingBar from './LoadingBar'
import { request } from './request'
import StorageSettings from './StorageSettings'
import VideoReview from './VideoReview'

type Mode = 'LOKAL' | 'CLOUD'
type MediaType = 'STOCK_VIDEO' | 'AI_GENERATED_VIDEO'
type Services = { database: boolean; redis: boolean; worker: boolean }
type Health = { status: 'ready' | 'waiting'; services: Services }
type Project = { id: string; idea: string; mode: Mode; media_type: MediaType; created_at: string }
type ProductionStep = { id: string; name: string; state: string; attempts: number; max_attempts: number }
type PexelsSource = { scene_position: number; video_id: number; video_page: string; creator: string; creator_page: string; width: number; height: number; duration_seconds: number }
type SpeechSegment = { scene_position: number; voice: string; duration_seconds: number }
type GraphicsManifest = { width: number; height: number; fps: number; duration_frames: number; scenes: { scene_position: number; start_frame: number; caption_frames: number }[] }
type EncodingManifest = { width: number; height: number; fps: number; duration_seconds: number; video_codec: string; audio_codec: string; size_bytes: number }
type ProjectStatus = { video_approved?: boolean; final_artifact_id?: string | null; latest_script_version: number | null; script_approved: boolean; production_run_id: string | null; production_state: string | null; production_error: string | null; production_steps?: ProductionStep[]; production_can_resume?: boolean; production_cancel_requested?: boolean; production_sources?: PexelsSource[]; production_speech?: SpeechSegment[]; production_graphics?: GraphicsManifest | null; production_encoding?: EncodingManifest | null }
type ScriptJob = { id: string; state: 'QUEUED' | 'RUNNING' | 'FAILED' | 'COMPLETED'; error_message: string | null; script_version: number | null; created_at: string }

const STORAGE_KEY = 'videostudio:last-project-id'
const productionLabels: Record<string, string> = { SCENES: 'Szenen beschaffen', SPEECH: 'Sprache erzeugen', GRAPHICS: 'Grafik rendern', ENCODING: 'Video encodieren', STORAGE: 'Video ablegen' }
const stepStates: Record<string, string> = { PENDING: 'Wartet', RUNNING: 'Läuft', FAILED: 'Gestoppt', COMPLETED: 'Fertig' }
const serviceLabels: Record<keyof Services, string> = {
  database: 'Datenbank', redis: 'Warteschlange', worker: 'Hintergrund-Worker',
}

async function responseError(response: Response) {
  try {
    const body = await response.json() as { error?: { code?: string; message?: string } }
    if (body.error?.code === 'VALIDATION_ERROR') return 'Bitte prüfe deine Eingaben.'
    return body.error?.message || 'Die Anfrage ist fehlgeschlagen.'
  } catch {
    return 'Die Anfrage ist fehlgeschlagen.'
  }
}

export default function Studio() {
  const [mediaAuthorized, setMediaAuthorized] = useState(false)
  const [health, setHealth] = useState<Health | null>(null)
  const [reachable, setReachable] = useState(true)
  const [idea, setIdea] = useState('')
  const [mode, setMode] = useState<Mode>('LOKAL')
  const [ideaError, setIdeaError] = useState('')
  const [saveError, setSaveError] = useState('')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(false)
  const [project, setProject] = useState<Project | null>(null)
  const [projectStatus, setProjectStatus] = useState<ProjectStatus | null>(null)
  const [scriptJob, setScriptJob] = useState<ScriptJob | null>(null)
  const [script, setScript] = useState<Script | null>(null)
  const [editing, setEditing] = useState(false)
  const [generationError, setGenerationError] = useState('')
  const [startingGeneration, setStartingGeneration] = useState(false)
  const [approving, setApproving] = useState(false)
  const [approvalError, setApprovalError] = useState('')
  const [checkingHealth, setCheckingHealth] = useState(true)
  const [fetchingScript, setFetchingScript] = useState(false)
  const [productionAction, setProductionAction] = useState<'resume' | 'cancel' | null>(null)
  const productionInFlight = useRef(false)
  const approvalInFlight = useRef(false)
  const projectInFlight = useRef(false)
  const generationInFlight = useRef(false)
  const activeProjectId = useRef<string | null>(null)
  const lastProjectId = useRef(window.localStorage.getItem(STORAGE_KEY))

  useEffect(() => {
    let active = true
    async function updateHealth() {
      try {
        const response = await request('/api/health/ready', { cache: 'no-store' })
        const result: Health = await response.json()
        if (active) { setHealth(result); setReachable(true) }
      } catch {
        if (active) { setHealth(null); setReachable(false) }
      } finally {
        if (active) setCheckingHealth(false)
      }
    }
    void updateHealth()
    const timer = window.setInterval(() => void updateHealth(), 10000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  async function loadProject(id: string) {
    setLoading(true)
    try {
      const [projectResponse, statusResponse] = await Promise.all([
        request(`/api/projects/${encodeURIComponent(id)}`, { cache: 'no-store' }),
        request(`/api/projects/${encodeURIComponent(id)}/status`, { cache: 'no-store' }),
      ])
      if (!projectResponse.ok || !statusResponse.ok) throw new Error()
      const loadedProject = await projectResponse.json() as Project
      const status = await statusResponse.json() as ProjectStatus
      let loadedScript: Script | null = null
      if (status.latest_script_version) {
        const scriptResponse = await request(`/api/projects/${encodeURIComponent(id)}/scripts/${status.latest_script_version}`, { cache: 'no-store' })
        if (!scriptResponse.ok) throw new Error()
        loadedScript = await scriptResponse.json() as Script
      }
      // Never combine a newly loaded project with a script left from an earlier view.
      setProject(loadedProject)
      activeProjectId.current = id
      lastProjectId.current = id
      window.localStorage.setItem(STORAGE_KEY, id)
      const url = new URL(window.location.href)
      if (url.searchParams.has('project')) { url.searchParams.delete('project'); window.history.replaceState(null, '', url) }
      setProjectStatus(status)
      setScript(loadedScript)
      if (!status.latest_script_version) {
        const jobId = window.localStorage.getItem(`videostudio:script-job:${id}`)
        if (jobId) void refreshGeneration(id, jobId)
      }
      setSaveError('')
      setApprovalError('')
      setGenerationError('')
    } catch {
      setSaveError('Das gespeicherte Projekt konnte nicht geladen werden. Bitte versuche es erneut.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const linked = new URLSearchParams(window.location.search).get('project')
    const id = linked && /^[0-9a-f-]{36}$/i.test(linked) ? linked : window.localStorage.getItem(STORAGE_KEY)
    if (id) void loadProject(id)
  }, [])

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (projectInFlight.current || loading || editing || approving || startingGeneration || fetchingScript) return
    const cleanedIdea = idea.trim()
    if (!cleanedIdea) { setIdeaError('Bitte beschreibe zuerst deine Videoidee.'); return }
    setIdeaError('')
    setSaveError('')
    projectInFlight.current = true
    setSaving(true)
    try {
      const response = await request('/api/projects', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idea: cleanedIdea, mode }),
      })
      if (!response.ok) throw new Error(await responseError(response))
      const saved = await response.json() as Project
      window.localStorage.setItem(STORAGE_KEY, saved.id)
      activeProjectId.current = saved.id
      lastProjectId.current = saved.id
      setProject(saved)
      setProjectStatus({ latest_script_version: null, script_approved: false, production_run_id: null, production_state: null, production_error: null })
      setScriptJob(null)
      setScript(null)
      setEditing(false)
      setGenerationError('')
      setIdea('')
      await loadProject(saved.id)
      void startGeneration(saved.id)
      window.requestAnimationFrame(() => {
        document.getElementById('saved-title')?.focus()
      })
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Das Projekt konnte nicht gespeichert werden.')
    } finally {
      projectInFlight.current = false
      setSaving(false)
    }
  }

  async function refreshGeneration(projectId: string, jobId: string) {
    if (generationInFlight.current) return
    generationInFlight.current = true
    try {
      const response = await request(`/api/projects/${encodeURIComponent(projectId)}/script-generations/${encodeURIComponent(jobId)}`, { cache: 'no-store' })
      if (!response.ok) throw new Error(await responseError(response))
      const job = await response.json() as ScriptJob
      if (activeProjectId.current !== projectId) return
      setScriptJob(job)
      if (job.state === 'COMPLETED' && job.script_version) {
        setFetchingScript(true)
        const scriptResponse = await request(`/api/projects/${encodeURIComponent(projectId)}/scripts/${job.script_version}`, { cache: 'no-store' })
        if (!scriptResponse.ok) throw new Error('Das fertige Skript konnte nicht geladen werden.')
        const loaded = await scriptResponse.json() as Script
        if (activeProjectId.current !== projectId) return
        setScript(loaded)
        setProjectStatus((current) => current ? { ...current, latest_script_version: job.script_version } : current)
      }
      setGenerationError('')
    } catch (error) {
      if (activeProjectId.current === projectId) setGenerationError(error instanceof Error ? error.message : 'Der Skriptstatus konnte nicht geladen werden.')
    } finally {
      generationInFlight.current = false
      if (activeProjectId.current === projectId) setFetchingScript(false)
    }
  }

  useEffect(() => {
    if (!project || !scriptJob || !['QUEUED', 'RUNNING'].includes(scriptJob.state)) return
    const timer = window.setInterval(() => void refreshGeneration(project.id, scriptJob.id), 3000)
    return () => window.clearInterval(timer)
  }, [project?.id, scriptJob?.id, scriptJob?.state])

  async function startGeneration(projectId = project?.id) {
    if (!projectId || startingGeneration) return
    setStartingGeneration(true)
    setGenerationError('')
    try {
      const response = await request(`/api/projects/${encodeURIComponent(projectId)}/script-generations`, { method: 'POST' })
      if (!response.ok) throw new Error(await responseError(response))
      const job = await response.json() as ScriptJob
      window.localStorage.setItem(`videostudio:script-job:${projectId}`, job.id)
      setScriptJob(job)
    } catch (error) {
      setGenerationError(error instanceof Error ? error.message : 'Der Skriptauftrag konnte nicht gestartet werden.')
    } finally {
      setStartingGeneration(false)
    }
  }

  async function approveScript() {
    if (!project || !script || editing || loading || saveError || approvalInFlight.current) return
    approvalInFlight.current = true
    setApproving(true)
    setApprovalError('')
    try {
      const response = await request(`/api/projects/${encodeURIComponent(project.id)}/scripts/${script.version}/approval`, { method: 'POST' })
      if (!response.ok) {
        if (response.status === 409) throw new Error('Es gibt eine neuere Skriptversion. Bitte lade das Projekt neu und prüfe sie vor der Freigabe.')
        throw new Error(await responseError(response))
      }
      const status = await request(`/api/projects/${encodeURIComponent(project.id)}/status`, { cache: 'no-store' })
      if (!status.ok) throw new Error('Die Freigabe wurde gespeichert. Bitte lade den Status erneut.')
      setProjectStatus(await status.json() as ProjectStatus)
    } catch (error) {
      setApprovalError(error instanceof Error ? error.message : 'Die Freigabe konnte nicht bestätigt werden. Bitte erneut versuchen; dieselbe Version erhält keinen zweiten Auftrag.')
    } finally {
      approvalInFlight.current = false
      setApproving(false)
    }
  }

  async function changeProduction(action: 'resume' | 'cancel') {
    if (!project || !projectStatus?.production_run_id || productionInFlight.current || loading || editing) return
    const id = project.id
    const run = projectStatus.production_run_id
    productionInFlight.current = true
    setProductionAction(action)
    setApprovalError('')
    try {
      const response = await request(`/api/projects/${encodeURIComponent(id)}/production-runs/${encodeURIComponent(run)}/${action}`, { method: 'POST' })
      const error = response.ok ? '' : await responseError(response)
      const status = await request(`/api/projects/${encodeURIComponent(id)}/status`, { cache: 'no-store' })
      if (!status.ok) throw new Error('Der Produktionsstatus konnte nicht geladen werden. Bitte lade das Projekt erneut.')
      if (activeProjectId.current === id) setProjectStatus(await status.json() as ProjectStatus)
      if (error) throw new Error(error)
    } catch (error) {
      if (activeProjectId.current === id) setApprovalError(error instanceof Error ? error.message : 'Die Produktionsaktion ist fehlgeschlagen.')
    } finally {
      productionInFlight.current = false
      setProductionAction(null)
    }
  }

  useEffect(() => {
    if (!project || !projectStatus?.script_approved || !['QUEUED', 'RUNNING'].includes(projectStatus.production_state ?? '')) return
    let active = true
    let polling = false
    const timer = window.setInterval(async () => {
      if (polling || productionInFlight.current) return
      polling = true
      try {
        const response = await request(`/api/projects/${encodeURIComponent(project.id)}/status`, { cache: 'no-store' })
        if (!response.ok) throw new Error()
        const status = await response.json() as ProjectStatus
        if (active && !productionInFlight.current) { setProjectStatus(status); setApprovalError('') }
      } catch {
        if (active) setApprovalError('Der Produktionsstatus ist derzeit nicht erreichbar. Bitte lade das Projekt erneut.')
      } finally {
        polling = false
      }
    }, 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [project?.id, projectStatus?.script_approved, projectStatus?.production_state])

  const scriptApproved = Boolean(script && projectStatus?.latest_script_version === script.version && projectStatus.script_approved)
  const newerScript = Boolean(script && projectStatus?.latest_script_version && projectStatus.latest_script_version > script.version)

  const ready = reachable && health?.status === 'ready'
  const mediaType = mode === 'LOKAL' ? 'STOCK_VIDEO' : 'AI_GENERATED_VIDEO'
  const creatingBlocked = saving || approving || loading || editing || startingGeneration || fetchingScript || Boolean(productionAction)
  const runningStep = projectStatus?.production_steps?.find(step => step.state === 'RUNNING')

  function focusScript() {
    window.requestAnimationFrame(() => document.getElementById('script-preview-title')?.focus())
  }

  return (
    <div className="page-shell">
      <header className="site-header">
        <div className="brand" aria-label="Videostudio">
          <span className="brand-mark" aria-hidden="true"><span /></span>
          <span>VIDEOSTUDIO<span className="brand-dot">.</span></span>
        </div>
        <span className="header-note">PIPELINE V2 <span className="header-separator">/</span> PROJEKTE</span>
      </header>

      <main>
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow"><span className="eyebrow-line" /> IDEE → SKRIPT</p>
            <h1 id="hero-title">Deine Idee.<br /><em>Ein prüfbares Skript.</em></h1>
            <p className="hero-description">Beschreibe dein Video und wähle die spätere Bildquelle. Nach dem Speichern startet die Skripterstellung automatisch. Ein Video wird noch nicht produziert.</p>
            <div className="status-pill" role="status" aria-live="polite">
              <span className={`status-dot ${ready ? 'is-ready' : ''}`} aria-hidden="true" />
              {ready ? 'Technische Basis bereit' : reachable ? 'Dienste starten oder werden geprüft' : 'API derzeit nicht erreichbar'}
            </div>
            {checkingHealth && <LoadingBar label="Verbindung wird geprüft …" />}
          </div>

          <form className="project-form panel" onSubmit={(event) => void createProject(event)} noValidate aria-busy={saving}>
            <div className="section-heading"><span className="section-index">01 / STARTEN</span><h2>Neues Projekt</h2></div>
            <label htmlFor="video-idea" className="field-label">Deine Videoidee</label>
            <textarea id="video-idea" className="idea-input" value={idea}
              onChange={(event) => { setIdea(event.target.value); if (ideaError) setIdeaError('') }}
              placeholder="Zum Beispiel: Ein bienenfreundlicher Stadtbalkon in fünf Schritten"
              rows={5} disabled={creatingBlocked} aria-invalid={Boolean(ideaError)}
              aria-describedby={ideaError ? 'idea-error' : 'idea-hint'} />
            {ideaError
              ? <p className="field-error" id="idea-error" role="alert">{ideaError}</p>
              : <p className="field-hint" id="idea-hint">Ein kurzer Satz reicht für den ersten Test.</p>}

            <label htmlFor="video-mode" className="field-label mode-label">Bildquelle wählen</label>
            <select id="video-mode" className="mode-select" value={mode} disabled={creatingBlocked}
              onChange={(event) => setMode(event.target.value as Mode)}>
              <option value="LOKAL">LOKAL · Pexels-Videos</option>
              <option value="CLOUD">CLOUD · KI-generierte Videos</option>
            </select>
            <div className="mode-detail" aria-live="polite">
              <strong>{mediaType} · {mode === 'LOKAL' ? 'Pexels' : 'Wan'}</strong>
              <span>{mode === 'LOKAL' ? 'Ausschließlich Stockvideos von Pexels.' : 'Wan-Videos über Modal; die CLOUD-Produktion folgt.'}</span>
            </div>
            <button className="primary-button" type="submit" disabled={creatingBlocked} aria-busy={saving}>
              {saving ? 'Projekt wird gespeichert …' : 'Projekt speichern'}<span aria-hidden="true">→</span>
            </button>
            {saving && <LoadingBar label="Projekt wird gespeichert …" />}
            <p className="form-footnote">Das Speichern startet einen Skriptauftrag über Antigravity. Modal wird nicht verwendet.</p>
          </form>
        </section>

        <StorageSettings onAccess={setMediaAuthorized} />
        {(project || loading || saveError) && (
          <section className="saved-project panel" aria-labelledby="saved-title" aria-busy={loading}>
            <div className="saved-header">
              <div className="section-heading"><span className="section-index">02 / ZULETZT GESPEICHERT</span><h2 id="saved-title" tabIndex={-1}>Projektansicht</h2></div>
              {(project || lastProjectId.current) && <button className="text-button" type="button" onClick={() => void loadProject(project?.id ?? lastProjectId.current!)} disabled={loading || editing || approving || saving || Boolean(productionAction)} aria-busy={loading}>Neu laden</button>}
            </div>
            {loading && <LoadingBar label="Projekt und Skript werden geladen …" />}
            {saveError && <p className="notice-error" role="alert">{saveError}</p>}
            {project && <div className="project-data">
              <div><span className="data-label">IDEE</span><p className="saved-idea">{project.idea}</p></div>
              <div className="project-meta">
                <div><span className="data-label">MODUS</span><strong>{project.mode}</strong></div>
                <div><span className="data-label">MEDIENTYP</span><strong>{project.media_type}</strong></div>
                <div><span className="data-label">STATUS</span><strong>{projectStatus?.latest_script_version ? `Skriptversion ${projectStatus.latest_script_version}` : 'Idee gespeichert'}</strong></div>
              </div>
              <p className="project-id">Projekt-ID: <code>{project.id}</code></p>
              <div className="generation-area">
                <h3>Automatisches Skript</h3>
                {!script && <p>Der Hintergrund-Worker verwendet Antigravity mit einem angemeldeten Google-AI-Pro-Konto. Ohne eingerichteten Worker auf diesem Rechner erscheint ein Fehler.</p>}
                {!script && (!scriptJob || scriptJob.state === 'FAILED') && <button className="primary-button" type="button" onClick={() => void startGeneration()} disabled={startingGeneration || loading || saving} aria-busy={startingGeneration}>{startingGeneration ? 'Auftrag wird gestartet …' : scriptJob ? 'Skript erneut versuchen' : 'Skript automatisch erstellen'}</button>}
                {startingGeneration && <LoadingBar label="Skriptauftrag wird gestartet …" />}
                {!startingGeneration && !script && scriptJob && ['QUEUED', 'RUNNING'].includes(scriptJob.state) && <LoadingBar label={scriptJob.state === 'QUEUED' ? 'Skriptauftrag wartet auf den Worker …' : 'Antigravity erstellt das Skript …'} startedAt={scriptJob.created_at} />}
                {fetchingScript && <LoadingBar label="Fertiges Skript wird geladen …" />}
                {scriptJob?.state === 'FAILED' && <p className="notice-error" role="alert">{scriptJob.error_message}</p>}
                {generationError && <p className="notice-error" role="alert">{generationError}</p>}
                {!script && scriptJob?.state === 'COMPLETED' && generationError && <button className="secondary-button" type="button" onClick={() => void loadProject(project.id)} disabled={loading}>Skript erneut laden</button>}
                {script && !editing && <div className="script-preview"><p className="script-success" role="status">Skriptversion {script.version} gespeichert. Du kannst das Skript prüfen und bearbeiten.</p><h4 id="script-preview-title" tabIndex={-1}>{script.title}</h4><p>{script.scenes.length} Szenen · {script.target_duration_seconds ?? 'Dauer offen'} Sekunden</p><button className="secondary-button" type="button" onClick={() => setEditing(true)} disabled={approving || loading || saving || Boolean(productionAction)}>Skript bearbeiten</button><ol>{script.scenes.map((scene) => <li key={scene.position}><strong>Szene {scene.position}</strong><p>{scene.narration}</p><small>{scene.visual_description}</small><p className="field-hint">{project.mode === 'LOKAL' ? (scene.pexels_queries ?? (scene.pexels_query ? [scene.pexels_query] : [])).join(' · ') : scene.wan_prompt}</p></li>)}</ol>
                  <div className="approval-area" aria-labelledby="approval-title">
                    <h4 id="approval-title">Skriptfreigabe · Version {script.version}</h4>
                    <p>Mit der Freigabe startet die Produktion dieser Version. Änderungen benötigen eine neue Freigabe. Das fertige Video prüfst du anschließend vor der zweiten Freigabe.</p>
                    {newerScript && <p className="notice-error" role="alert">Eine neuere Version liegt vor. Bitte lade das Projekt neu.</p>}
                    {!scriptApproved && <button className="primary-button" type="button" onClick={() => void approveScript()} disabled={approving || loading || saving || Boolean(saveError) || newerScript} aria-busy={approving}>{approving ? 'Freigabe wird gespeichert …' : `Skriptversion ${script.version} freigeben`}</button>}
                    {approving && <LoadingBar label="Freigabe und Auftragsübergabe werden bestätigt …" />}
                    {scriptApproved && <div role="status" aria-live="polite"><p className="script-success">Skriptversion {script.version} freigegeben.</p>
                      {['QUEUED', 'RUNNING'].includes(projectStatus?.production_state ?? '')
                        ? <LoadingBar label={projectStatus?.production_cancel_requested ? 'Produktion wird abgebrochen …' : projectStatus?.production_state === 'QUEUED' ? 'Produktionsauftrag wartet auf die Verarbeitung …' : `${runningStep ? productionLabels[runningStep.name] : 'Videoproduktion'} …`} />
                        : <p>{projectStatus?.production_state === 'FAILED' ? 'Produktionsauftrag gestoppt.' : 'Produktion abgeschlossen.'}</p>}
                      {projectStatus?.production_error && <p className="notice-error">{projectStatus.production_error}</p>}
                      {Boolean(projectStatus?.production_steps?.length) && <ul className="production-step-list" aria-label="Produktionsschritte">{projectStatus!.production_steps!.map(step => <li key={step.id} className={`production-step ${step.state.toLowerCase()}`}><span>{productionLabels[step.name]}</span><span>{stepStates[step.state]}{step.attempts > 0 ? ` · Versuch ${step.attempts}/${step.max_attempts}` : ''}</span></li>)}</ul>}
                      {Boolean(projectStatus?.production_sources?.length) && <section className="scene-sources" aria-label="Szenenquellen">
                        <h3>Clips von <a href="https://www.pexels.com" target="_blank" rel="noopener noreferrer">Pexels</a></h3>
                        <ul>{projectStatus!.production_sources!.map(source => <li key={source.scene_position}>
                          <span>Szene {source.scene_position}</span>
                          <a href={source.video_page} target="_blank" rel="noopener noreferrer">Clip {source.video_id} ↗</a>
                          <span>von <a href={source.creator_page} target="_blank" rel="noopener noreferrer">{source.creator}</a></span>
                          <small>{source.width} × {source.height} · {source.duration_seconds.toFixed(1)} s</small>
                        </li>)}</ul>
                      </section>}
                      {Boolean(projectStatus?.production_speech?.length) && <section className="speech-segments" aria-label="Sprachsegmente">
                        <h3>Sprachsegmente</h3>
                        <p>{projectStatus!.production_speech![0].voice} · {new Intl.NumberFormat('de-DE', { maximumFractionDigits: 2 }).format(projectStatus!.production_speech!.reduce((total, segment) => total + segment.duration_seconds, 0))} s Sprache</p>
                        <ul>{projectStatus!.production_speech!.map(segment => <li key={segment.scene_position}>
                          <span>Szene {segment.scene_position}</span>
                          <strong>{new Intl.NumberFormat('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(segment.duration_seconds)} s</strong>
                        </li>)}</ul>
                      </section>}
                      {projectStatus?.production_graphics && <section className="speech-segments graphics-summary" aria-label="Gerenderte Grafiken">
                        <h3>Untertitel gerendert</h3>
                        <p>{projectStatus.production_graphics.scenes.length} Untertitel · {projectStatus.production_graphics.width} × {projectStatus.production_graphics.height} · {projectStatus.production_graphics.fps} fps</p>
                        <p>{new Intl.NumberFormat('de-DE', { maximumFractionDigits: 2 }).format(projectStatus.production_graphics.duration_frames / projectStatus.production_graphics.fps)} s geplante Videolänge</p>
                        <ul>{projectStatus.production_graphics.scenes.map(scene => <li key={scene.scene_position}>
                          <span>Untertitel {scene.scene_position}</span>
                          <strong>{new Intl.NumberFormat('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(scene.start_frame / projectStatus.production_graphics!.fps)}–{new Intl.NumberFormat('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format((scene.start_frame + scene.caption_frames) / projectStatus.production_graphics!.fps)} s</strong>
                        </li>)}</ul>
                      </section>}
                      {projectStatus?.production_encoding && <section className="speech-segments encoding-summary" aria-label="Encodiertes Video">
                        <h3>MP4 zusammengesetzt und geprüft</h3>
                        <p>{new Intl.NumberFormat('de-DE', { maximumFractionDigits: 2 }).format(projectStatus.production_encoding.duration_seconds)} s · {projectStatus.production_encoding.width} × {projectStatus.production_encoding.height} · {projectStatus.production_encoding.fps} fps</p>
                        <p>H.264 · AAC · {new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 }).format(projectStatus.production_encoding.size_bytes / 1024 / 1024)} MB</p>
                      </section>}
                      <div className="production-actions">
                        {projectStatus?.final_artifact_id && projectStatus.production_state === 'COMPLETED' && <VideoReview key={projectStatus.final_artifact_id} projectId={project.id} artifactId={projectStatus.final_artifact_id}
                          idea={project.idea} script={script} authorized={mediaAuthorized} approved={Boolean(projectStatus.video_approved)}
                          busy={loading || saving || approving || newerScript || Boolean(productionAction)}
                          sceneStarts={projectStatus.production_graphics?.scenes.map(scene => ({ scene_position: scene.scene_position, seconds: scene.start_frame / projectStatus.production_graphics!.fps }))}
                          duplicateClips={new Set(projectStatus.production_sources?.map(source => source.video_id)).size !== (projectStatus.production_sources?.length ?? 0)}
                          onApproved={() => setProjectStatus(current => current && activeProjectId.current === project.id && current.final_artifact_id === projectStatus.final_artifact_id ? { ...current, video_approved: true } : current)}
                          onEdit={() => { setEditing(true); focusScript() }} />}
                        {projectStatus?.production_can_resume && <button className="primary-button" type="button" onClick={() => void changeProduction('resume')} disabled={Boolean(productionAction) || loading || saving || Boolean(saveError) || newerScript} aria-busy={productionAction === 'resume'}>Produktion wiederaufnehmen</button>}
                        {['QUEUED', 'RUNNING'].includes(projectStatus?.production_state ?? '') && <button className="secondary-button" type="button" onClick={() => void changeProduction('cancel')} disabled={Boolean(productionAction) || Boolean(projectStatus?.production_cancel_requested) || loading || saving} aria-busy={productionAction === 'cancel'}>Produktion abbrechen</button>}
                      </div>
                      {productionAction && <LoadingBar label={productionAction === 'resume' ? 'Wiederaufnahme wird gespeichert …' : 'Abbruch wird gespeichert …'} />}
                    </div>}
                    {approvalError && <p className="notice-error" role="alert">{approvalError}</p>}
                  </div>
                </div>}
                {script && editing && <ScriptEditor projectId={project.id} mode={project.mode} script={script}
                  onSaved={(saved) => { setScript(saved); setEditing(false); setApprovalError(''); setProjectStatus({ latest_script_version: saved.version, script_approved: false, production_run_id: null, production_state: null, production_error: null }); focusScript() }}
                  onCancel={() => { setEditing(false); focusScript() }} onReload={() => { setEditing(false); void loadProject(project.id) }} />}
              </div>
            </div>}
          </section>
        )}

        <section className="content-grid" aria-label="Entwicklungsstand">
          <div className="panel workflow-panel">
            <div className="section-heading"><span className="section-index">03 / ABLAUF</span><h2>Was schon möglich ist</h2></div>
            <ol className="workflow-list">
              <li><span className="step-number">01</span><div><h3>Idee speichern</h3><p>Projekt und Modus werden in PostgreSQL gesichert.</p></div><span className="step-tag available"><span aria-hidden="true">✓ </span>Verfügbar</span></li>
              <li><span className="step-number">02</span><div><h3>Skript erzeugen</h3><p>Nach dem Speichern entsteht das Skript automatisch über dein angemeldetes Pro-Konto.</p></div><span className="step-tag available"><span aria-hidden="true">✓ </span>Verfügbar</span></li>
              <li><span className="step-number">03</span><div><h3>Skript bearbeiten</h3><p>Texte, Szenendauer und Bildvorgaben prüfen. Speichern erstellt eine neue Version.</p></div><span className="step-tag available"><span aria-hidden="true">✓ </span>Verfügbar</span></li>
              <li><span className="step-number">04</span><div><h3>Skript freigeben</h3><p>Die geprüfte Version bestätigen und ihren Produktionsauftrag speichern.</p></div><span className="step-tag available"><span aria-hidden="true">✓ </span>Verfügbar</span></li>
              <li><span className="step-number">05</span><div><h3>Pexels-Clips beschaffen</h3><p>Freigegebene LOKAL-Szenen erhalten geprüfte Clips mit verlinkten Quellen.</p></div><span className="step-tag available"><span aria-hidden="true">✓ </span>Verfügbar</span></li>
              <li><span className="step-number">06</span><div><h3>Sprache erzeugen</h3><p>Deutsche Sprechertexte werden szenenweise vertont; die gemessenen Dauern bleiben gespeichert.</p></div><span className="step-tag available"><span aria-hidden="true">✓ </span>Verfügbar</span></li>
              <li><span className="step-number">07</span><div><h3>Untertitel rendern</h3><p>Untertitel erhalten sichere Ränder und Zeitdaten passend zu den Sprachsegmenten.</p></div><span className="step-tag available"><span aria-hidden="true">✓ </span>Verfügbar</span></li>
              <li><span className="step-number">08</span><div><h3>Video ansehen</h3><p>Eingabe und Ausgabe vergleichen, Szenen prüfen und das fertige Video freigeben.</p></div><span className="step-tag available">Verfügbar</span></li>
            </ol>
          </div>
          <div className="panel systems-panel">
            <div className="section-heading"><span className="section-index">04 / SYSTEM</span><h2>Technischer Status</h2></div>
            <p className="systems-intro">Live-Status der Dienste im Hintergrund. Die Anzeige aktualisiert sich alle zehn Sekunden.</p>
            <ul className="service-list">
              {(Object.keys(serviceLabels) as (keyof Services)[]).map((key) => {
                const online = reachable && health?.services[key] === true
                return <li key={key}><span className="service-name"><span className={`service-indicator ${online ? 'online' : ''}`} aria-hidden="true" />{serviceLabels[key]}</span><span className={`service-state ${online ? 'online' : ''}`}>{online ? 'Bereit' : 'Wartet'}</span></li>
              })}
            </ul>
            <p className="panel-footnote">LOKAL beschafft Pexels-Clips. Die CLOUD-Beschaffung folgt.</p>
          </div>
        </section>
      </main>
      <footer className="site-footer"><span>VIDEOSTUDIO / V2</span><span>Skript erstellen, bearbeiten und freigeben</span></footer>
    </div>
  )
}
