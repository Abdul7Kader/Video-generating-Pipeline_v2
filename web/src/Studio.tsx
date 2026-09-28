import { useEffect, useState, type FormEvent } from 'react'
import { buildScriptPayload } from './editor-model'

type Mode = 'LOKAL' | 'CLOUD'
type MediaType = 'STOCK_VIDEO' | 'AI_GENERATED_VIDEO'
type Services = { database: boolean; redis: boolean; worker: boolean }
type Health = { status: 'ready' | 'waiting'; services: Services }
type Project = { id: string; idea: string; mode: Mode; media_type: MediaType; created_at: string }
type Generation = { state: 'QUEUED' | 'RUNNING' | 'FAILED' | 'COMPLETED'; error_message: string | null; script_version: number | null }
type ProjectStatus = { latest_script_version: number | null; production_state: string | null; script_generation: Generation | null }
type Scene = { position: number; narration: string; visual_description: string; media_type: MediaType; pexels_query: string | null; wan_prompt: string | null }
type Script = { id: string; project_id: string; version: number; title: string; narration: string; scenes: Scene[]; created_at: string }

const STORAGE_KEY = 'videostudio:last-project-id'
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
  const [generation, setGeneration] = useState<Generation | null>(null)
  const [generating, setGenerating] = useState(false)
  const [script, setScript] = useState<Script | null>(null)
  const [draftTitle, setDraftTitle] = useState('')
  const [draftScenes, setDraftScenes] = useState<Scene[]>([])
  const [scriptError, setScriptError] = useState('')
  const [savingScript, setSavingScript] = useState(false)
  const [savedMessage, setSavedMessage] = useState('')

  useEffect(() => {
    let active = true
    async function updateHealth() {
      try {
        const response = await fetch('/api/health/ready', { cache: 'no-store' })
        const result: Health = await response.json()
        if (active) { setHealth(result); setReachable(true) }
      } catch {
        if (active) { setHealth(null); setReachable(false) }
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
        fetch(`/api/projects/${encodeURIComponent(id)}`, { cache: 'no-store' }),
        fetch(`/api/projects/${encodeURIComponent(id)}/status`, { cache: 'no-store' }),
      ])
      if (!projectResponse.ok || !statusResponse.ok) throw new Error()
      setProject(await projectResponse.json() as Project)
      const status = await statusResponse.json() as ProjectStatus
      setProjectStatus(status)
      setGeneration(status.script_generation)
      if (status.latest_script_version) {
        const scriptResponse = await fetch(`/api/projects/${encodeURIComponent(id)}/scripts/${status.latest_script_version}`, { cache: 'no-store' })
        if (!scriptResponse.ok) throw new Error()
        const latest = await scriptResponse.json() as Script
        setScript(latest)
        setDraftTitle(latest.title)
        setDraftScenes(latest.scenes)
      } else {
        setScript(null); setDraftTitle(''); setDraftScenes([])
      }
      setSaveError('')
    } catch {
      setSaveError('Das gespeicherte Projekt konnte nicht geladen werden. Bitte versuche es erneut.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const id = window.localStorage.getItem(STORAGE_KEY)
    if (id) void loadProject(id)
  }, [])

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (saving) return
    const cleanedIdea = idea.trim()
    if (!cleanedIdea) { setIdeaError('Bitte beschreibe zuerst deine Videoidee.'); return }
    setIdeaError('')
    setSaveError('')
    setSaving(true)
    try {
      const response = await fetch('/api/projects', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idea: cleanedIdea, mode }),
      })
      if (!response.ok) throw new Error(await responseError(response))
      const saved = await response.json() as Project
      window.localStorage.setItem(STORAGE_KEY, saved.id)
      setProject(saved)
      setProjectStatus({ latest_script_version: null, production_state: null, script_generation: null })
      setGeneration(null)
      setScript(null)
      setIdea('')
      await loadProject(saved.id)
      window.requestAnimationFrame(() => {
        document.getElementById('saved-title')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Das Projekt konnte nicht gespeichert werden.')
    } finally {
      setSaving(false)
    }
  }

  function updateScene(index: number, field: 'narration' | 'visual_description' | 'pexels_query' | 'wan_prompt', value: string) {
    setDraftScenes((current) => current.map((scene, sceneIndex) => sceneIndex === index ? { ...scene, [field]: value } : scene))
    setSavedMessage('')
  }

  function addScene() {
    if (!project || draftScenes.length >= 10) return
    const isLocal = project.mode === 'LOKAL'
    setDraftScenes((current) => [...current, {
      position: current.length + 1, narration: '', visual_description: '', media_type: project.media_type,
      pexels_query: isLocal ? '' : null, wan_prompt: isLocal ? null : '',
    }])
    setSavedMessage('')
  }

  function removeScene(index: number) {
    if (draftScenes.length <= 6) return
    setDraftScenes((current) => current.filter((_, sceneIndex) => sceneIndex !== index)
      .map((scene, sceneIndex) => ({ ...scene, position: sceneIndex + 1 })))
    setSavedMessage('')
  }

  async function saveScript() {
    if (!project || !script || savingScript) return
    const result = buildScriptPayload(project.mode, script.version, draftTitle, draftScenes)
    if (!result.payload) {
      setScriptError(result.error ?? 'Bitte prüfe deine Eingaben.')
      return
    }
    setSavingScript(true); setScriptError(''); setSavedMessage('')
    try {
      const response = await fetch(`/api/projects/${encodeURIComponent(project.id)}/scripts`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(result.payload),
      })
      if (!response.ok) {
        const message = response.status === 409
          ? 'Das Skript wurde zwischenzeitlich geändert. Lade die aktuelle Version neu und übertrage deine Änderungen erneut.'
          : await responseError(response)
        throw new Error(message)
      }
      const saved = await response.json() as Script
      setScript(saved); setDraftTitle(saved.title); setDraftScenes(saved.scenes)
      setProjectStatus((current) => current ? { ...current, latest_script_version: saved.version } : current)
      setSavedMessage(`Skriptversion ${saved.version} wurde unveränderlich gespeichert.`)
    } catch (error) {
      setScriptError(error instanceof Error ? error.message : 'Das Skript konnte nicht gespeichert werden.')
    } finally {
      setSavingScript(false)
    }
  }

  async function startGeneration() {
    if (!project || generating) return
    setGenerating(true)
    setSaveError('')
    try {
      const response = await fetch(`/api/projects/${encodeURIComponent(project.id)}/script-generation`, { method: 'POST' })
      if (!response.ok) throw new Error(await responseError(response))
      setGeneration(await response.json() as Generation)
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Der Skriptauftrag konnte nicht gestartet werden.')
    } finally {
      setGenerating(false)
    }
  }

  useEffect(() => {
    if (!project || !generation || !['QUEUED', 'RUNNING'].includes(generation.state)) return
    const timer = window.setInterval(() => void loadProject(project.id), 2500)
    return () => window.clearInterval(timer)
  }, [project?.id, generation?.state])

  const ready = reachable && health?.status === 'ready'
  const mediaType = mode === 'LOKAL' ? 'STOCK_VIDEO' : 'AI_GENERATED_VIDEO'

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
            <p className="eyebrow"><span className="eyebrow-line" /> SCHRITT 11 · SKRIPT BEARBEITEN</p>
            <h1 id="hero-title">Deine Idee.<br /><em>Dein fertiges Skript.</em></h1>
            <p className="hero-description">Erzeuge dein Skript automatisch und bearbeite danach Titel, Sprechertexte, Bildbeschreibungen und die passende Bildquelle. Jede Speicherung legt eine neue, nachvollziehbare Version an.</p>
            <div className="status-pill" role="status" aria-live="polite">
              <span className={`status-dot ${ready ? 'is-ready' : ''}`} aria-hidden="true" />
              {ready ? 'Technische Basis bereit' : reachable ? 'Dienste starten oder werden geprüft' : 'API derzeit nicht erreichbar'}
            </div>
          </div>

          <form className="project-form panel" onSubmit={(event) => void createProject(event)} noValidate>
            <div className="section-heading"><span className="section-index">01 / STARTEN</span><h2>Neues Projekt</h2></div>
            <label htmlFor="video-idea" className="field-label">Deine Videoidee</label>
            <textarea id="video-idea" className="idea-input" value={idea}
              onChange={(event) => { setIdea(event.target.value); if (ideaError) setIdeaError('') }}
              placeholder="Zum Beispiel: Ein bienenfreundlicher Stadtbalkon in fünf Schritten"
              rows={5} aria-invalid={Boolean(ideaError)}
              aria-describedby={ideaError ? 'idea-error' : 'idea-hint'} />
            {ideaError
              ? <p className="field-error" id="idea-error" role="alert">{ideaError}</p>
              : <p className="field-hint" id="idea-hint">Ein kurzer Satz reicht für den ersten Test.</p>}

            <label htmlFor="video-mode" className="field-label mode-label">Bildquelle wählen</label>
            <select id="video-mode" className="mode-select" value={mode}
              onChange={(event) => setMode(event.target.value as Mode)}>
              <option value="LOKAL">LOKAL · Pexels-Videos</option>
              <option value="CLOUD">CLOUD · KI-generierte Videos</option>
            </select>
            <div className="mode-detail" aria-live="polite">
              <strong>{mediaType} · {mode === 'LOKAL' ? 'Pexels' : 'Wan'}</strong>
              <span>{mode === 'LOKAL' ? 'Später ausschließlich Stockvideos von Pexels.' : 'Später ausschließlich Wan-Videos über Modal.'}</span>
            </div>
            <button className="primary-button" type="submit" disabled={saving}>
              {saving ? 'Projekt wird gespeichert …' : 'Projekt speichern'}<span aria-hidden="true">→</span>
            </button>
            <p className="form-footnote">Das Speichern startet noch keine Skript- oder Videoerstellung und verursacht keine Modal-Kosten.</p>
          </form>
        </section>

        {(project || loading || saveError) && (
          <section className="saved-project panel" aria-labelledby="saved-title">
            <div className="saved-header">
              <div className="section-heading"><span className="section-index">02 / ZULETZT GESPEICHERT</span><h2 id="saved-title">Projektansicht</h2></div>
              {project && <button className="text-button" type="button" onClick={() => void loadProject(project.id)} disabled={loading}>Aus Datenbank neu laden</button>}
            </div>
            {loading && <p className="saved-note" role="status">Gespeichertes Projekt wird geladen …</p>}
            {saveError && <p className="notice-error" role="alert">{saveError}</p>}
            {project && <div className="project-data">
              <div><span className="data-label">IDEE</span><p className="saved-idea">{project.idea}</p></div>
              <div className="project-meta">
                <div><span className="data-label">MODUS</span><strong>{project.mode}</strong></div>
                <div><span className="data-label">MEDIENTYP</span><strong>{project.media_type}</strong></div>
                <div><span className="data-label">STATUS</span><strong>{projectStatus?.latest_script_version ? `Skriptversion ${projectStatus.latest_script_version}` : 'Idee gespeichert'}</strong></div>
              </div>
              <p className="project-id">Projekt-ID: <code>{project.id}</code></p>
              <div className="generation-box">
                <div><span className="data-label">AUTOMATISCHES SKRIPT</span>
                  <p>{generation?.state === 'COMPLETED' ? `Skriptversion ${generation.script_version} wurde validiert und gespeichert.`
                    : generation?.state === 'FAILED' ? generation.error_message
                    : generation ? 'Der Hintergrund-Worker bearbeitet den Auftrag …'
                    : 'Bereit zum bewussten Start. Es gibt keine automatische kostenpflichtige Wiederholung.'}</p></div>
                <button className="primary-button generation-button" type="button" onClick={() => void startGeneration()}
                  disabled={generating || generation?.state === 'QUEUED' || generation?.state === 'RUNNING'}>
                  {generation?.state === 'FAILED' ? 'Bewusst erneut versuchen' : generation?.state === 'COMPLETED' ? 'Neues Skript erzeugen' : generation ? 'Skript wird erzeugt …' : 'Skript automatisch erzeugen'}
                  <span aria-hidden="true">→</span>
                </button>
              </div>
            </div>}
          </section>
        )}

        {project && script && (
          <section className="script-editor panel" aria-labelledby="editor-title">
            <div className="editor-header">
              <div className="section-heading">
                <span className="section-index">03 / SKRIPT BEARBEITEN</span>
                <h2 id="editor-title">Skriptversion {script.version}</h2>
              </div>
              <span className="version-badge">Aktuelle Basis · v{script.version}</span>
            </div>
            <label className="field-label" htmlFor="script-title">Videotitel</label>
            <input id="script-title" className="idea-input title-input" value={draftTitle}
              maxLength={120} onChange={(event) => { setDraftTitle(event.target.value); setSavedMessage('') }} />

            <div className="scene-list">
              {draftScenes.map((scene, index) => (
                <fieldset className="scene-card" key={`${script.id}-${index}`}>
                  <legend>Szene {index + 1}</legend>
                  <button className="remove-scene" type="button" disabled={draftScenes.length <= 6}
                    onClick={() => removeScene(index)} aria-label={`Szene ${index + 1} entfernen`}>Entfernen</button>
                  <label className="field-label" htmlFor={`narration-${index}`}>Sprechertext</label>
                  <textarea id={`narration-${index}`} className="idea-input scene-textarea" maxLength={400}
                    value={scene.narration} onChange={(event) => updateScene(index, 'narration', event.target.value)} />
                  <label className="field-label" htmlFor={`visual-${index}`}>Bildbeschreibung</label>
                  <textarea id={`visual-${index}`} className="idea-input scene-textarea" maxLength={600}
                    value={scene.visual_description} onChange={(event) => updateScene(index, 'visual_description', event.target.value)} />
                  <label className="field-label" htmlFor={`source-${index}`}>
                    {project.mode === 'LOKAL' ? 'Pexels-Suchbegriffe' : 'Wan-Prompt'}
                  </label>
                  <textarea id={`source-${index}`} className="idea-input scene-textarea source-input"
                    maxLength={project.mode === 'LOKAL' ? 400 : 1000}
                    value={(project.mode === 'LOKAL' ? scene.pexels_query : scene.wan_prompt) ?? ''}
                    onChange={(event) => updateScene(index, project.mode === 'LOKAL' ? 'pexels_query' : 'wan_prompt', event.target.value)} />
                </fieldset>
              ))}
            </div>
            <div className="editor-actions">
              <button className="secondary-button" type="button" onClick={addScene} disabled={draftScenes.length >= 10}>+ Szene hinzufügen</button>
              <button className="primary-button save-script" type="button" onClick={() => void saveScript()} disabled={savingScript}>
                {savingScript ? 'Neue Version wird gespeichert …' : 'Als neue Version speichern'}<span aria-hidden="true">→</span>
              </button>
            </div>
            {scriptError && <p className="notice-error" role="alert">{scriptError}</p>}
            {savedMessage && <p className="saved-note" role="status">{savedMessage}</p>}
            <p className="form-footnote">Die bisherige Version bleibt unverändert erhalten. Bei einem Versionskonflikt werden keine Eingaben überschrieben.</p>
          </section>
        )}

        <section className="content-grid" aria-label="Entwicklungsstand">
          <div className="panel workflow-panel">
            <div className="section-heading"><span className="section-index">04 / ABLAUF</span><h2>Was schon möglich ist</h2></div>
            <ol className="workflow-list">
              <li><span className="step-number">01</span><div><h3>Idee speichern</h3><p>Projekt und Modus werden in PostgreSQL gesichert.</p></div><span className="step-tag available">Jetzt testen</span></li>
              <li><span className="step-number">02</span><div><h3>Skript bearbeiten</h3><p>Szenen und Quellenangaben werden als neue Version gespeichert.</p></div><span className="step-tag available">Jetzt testen</span></li>
              <li><span className="step-number">03</span><div><h3>Video ansehen</h3><p>Produktion und Vorschau sind noch nicht aktiv.</p></div><span className="step-tag">Folgt</span></li>
            </ol>
          </div>
          <div className="panel systems-panel">
            <div className="section-heading"><span className="section-index">05 / SYSTEM</span><h2>Technischer Status</h2></div>
            <p className="systems-intro">Live-Status der Dienste im Hintergrund. Die Anzeige aktualisiert sich alle zehn Sekunden.</p>
            <ul className="service-list">
              {(Object.keys(serviceLabels) as (keyof Services)[]).map((key) => {
                const online = reachable && health?.services[key] === true
                return <li key={key}><span className="service-name"><span className={`service-indicator ${online ? 'online' : ''}`} aria-hidden="true" />{serviceLabels[key]}</span><span className={`service-state ${online ? 'online' : ''}`}>{online ? 'Bereit' : 'Wartet'}</span></li>
              })}
            </ul>
            <p className="panel-footnote">LOKAL und CLOUD wählen derzeit nur die spätere Bildquelle. Es wird noch kein Video erzeugt.</p>
          </div>
        </section>
      </main>
      <footer className="site-footer"><span>VIDEOSTUDIO / V2</span><span>Entwicklungsstand · Schritt 11</span></footer>
    </div>
  )
}
