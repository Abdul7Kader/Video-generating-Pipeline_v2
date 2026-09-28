export type EditorMode = 'LOKAL' | 'CLOUD'

export type EditableScene = {
  narration: string
  visual_description: string
  pexels_query: string | null
  wan_prompt: string | null
}

export type ScriptPayload = {
  expected_version: number
  title: string
  narration: string
  scenes: EditableScene[]
}

export function buildScriptPayload(
  mode: EditorMode, version: number, titleInput: string, scenes: EditableScene[],
): { payload?: ScriptPayload; error?: string } {
  const title = titleInput.trim()
  const sourceField = mode === 'LOKAL' ? 'pexels_query' : 'wan_prompt'
  if (!title || scenes.length < 6 || scenes.length > 10 || scenes.some((scene) =>
    !scene.narration.trim() || !scene.visual_description.trim() || !scene[sourceField]?.trim())) {
    return { error: 'Bitte fülle Titel, Sprechertext, Bildbeschreibung und alle modusspezifischen Suchbegriffe oder Prompts aus.' }
  }
  const cleanedScenes = scenes.map((scene) => ({
    narration: scene.narration.trim(),
    visual_description: scene.visual_description.trim(),
    pexels_query: mode === 'LOKAL' ? scene.pexels_query!.trim() : null,
    wan_prompt: mode === 'CLOUD' ? scene.wan_prompt!.trim() : null,
  }))
  return {
    payload: {
      expected_version: version, title,
      narration: cleanedScenes.map((scene) => scene.narration).join('\n\n'),
      scenes: cleanedScenes,
    },
  }
}
