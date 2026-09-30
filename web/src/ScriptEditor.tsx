import { useState, type FormEvent } from 'react'

export type ScriptScene = {
  position: number; narration: string; visual_description: string; duration_seconds: number | null;
  pexels_queries: string[] | null; pexels_query: string | null; wan_prompt: string | null;
}
export type Script = {
  title: string; version: number; narration: string; language: 'de-DE';
  target_duration_seconds: number | null; scenes: ScriptScene[];
}

type Props = {
  projectId: string; mode: 'LOKAL' | 'CLOUD'; script: Script;
  onSaved: (script: Script) => void; onCancel: () => void; onReload: () => void;
}

export default function ScriptEditor({ projectId, mode, script, onSaved, onCancel, onReload }: Props) {
  // Keep an independent draft; a version conflict must not discard the user's edits.
  // https://react.dev/reference/react/useState#updating-objects-and-arrays-in-state
  const [draft, setDraft] = useState(script)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [conflict, setConflict] = useState(false)
  const total = draft.scenes.reduce((sum, scene) => sum + (scene.duration_seconds ?? 0), 0)

  function updateScene(position: number, changes: Partial<ScriptScene>) {
    setDraft((current) => ({ ...current, scenes: current.scenes.map((scene) => scene.position === position ? { ...scene, ...changes } : scene) }))
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (saving) return
    setError('')
    setConflict(false)
    if (total < 30 || total > 60) { setError('Die Gesamtdauer muss zwischen 30 und 60 Sekunden liegen.'); return }
    const scenes = draft.scenes.map((scene) => ({
      narration: scene.narration.trim(), visual_description: scene.visual_description.trim(),
      duration_seconds: scene.duration_seconds,
      ...(mode === 'LOKAL'
        ? { pexels_queries: (scene.pexels_queries ?? []).map((query) => query.trim()).filter(Boolean) }
        : { wan_prompt: scene.wan_prompt?.trim() }),
    }))
    setSaving(true)
    try {
      const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/scripts`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expected_version: draft.version, title: draft.title.trim(),
          narration: scenes.map((scene) => scene.narration).join(' '), language: draft.language,
          target_duration_seconds: total, scenes }),
      })
      const body = await response.json()
      if (!response.ok) {
        if (response.status === 409) {
          setConflict(true)
          throw new Error('Inzwischen wurde eine neue Version gespeichert. Deine Eingaben bleiben hier erhalten. Vergleiche sie vor dem Neuladen.')
        }
        throw new Error(body.error?.code === 'VALIDATION_ERROR' ? 'Bitte prüfe alle Eingabefelder.' : body.error?.message || 'Das Skript konnte nicht gespeichert werden.')
      }
      onSaved(body as Script)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Das Skript konnte nicht gespeichert werden.')
    } finally {
      setSaving(false)
    }
  }

  return <form className="script-editor" onSubmit={(event) => void save(event)}>
    <h4>Skript bearbeiten · Version {draft.version}</h4>
    <p>Speichern erstellt eine neue Version. {draft.scenes.length} Szenen · {total} Sekunden insgesamt.</p>
    <fieldset disabled={saving}>
      <label className="field-label" htmlFor="script-title">Videotitel</label>
      <input id="script-title" className="editor-input" value={draft.title} required maxLength={120}
        onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))} />
      {draft.scenes.map((scene) => <section className="editor-scene" key={scene.position} aria-labelledby={`scene-${scene.position}-title`}>
        <h5 id={`scene-${scene.position}-title`}>Szene {scene.position}</h5>
        <label className="field-label" htmlFor={`scene-${scene.position}-duration`}>Dauer in Sekunden</label>
        <input id={`scene-${scene.position}-duration`} className="editor-input duration-input" type="number" min={3} max={12} step={1} required
          value={scene.duration_seconds ?? ''} onChange={(event) => updateScene(scene.position, { duration_seconds: Number(event.target.value) })} />
        <label className="field-label" htmlFor={`scene-${scene.position}-narration`}>Sprechertext</label>
        <textarea id={`scene-${scene.position}-narration`} className="editor-input" rows={3} required maxLength={400}
          value={scene.narration} onChange={(event) => updateScene(scene.position, { narration: event.target.value })} />
        <label className="field-label" htmlFor={`scene-${scene.position}-visual`}>Bildbeschreibung</label>
        <textarea id={`scene-${scene.position}-visual`} className="editor-input" rows={3} required maxLength={600}
          value={scene.visual_description} onChange={(event) => updateScene(scene.position, { visual_description: event.target.value })} />
        {mode === 'LOKAL' ? <>
          <label className="field-label" htmlFor={`scene-${scene.position}-queries`}>Pexels-Suchbegriffe · 2 bis 4, je eine Zeile</label>
          <textarea id={`scene-${scene.position}-queries`} className="editor-input" rows={3} required
            value={(scene.pexels_queries ?? (scene.pexels_query ? [scene.pexels_query] : [])).join('\n')}
            onChange={(event) => updateScene(scene.position, { pexels_queries: event.target.value.split('\n') })} />
        </> : <>
          <label className="field-label" htmlFor={`scene-${scene.position}-wan`}>Wan-Prompt auf Englisch</label>
          <textarea id={`scene-${scene.position}-wan`} className="editor-input" rows={4} required maxLength={1000}
            value={scene.wan_prompt ?? ''} onChange={(event) => updateScene(scene.position, { wan_prompt: event.target.value })} />
        </>}
      </section>)}
      <div className="editor-actions">
        <button className="secondary-button" type="submit">{saving ? 'Version wird gespeichert …' : 'Neue Version speichern'}</button>
        <button className="text-button" type="button" onClick={onCancel}>Änderungen verwerfen</button>
      </div>
    </fieldset>
    {error && <p className="notice-error" role="alert">{error}</p>}
    {conflict && <button className="text-button" type="button" onClick={onReload}>Änderungen verwerfen und aktuelle Version laden</button>}
  </form>
}
