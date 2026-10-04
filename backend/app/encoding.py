"""CPU-only FFmpeg composition of approved sources, audio and Remotion overlays."""

from app.graphics import build_plan
from app.production_stages import StageFailure, StageResult


def encoding_plan(context):
    expected_type = {'LOKAL': 'STOCK_VIDEO', 'CLOUD': 'AI_GENERATED_VIDEO'}.get(context.get('mode'))
    if not expected_type or context.get('media_type') != expected_type:
        raise StageFailure('MODE_MISMATCH', 'Der Quellenvertrag passt nicht zum freigegebenen Videomodus.')
    try:
        previous = context['previous_results']
        source = StageResult.model_validate(previous['SCENES'])
        speech = StageResult.model_validate(previous['SPEECH'])
        graphics = StageResult.model_validate(previous['GRAPHICS'])
        plan = build_plan(context)
        if graphics.graphics != plan:
            raise ValueError('changed graphics timeline')
        groups = (
            (source.artifacts, {f'scene_{s.scene_position}' for s in plan.scenes}, 'SOURCE', expected_type),
            (speech.artifacts, {f'speech_{s.scene_position}' for s in plan.scenes}, 'INTERMEDIATE', 'SPEECH_AUDIO'),
            (graphics.artifacts, {plan.title_artifact_key, *(s.artifact_key for s in plan.scenes)}, 'INTERMEDIATE', 'GRAPHICS_OVERLAY'),
        )
        if any(a.media_type != expected_type for a in source.artifacts):
            raise StageFailure('MODE_MISMATCH', 'Gemischte Szenenquellen wurden abgewiesen. Kein Quellenwechsel beim Videoschnitt.')
        if {s.artifact_key for s in speech.speech} != groups[1][1]:
            raise ValueError('speech key mismatch')
        inputs = {}
        for artifacts, keys, kind, media in groups:
            if (len(artifacts) != len(keys) or {a.key for a in artifacts} != keys
                    or any(a.kind != kind or a.media_type != media for a in artifacts)):
                raise ValueError('incomplete input artifacts')
            inputs.update({a.key: a for a in artifacts})
        return plan, inputs
    except (KeyError, ValueError, TypeError) as exc:
        raise StageFailure('ENCODING_INPUT_INVALID', 'Clips, Sprache oder Grafikzeitdaten fehlen oder passen nicht zur Freigabe. Videoschnitt wurde blockiert.') from exc
