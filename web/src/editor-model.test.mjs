import assert from 'node:assert/strict'
import test from 'node:test'

import { buildScriptPayload } from './editor-model.ts'

const localScenes = Array.from({ length: 6 }, (_, index) => ({
  narration: ` Text ${index + 1} `,
  visual_description: ` Bild ${index + 1} `,
  pexels_query: ` rain city ${index + 1} `,
  wan_prompt: null,
}))

test('erstellt eine bereinigte LOKAL-Version mit ausschließlich Pexels-Feldern', () => {
  const result = buildScriptPayload('LOKAL', 3, ' Neuer Titel ', localScenes)
  assert.equal(result.error, undefined)
  assert.equal(result.payload.expected_version, 3)
  assert.equal(result.payload.title, 'Neuer Titel')
  assert.equal(result.payload.scenes[0].pexels_query, 'rain city 1')
  assert.equal(result.payload.scenes[0].wan_prompt, null)
  assert.equal(result.payload.narration.split('\n\n').length, 6)
})

test('erstellt CLOUD-Szenen ohne stille Pexels-Quelle', () => {
  const cloud = localScenes.map((scene, index) => ({ ...scene, pexels_query: null, wan_prompt: ` cinematic rain ${index + 1} ` }))
  const result = buildScriptPayload('CLOUD', 1, 'Regen', cloud)
  assert.equal(result.payload.scenes[0].pexels_query, null)
  assert.equal(result.payload.scenes[0].wan_prompt, 'cinematic rain 1')
})

test('weist unvollständige Felder und unzulässige Szenenzahlen ab', () => {
  assert.match(buildScriptPayload('LOKAL', 1, '', localScenes).error, /Bitte fülle/)
  assert.match(buildScriptPayload('LOKAL', 1, 'Titel', localScenes.slice(0, 5)).error, /Bitte fülle/)
  const incomplete = localScenes.map((scene) => ({ ...scene }))
  incomplete[2].visual_description = ' '
  assert.match(buildScriptPayload('LOKAL', 1, 'Titel', incomplete).error, /Bitte fülle/)
})
