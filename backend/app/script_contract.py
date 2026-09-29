"""Small, dependency-free contract probe for the Gemini Pro copy/paste flow."""

import argparse
import json
from pathlib import Path


IDEAS = {
    "balkon": "Ein bienenfreundlicher Stadtbalkon in fünf Schritten",
    "regen": "Ein Regentag in der Stadt",
}


def make_prompt(idea: str, mode: str) -> str:
    if mode not in ("LOKAL", "CLOUD"):
        raise ValueError("mode muss LOKAL oder CLOUD sein")
    if not idea.strip():
        raise ValueError("idea darf nicht leer sein")
    media_type = "STOCK_VIDEO" if mode == "LOKAL" else "AI_GENERATED_VIDEO"
    source_field = (
        '"pexels_queries": ["deutscher Suchbegriff", "English search phrase"]'
        if mode == "LOKAL"
        else '"wan_prompt": "Detailed English text-to-video prompt for this scene"'
    )
    return f"""Erstelle ein deutsches Skript für ein vertikales Kurzvideo.
Idee: {idea.strip()}
Produktionsmodus: {mode}

Antworte ausschließlich mit einem gültigen JSON-Objekt. Keine Markdown-Codeblöcke,
keine Einleitung und keine Kommentare. Verwende exakt diese Struktur und Schlüssel:
{{
  "title": "Deutscher Videotitel",
  "language": "de-DE",
  "mode": "{mode}",
  "target_duration_seconds": 42,
  "scenes": [
    {{
      "index": 1,
      "duration_seconds": 7,
      "narration": "Deutscher Sprechertext für genau diese Szene.",
      "visual_description": "Konkrete sichtbare Handlung und Bildkomposition.",
      "media_type": "{media_type}",
      {source_field}
    }}
  ]
}}

Regeln:
- 6 bis 10 Szenen in erzählerischer Reihenfolge; index beginnt bei 1 und steigt ohne Lücke.
- Gesamtdauer 30 bis 60 Sekunden. Jede Szene dauert ganzzahlig 3 bis 12 Sekunden.
  Die Summe aller duration_seconds ist exakt target_duration_seconds.
- title 1 bis 120 Zeichen; narration pro Szene 1 bis 400 Zeichen und auf Deutsch;
  visual_description pro Szene 1 bis 600 Zeichen, konkret und filmbar.
- Alle visuellen Szenen verwenden ausschließlich {media_type}.
- Für {mode} hat jede Szene {source_field.split(':')[0]} und keinen Schlüssel der anderen Quelle.
- Bei LOKAL: je Szene 2 bis 4 unterschiedliche Pexels-Suchbegriffe, je 1 bis 100 Zeichen.
  Bei CLOUD: je Szene ein englischer Wan-Prompt mit 1 bis 1000 Zeichen.
- Keine zusätzlichen Schlüssel. Keine Musik-, Rechte- oder Veröffentlichungsbehauptungen erfinden.
"""


def output_schema(mode: str) -> dict:
    """Constrain CLI output; validate_script remains the final authority."""
    if mode not in ("LOKAL", "CLOUD"):
        raise ValueError("mode muss LOKAL oder CLOUD sein")
    source = (
        {"pexels_queries": {"type": "array", "minItems": 2, "maxItems": 4,
                            "items": {"type": "string", "minLength": 1, "maxLength": 100}}}
        if mode == "LOKAL" else
        {"wan_prompt": {"type": "string", "minLength": 1, "maxLength": 1000}}
    )
    scene = {
        "type": "object",
        "properties": {
            "index": {"type": "integer"},
            "duration_seconds": {"type": "integer", "minimum": 3, "maximum": 12},
            "narration": {"type": "string", "minLength": 1, "maxLength": 400},
            "visual_description": {"type": "string", "minLength": 1, "maxLength": 600},
            "media_type": {"type": "string", "enum": ["STOCK_VIDEO" if mode == "LOKAL" else "AI_GENERATED_VIDEO"]},
            **source,
        },
        "required": ["index", "duration_seconds", "narration", "visual_description", "media_type", *source],
    }
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 120},
            "language": {"type": "string", "enum": ["de-DE"]},
            "mode": {"type": "string", "enum": [mode]},
            "target_duration_seconds": {"type": "integer", "minimum": 30, "maximum": 60},
            "scenes": {"type": "array", "minItems": 6, "maxItems": 10, "items": scene},
        },
        "required": ["title", "language", "mode", "target_duration_seconds", "scenes"],
    }


def _object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Doppelter JSON-Schlüssel: {key}")
        result[key] = value
    return result


def _keys(value, expected, path):
    if not isinstance(value, dict):
        raise ValueError(f"{path} muss ein Objekt sein")
    missing = expected - value.keys()
    extra = value.keys() - expected
    if missing or extra:
        raise ValueError(f"{path}: fehlende Schlüssel {sorted(missing)}, zusätzliche Schlüssel {sorted(extra)}")


def _string(value, path, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{path} muss Text mit 1 bis {maximum} Zeichen sein")


def validate_script(raw: str, mode: str) -> dict:
    if mode not in ("LOKAL", "CLOUD"):
        raise ValueError("mode muss LOKAL oder CLOUD sein")
    try:
        script = json.loads(raw, object_pairs_hook=_object_without_duplicates)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Ungültiges JSON: {exc.msg}") from exc

    _keys(script, {"title", "language", "mode", "target_duration_seconds", "scenes"}, "script")
    _string(script["title"], "title", 120)
    if script["language"] != "de-DE":
        raise ValueError("language muss de-DE sein")
    if script["mode"] != mode:
        raise ValueError(f"mode muss {mode} sein")
    target = script["target_duration_seconds"]
    if type(target) is not int or not 30 <= target <= 60:
        raise ValueError("target_duration_seconds muss 30 bis 60 sein")
    scenes = script["scenes"]
    if not isinstance(scenes, list) or not 6 <= len(scenes) <= 10:
        raise ValueError("scenes muss 6 bis 10 Szenen enthalten")

    expected_media = "STOCK_VIDEO" if mode == "LOKAL" else "AI_GENERATED_VIDEO"
    total = 0
    for index, scene in enumerate(scenes, start=1):
        path = f"scenes[{index}]"
        source_key = "pexels_queries" if mode == "LOKAL" else "wan_prompt"
        _keys(scene, {"index", "duration_seconds", "narration", "visual_description", "media_type", source_key}, path)
        if type(scene["index"]) is not int or scene["index"] != index:
            raise ValueError(f"{path}.index muss {index} sein")
        duration = scene["duration_seconds"]
        if type(duration) is not int or not 3 <= duration <= 12:
            raise ValueError(f"{path}.duration_seconds muss 3 bis 12 sein")
        total += duration
        _string(scene["narration"], f"{path}.narration", 400)
        _string(scene["visual_description"], f"{path}.visual_description", 600)
        if scene["media_type"] != expected_media:
            raise ValueError(f"{path}.media_type muss {expected_media} sein")
        if mode == "LOKAL":
            queries = scene["pexels_queries"]
            if not isinstance(queries, list) or not 2 <= len(queries) <= 4:
                raise ValueError(f"{path}.pexels_queries muss 2 bis 4 Suchbegriffe enthalten")
            for query in queries:
                _string(query, f"{path}.pexels_queries", 100)
            if len(set(queries)) != len(queries):
                raise ValueError(f"{path}.pexels_queries enthält Duplikate")
        else:
            _string(scene["wan_prompt"], f"{path}.wan_prompt", 1000)
    if total != target:
        raise ValueError(f"duration: Szenensumme {total} ist nicht target_duration_seconds {target}")
    return script


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prompt", "validate"))
    parser.add_argument("--mode", choices=("LOKAL", "CLOUD"), required=True)
    parser.add_argument("--idea", help="Videoidee für prompt")
    parser.add_argument("--file", type=Path, help="Antwortdatei für validate")
    args = parser.parse_args()
    if args.action == "prompt":
        if not args.idea:
            parser.error("--idea ist für prompt erforderlich")
        print(make_prompt(args.idea, args.mode))
    else:
        if not args.file:
            parser.error("--file ist für validate erforderlich")
        script = validate_script(args.file.read_text(encoding="utf-8"), args.mode)
        print(f"Gültig: {len(script['scenes'])} Szenen, {script['target_duration_seconds']} Sekunden, {args.mode}")


if __name__ == "__main__":
    main()
