"""Generate one script with the signed-in Antigravity CLI, without a Gemini API key."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from script_probe import make_prompt, validate_script


def generate(idea: str, mode: str, timeout_seconds: int = 180) -> dict:
    prompt = make_prompt(idea, mode)
    settings_path = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Antigravity-Credit-Einstellung kann nicht geprüft werden") from exc
        if settings.get("useG1Credits") is not False:
            raise RuntimeError("Antigravity-Credit-Überziehung ist nicht nachweislich deaktiviert")
    env = os.environ.copy()
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
        env.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="video-script-") as scratch:
        result = subprocess.run(
            [
                "agy", "-p", prompt,
                "--model", "gemini-3.1-pro-low",
                "--output-format", "json",
                "--print-timeout", f"{timeout_seconds}s",
                "--sandbox",
            ],
            cwd=scratch,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds + 30,
            check=False,
        )
    if result.returncode != 0:
        raise RuntimeError(f"Antigravity CLI fehlgeschlagen (Exit {result.returncode}): {result.stderr.strip()}")
    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Antigravity CLI lieferte kein gültiges JSON-Ergebnis") from exc
    if envelope.get("status") != "SUCCESS" or not envelope.get("response"):
        raise RuntimeError("Antigravity CLI lieferte keine Skriptantwort")
    return validate_script(envelope["response"], mode)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--idea", required=True)
    parser.add_argument("--mode", choices=("LOKAL", "CLOUD"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    script = generate(args.idea, args.mode)
    args.out.write_text(json.dumps(script, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Gültig: {len(script['scenes'])} Szenen, {script['target_duration_seconds']} Sekunden, {args.mode}")


if __name__ == "__main__":
    main()
