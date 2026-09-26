"""Probe der kostenlosen Pexels Video API mit drei vorhandenen LOKAL-Szenen.

API-Vertrag: https://www.pexels.com/api/documentation/
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tasks" / "response-balkon-agy.json"
OUTPUT = ROOT / "tasks" / "pexels-probe-output"
API = "https://api.pexels.com/v1/videos/search"
USER_AGENT = "Video-generating-Pipeline-v2/0.1"
MIN_WIDTH = 720
MIN_HEIGHT = 1280
MAX_DOWNLOAD = 150 * 1024 * 1024


def api_key():
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if key:
        return key
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == "PEXELS_API_KEY":
                key = value.strip().strip('"\'')
                if key:
                    return key
    raise RuntimeError("PEXELS_API_KEY fehlt. Kostenlosen Key lokal in .env eintragen.")


def search(key, query):
    params = urlencode({"query": query, "orientation": "portrait", "per_page": 10})
    request = Request(
        f"{API}?{params}",
        headers={"Authorization": key, "Accept": "application/json",
                 "User-Agent": USER_AGENT},
    )
    try:
        with urlopen(request, timeout=25) as response:
            data = json.load(response)
            quota = {
                name: response.headers.get(name)
                for name in ("X-Ratelimit-Limit", "X-Ratelimit-Remaining", "X-Ratelimit-Reset")
            }
    except HTTPError as exc:
        try:
            error = json.loads(exc.read(1024))
            detail = str(error.get("error") or error.get("message") or "").replace(key, "[redacted]")[:160]
        except (ValueError, AttributeError):
            detail = ""
        suffix = f": {detail}" if detail else "."
        raise RuntimeError(f"Pexels-Suche fehlgeschlagen (HTTP {exc.code}){suffix}") from exc
    except URLError as exc:
        raise RuntimeError(f"Pexels nicht erreichbar: {exc.reason}") from exc
    return data.get("videos", []), quota


def suitable_files(video, scene_seconds):
    if video.get("duration", 0) < scene_seconds:
        return []
    files = [
        item for item in video.get("video_files", [])
        if item.get("file_type") == "video/mp4"
        and (item.get("width") or 0) >= MIN_WIDTH
        and (item.get("height") or 0) >= MIN_HEIGHT
        and urlparse(item.get("link", "")).scheme == "https"
    ]
    return sorted(files, key=lambda item: (item["width"] * item["height"], item.get("fps") or 0))


def slug_match_score(video, query):
    """Conservative title hint; Pexels does not supply a video title in API JSON."""
    words = lambda text: {word.removesuffix("s") for word in re.findall(r"[a-z]+", text.lower()) if len(word) > 2}
    slug = urlparse(video.get("url", "")).path.rsplit("/", 2)[-2]
    return len(words(query) & words(slug))


def candidate(video, file, query, scene_index):
    user = video.get("user") or {}
    return {
        "scene_index": scene_index,
        "query": query,
        "video_id": video["id"],
        "video_page": video["url"],
        "videographer": user.get("name"),
        "videographer_page": user.get("url"),
        "duration_seconds": video["duration"],
        "file_id": file["id"],
        "width": file["width"],
        "height": file["height"],
        "fps": file.get("fps"),
    }


def download(url, target):
    part = target.with_suffix(".part")
    digest = hashlib.sha256()
    total = 0
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=45) as response, part.open("wb") as output:
            length = int(response.headers.get("Content-Length", 0))
            if length > MAX_DOWNLOAD:
                raise RuntimeError("Pexels-Clip überschreitet 150 MB.")
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_DOWNLOAD:
                    raise RuntimeError("Pexels-Clip überschreitet 150 MB.")
                digest.update(chunk)
                output.write(chunk)
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)
    return digest.hexdigest(), total


def probe_media(path, ffprobe):
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    media = json.loads(result.stdout)
    if not any(stream.get("codec_type") == "video" for stream in media.get("streams", [])):
        raise RuntimeError("ffprobe fand keinen Videostream.")
    return media


def main():
    key = api_key()
    ffprobe = os.environ.get("FFPROBE_PATH") or shutil.which("ffprobe")
    if not ffprobe or not Path(ffprobe).is_file():
        raise RuntimeError("ffprobe fehlt. Bitte FFmpeg/ffprobe installieren und zum PATH hinzufügen.")
    scenes = json.loads(SCRIPT.read_text(encoding="utf-8"))["scenes"][:3]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    found = []
    first_link = None
    quota = {}
    for scene in scenes:
        selected = None
        for query in scene["pexels_queries"]:
            videos, quota = search(key, query)
            options = []
            for video in videos:
                files = suitable_files(video, scene["duration_seconds"])
                if files:
                    relevance = slug_match_score(video, query)
                    if relevance:
                        options.append((relevance, video["duration"], video, files[0]))
            if options:
                _, _, video, file = max(options, key=lambda item: (item[0], -item[1]))
                selected = candidate(video, file, query, scene["index"])
                if first_link is None:
                    first_link = file["link"]
                break
        if not selected:
            raise RuntimeError(f"Keine technisch passende Pexels-Datei für Szene {scene['index']}.")
        found.append(selected)
        print(f"Szene {scene['index']}: Pexels {selected['video_id']} "
              f"({selected['width']}x{selected['height']}, {selected['duration_seconds']} s)")

    clip = OUTPUT / f"pexels-{found[0]['video_id']}-{found[0]['file_id']}.mp4"
    sha256, size = download(first_link, clip)
    media = probe_media(clip, ffprobe)
    report = {
        "source": "Pexels Video API",
        "license": "https://www.pexels.com/license/",
        "attribution": "https://www.pexels.com/api/documentation/",
        "scenes": found,
        "quota": quota,
        "download": {"path": str(clip.relative_to(ROOT)), "bytes": size,
                     "sha256": sha256, "ffprobe": media},
    }
    (OUTPUT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Clip geprüft: {clip} ({size} Bytes). Herkunft: {OUTPUT / 'report.json'}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"Pexels-Probe: {exc}", file=sys.stderr)
        sys.exit(1)
