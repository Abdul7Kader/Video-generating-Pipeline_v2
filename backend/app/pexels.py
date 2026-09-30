"""Bounded Pexels stock sourcing with verified, resumable scene files.

API contract: https://www.pexels.com/api/documentation/
Only the API receives Authorization; downloads are restricted to Pexels' CDN.
"""

from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.parse import urlparse
from uuid import UUID

import httpx

from app.production_stages import PexelsSource, StageArtifact, StageFailure, StageResult

ROOT = Path(__file__).resolve().parents[2]
API = "https://api.pexels.com/v1/videos/search"
MAX_DOWNLOAD = 150 * 1024 * 1024
CACHE_SECONDS = 86400


def api_key():
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        # Compose's private .env is also usable by the native host worker.
        try:
            for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
                name, sep, value = line.partition("=")
                if sep and name.strip() == "PEXELS_API_KEY":
                    key = value.strip().strip("\"'")
        except FileNotFoundError:
            pass
    if not key:
        raise StageFailure("PEXELS_KEY_REQUIRED", "Pexels-Key fehlt. Kostenlosen Key privat für den Host-Worker einrichten und erneut starten.")
    return key


def media_root():
    root = Path(os.environ.get("MEDIA_ROOT") or ROOT / ".data" / "media").expanduser()
    if not root.is_absolute():
        raise StageFailure("MEDIA_ROOT_INVALID", "MEDIA_ROOT muss ein absoluter Ordnerpfad sein.")
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def ffprobe_path():
    executable = os.environ.get("FFPROBE_PATH") or shutil.which("ffprobe")
    if not executable or not Path(executable).is_file():
        raise StageFailure("FFPROBE_REQUIRED", "ffprobe fehlt. FFmpeg installieren und ffprobe im Worker-PATH oder als FFPROBE_PATH einrichten.")
    return executable


def write_json(path, value):
    part = path.with_suffix(".json.part")
    try:
        part.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        part.replace(path)
    finally:
        part.unlink(missing_ok=True)


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def safe_download_url(value):
    url = urlparse(value)
    return (url.scheme == "https" and url.hostname == "videos.pexels.com"
            and url.port in (None, 443) and not url.username and not url.password)


def http_failure(status):
    if status in (401, 403):
        return StageFailure("PEXELS_AUTH_FAILED", "Pexels-Key wurde abgewiesen. Private Worker-Konfiguration prüfen.")
    if status == 429:
        return StageFailure("PEXELS_QUOTA_EXHAUSTED", "Pexels-Limit erreicht. Nach Freigabe des Kontingents erneut starten; es wird keine andere Quelle verwendet.")
    return StageFailure("PEXELS_UNAVAILABLE", "Pexels ist vorübergehend nicht erreichbar.", status >= 500)


def search(client, key, query, root):
    cache = root / "pexels-search"
    cache.mkdir(exist_ok=True)
    path = cache / (hashlib.sha256(query.casefold().strip().encode()).hexdigest() + ".json")
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        age = time.time() - saved["saved_at"]
        if 0 <= age < CACHE_SECONDS and isinstance(saved["videos"], list):
            return saved["videos"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    # Never follow API redirects with an authentication header.
    with client.stream("GET", API, params={"query": query, "orientation": "portrait", "per_page": 10},
                       headers={"Authorization": key}, timeout=25) as response:
        if response.status_code != 200:
            raise http_failure(response.status_code)
        payload = bytearray()
        for chunk in response.iter_bytes():
            payload.extend(chunk)
            if len(payload) > 2 * 1024 * 1024:
                raise StageFailure("PEXELS_RESPONSE_INVALID", "Pexels lieferte eine ungültige Suchantwort.")
        data = json.loads(payload)
        videos = data.get("videos")
        if not isinstance(videos, list) or len(videos) > 10:
            raise StageFailure("PEXELS_RESPONSE_INVALID", "Pexels lieferte eine ungültige Suchantwort.")
    write_json(path, {"saved_at": time.time(), "videos": videos})
    return videos


def relevance(video, query):
    stop = {"the", "and", "with", "for", "from", "auf", "und", "mit", "der", "die", "das"}
    def words(text):
        return {word.removesuffix("s") for word in re.findall(r"[a-z]+", text.lower())
                if len(word) > 2 and word not in stop}
    wanted = words(query)
    slug = words(urlparse(video.get("url", "")).path)
    return len(wanted & slug) / max(1, len(wanted))


def candidates(videos, query, duration):
    options = []
    for video in videos:
        if not isinstance(video, dict):
            continue
        try:
            score = relevance(video, query)
            if score < .5 or float(video.get("duration") or 0) < duration:
                continue
            files = [f for f in video["video_files"] if f.get("file_type") == "video/mp4"
                     and (f.get("width") or 0) >= 720 and (f.get("height") or 0) >= 1280
                     and f["height"] >= f["width"] and safe_download_url(f.get("link", ""))]
            if files:
                file = min(files, key=lambda f: f["width"] * f["height"])
                options.append((score, float(video["duration"]), video, file))
        except (ValueError, TypeError, KeyError):
            continue
    options.sort(key=lambda item: (-item[0], item[1]))
    return [(video, file) for _, _, video, file in options[:2]]


def download(client, url, part):
    if not safe_download_url(url):
        raise StageFailure("PEXELS_MEDIA_INVALID", "Pexels lieferte eine unzulässige Clipadresse.")
    # Separate request headers: never send the API key to media hosts.
    with client.stream("GET", url, timeout=45) as response:
        if response.status_code != 200:
            if 300 <= response.status_code < 500 and response.status_code != 429:
                raise StageFailure("PEXELS_MEDIA_INVALID", "Pexels-Clip ist unter dieser Adresse nicht verfügbar.")
            raise http_failure(response.status_code)
        if int(response.headers.get("content-length") or 0) > MAX_DOWNLOAD:
            raise StageFailure("PEXELS_MEDIA_INVALID", "Pexels-Clip überschreitet die Dateigrenze von 150 MB.")
        size = 0
        with part.open("wb") as stream:
            for chunk in response.iter_bytes(1024 * 1024):
                size += len(chunk)
                if size > MAX_DOWNLOAD:
                    raise StageFailure("PEXELS_MEDIA_INVALID", "Pexels-Clip überschreitet die Dateigrenze von 150 MB.")
                stream.write(chunk)


def probe(path, duration, executable):
    try:
        output = subprocess.run([executable, "-v", "error", "-show_entries",
                                 "format=duration,format_name:stream=codec_type,width,height,avg_frame_rate,duration",
                                 "-of", "json", str(path)], capture_output=True, text=True, timeout=30, check=True)
        data = json.loads(output.stdout)
        stream = next(s for s in data["streams"] if s["codec_type"] == "video")
        seconds = float(stream.get("duration") or data["format"]["duration"])
        width, height = int(stream["width"]), int(stream["height"])
        fps = float(Fraction(stream["avg_frame_rate"]))
        if ("mp4" not in data["format"]["format_name"] or seconds < duration or width < 720
                or height < 1280 or height < width or not 0 < fps <= 240):
            raise ValueError("unsuitable media")
        return {"duration_seconds": seconds, "width": width, "height": height, "fps": fps}
    except (subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError, StopIteration, ZeroDivisionError) as exc:
        raise StageFailure("PEXELS_MEDIA_INVALID", "Pexels-Clip ist beschädigt, zu kurz oder erfüllt das Hochformat nicht.") from exc


def collect_scenes(context, client=None):
    if context["mode"] != "LOKAL" or context["media_type"] != "STOCK_VIDEO" or any(s["media_type"] != "STOCK_VIDEO" for s in context["scenes"]):
        raise StageFailure("MODE_MISMATCH", "Pexels darf ausschließlich STOCK_VIDEO-Szenen im Modus LOKAL beschaffen.")
    key, executable, root = api_key(), ffprobe_path(), media_root()
    directory = root / "sources" / str(UUID(context["run_id"]))
    directory.mkdir(parents=True, exist_ok=True)
    own_client = client is None
    client = client or httpx.Client(follow_redirects=False, trust_env=False, headers={"User-Agent": "VideoPipeline/0.1"})
    artifacts, sources = [], []
    try:
        for scene in context["scenes"]:
            position = scene["position"]
            duration = scene.get("duration_seconds")
            queries = scene.get("pexels_queries") or [scene.get("pexels_query")]
            if not isinstance(position, int) or not 1 <= position <= 20 or not duration or not all(isinstance(q, str) and q.strip() for q in queries) or not 1 <= len(queries) <= 4:
                raise StageFailure("SCENE_SEARCH_REQUIRED", f"Szene {position}: Dauer und Pexels-Suchbegriffe im Skript ergänzen und neu freigeben.")
            fingerprint = hashlib.sha256(json.dumps({"scene": str(scene["id"]), "duration": duration, "queries": queries}, sort_keys=True).encode()).hexdigest()
            clip = directory / f"scene-{position}.mp4"
            checkpoint = directory / f"scene-{position}.json"
            try:
                saved = json.loads(checkpoint.read_text(encoding="utf-8"))
                artifact = StageArtifact.model_validate(saved["artifact"])
                source = PexelsSource.model_validate(saved["source"])
                if (saved["fingerprint"] != fingerprint or artifact.storage_path != clip.relative_to(root).as_posix()
                        or artifact.key != f"scene_{position}" or artifact.kind != "SOURCE" or artifact.media_type != "STOCK_VIDEO"
                        or source.artifact_key != artifact.key or source.scene_position != position
                        or source.scene_duration_seconds != duration or checksum(clip) != artifact.checksum_sha256):
                    raise ValueError("checkpoint mismatch")
                probe(clip, duration, executable)
            except (OSError, ValueError, KeyError, TypeError, StageFailure):
                selected = None
                for query in queries:
                    for video, file in candidates(search(client, key, query, root), query, duration):
                        part = clip.with_suffix(".mp4.part")
                        try:
                            download(client, file["link"], part)
                            media = probe(part, duration, executable)
                            source = PexelsSource(scene_position=position, artifact_key=f"scene_{position}",
                                                  video_id=video["id"], file_id=file["id"], query=query,
                                                  video_page=video["url"], creator=video["user"]["name"],
                                                  creator_page=video["user"]["url"], scene_duration_seconds=duration, **media)
                            artifact = StageArtifact(key=source.artifact_key, kind="SOURCE", media_type="STOCK_VIDEO",
                                                     storage_path=clip.relative_to(root).as_posix(), checksum_sha256=checksum(part))
                            part.replace(clip)
                            write_json(checkpoint, {"fingerprint": fingerprint, "artifact": artifact.model_dump(), "source": source.model_dump()})
                            selected = source
                            break
                        except StageFailure as exc:
                            if exc.code != "PEXELS_MEDIA_INVALID":
                                raise
                        except (ValueError, KeyError, TypeError):
                            pass  # Unusable provider metadata; try the next bounded candidate.
                        finally:
                            part.unlink(missing_ok=True)
                    if selected:
                        break
                if not selected:
                    raise StageFailure("PEXELS_NO_MATCH", f"Szene {position}: Kein geeigneter Pexels-Clip gefunden. Suchbegriffe oder Bildbeschreibung im Skript ändern und neu freigeben.")
            artifacts.append(artifact)
            sources.append(source)
        result = StageResult(artifacts=artifacts, sources=sources)
        write_json(directory / "manifest.json", result.model_dump())
        return result.model_dump()
    except httpx.HTTPError as exc:
        raise StageFailure("PEXELS_UNAVAILABLE", "Pexels-Verbindung unterbrochen. Bereits geprüfte Szenen bleiben gespeichert.", True) from exc
    except OSError as exc:
        raise StageFailure("MEDIA_STORAGE_FAILED", "Clip konnte nicht gespeichert werden. Medienordner und freien Speicher prüfen.") from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise StageFailure("PEXELS_RESPONSE_INVALID", "Pexels lieferte ungültige Metadaten.") from exc
    finally:
        if own_client:
            client.close()
