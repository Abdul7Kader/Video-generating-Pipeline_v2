import { useEffect, useState } from 'react'

type Services = { database: boolean; redis: boolean; worker: boolean }
type Health = { status: 'ready' | 'waiting'; services: Services }

const labels: Record<keyof Services, string> = {
  database: 'Datenbank',
  redis: 'Warteschlange',
  worker: 'Hintergrund-Worker',
}

function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [reachable, setReachable] = useState(true)

  useEffect(() => {
    let active = true
    async function updateHealth() {
      try {
        const response = await fetch('/api/health/ready', { cache: 'no-store' })
        const result: Health = await response.json()
        if (active) {
          setHealth(result)
          setReachable(true)
        }
      } catch {
        if (active) {
          setHealth(null)
          setReachable(false)
        }
      }
    }
    void updateHealth()
    const timer = window.setInterval(() => void updateHealth(), 10000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  const ready = reachable && health?.status === 'ready'

  return (
    <div className="page-shell">
      <header className="site-header">
        <div className="brand" aria-label="Videostudio">
          <span className="brand-mark" aria-hidden="true"><span /></span>
          <span>VIDEOSTUDIO<span className="brand-dot">.</span></span>
        </div>
        <span className="header-note">PIPELINE V2 <span className="header-separator">/</span> ENTWICKLUNG</span>
      </header>

      <main>
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow"><span className="eyebrow-line" /> DEIN WORKSPACE FÜR VIDEOS</p>
            <h1 id="hero-title">Eine Idee.<br /><em>Ein fertiges Video.</em></h1>
            <p className="hero-description">Hier entsteht dein automatisierter Weg von der Videoidee bis zur Vorschau. Die technische Basis läuft bereits; Skripte und Videos kommen in den nächsten Schritten hinzu.</p>
            <div className="status-pill" role="status" aria-live="polite">
              <span className={`status-dot ${ready ? 'is-ready' : ''}`} aria-hidden="true" />
              {ready ? 'Technische Basis bereit' : reachable ? 'Dienste starten oder werden geprüft' : 'API derzeit nicht erreichbar'}
            </div>
          </div>
          <div className="hero-visual" aria-hidden="true">
            <div className="visual-top"><span>PREVIEW / 9:16</span><span>00:00</span></div>
            <div className="visual-center"><div className="play-shape" /></div>
            <div className="visual-bottom"><span>DEIN VIDEO ENTSTEHT HIER</span><span className="visual-bars"><i /><i /><i /><i /><i /></span></div>
          </div>
        </section>

        <section className="content-grid" aria-label="Projektstatus">
          <div className="panel workflow-panel">
            <div className="section-heading"><span className="section-index">01 / ABLAUF</span><h2>So wird dein Video entstehen</h2></div>
            <ol className="workflow-list">
              <li><span className="step-number">01</span><div><h3>Idee eingeben</h3><p>Thema beschreiben und LOKAL oder CLOUD wählen.</p></div><span className="step-tag">Folgt</span></li>
              <li><span className="step-number">02</span><div><h3>Skript prüfen</h3><p>Gemini Pro erstellt es automatisch zur Freigabe.</p></div><span className="step-tag">Folgt</span></li>
              <li><span className="step-number">03</span><div><h3>Video ansehen</h3><p>Produktion und fertigen Clip hier prüfen.</p></div><span className="step-tag">Folgt</span></li>
            </ol>
          </div>

          <div className="panel systems-panel">
            <div className="section-heading"><span className="section-index">02 / SYSTEM</span><h2>Technischer Status</h2></div>
            <p className="systems-intro">Live-Status der Dienste im Hintergrund. Die Anzeige aktualisiert sich alle zehn Sekunden.</p>
            <ul className="service-list">
              {(Object.keys(labels) as (keyof Services)[]).map((key) => {
                const online = reachable && health?.services[key] === true
                return <li key={key}><span className="service-name"><span className={`service-indicator ${online ? 'online' : ''}`} aria-hidden="true" />{labels[key]}</span><span className={`service-state ${online ? 'online' : ''}`}>{online ? 'Bereit' : 'Wartet'}</span></li>
              })}
            </ul>
            <p className="panel-footnote">Noch keine Videoerstellung aktiv. Dieser Schritt richtet die Infrastruktur ein.</p>
          </div>
        </section>
      </main>

      <footer className="site-footer"><span>VIDEOSTUDIO / V2</span><span>Entwicklungsstand · Schritt 6</span></footer>
    </div>
  )
}

export default App
