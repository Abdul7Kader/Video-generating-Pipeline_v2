"""Generate one script through the same guarded Antigravity runtime as the worker."""

import argparse
import json
from pathlib import Path
import sys

# Share model, schema, credit guard and safe errors with the production worker.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.antigravity import generate


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
