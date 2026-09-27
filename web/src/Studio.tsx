import { useEffect, useState, type FormEvent } from 'react'

type Mode = 'LOKAL' | 'CLOUD'
type MediaType = 'STOCK_VIDEO' | 'AI_GENERATED_VIDEO'
type Services = { database: boolean; redis: boolean; worker: boolean }
type Health = { status: 'ready' | 'waiting'; services: Services }
type Project = { id: string; idea: string; mode: Mode; media_type: MediaType; created_at: string }
type ProjectStatus = { latest_script_version: number | null; production_state: string | null }

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
      setProjectStatus(await statusResponse.json() as ProjectStatus)
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
      setProjectStatus({ latest_script_version: null, production_state: null })
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
            <p className="eyebrow"><span className="eyebrow-line" /> SCHRITT 09 · PROJEKT ANLEGEN</p>
            <h1 id="hero-title">Deine Idee.<br /><em>Ein echtes Projekt.</em></h1>
            <p className="hero-description">Beschreibe dein Video und wähle, woher die Bilder später kommen. Deine Idee wird jetzt in der Datenbank gespeichert. Skript und Video folgen in den nächsten Entwicklungsschritten.</p>
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
            </div>}
          </section>
        )}

        <section className="content-grid" aria-label="Entwicklungsstand">
          <div className="panel workflow-panel">
            <div className="section-heading"><span className="section-index">03 / ABLAUF</span><h2>Was schon möglich ist</h2></div>
            <ol className="workflow-list">
              <li><span className="step-number">01</span><div><h3>Idee speichern</h3><p>Projekt und Modus werden in PostgreSQL gesichert.</p></div><span className="step-tag available">Jetzt testen</span></li>
              <li><span className="step-number">02</span><div><h3>Skript prüfen</h3><p>Die automatische Gemini-Pro-Integration folgt.</p></div><span className="step-tag">Folgt</span></li>
              <li><span className="step-number">03</span><div><h3>Video ansehen</h3><p>Produktion und Vorschau sind noch nicht aktiv.</p></div><span className="step-tag">Folgt</span></li>
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
            <p className="panel-footnote">LOKAL und CLOUD wählen derzeit nur die spätere Bildquelle. Es wird noch kein Video erzeugt.</p>
          </div>
        </section>
      </main>
      <footer className="site-footer"><span>VIDEOSTUDIO / V2</span><span>Entwicklungsstand · Schritt 9</span></footer>
    </div>
  )
}
