# CLOUD-Rücktransfer v1 – Schritt 21

Stand: 05.10.2026. Implementiert in `backend/app/wan_contract.py` und `backend/app/wan.py`. Der Adapter akzeptiert derzeit ausschließlich **explizit injizierte kontrollierte Testtransporte**. Kein Modal SDK, kein HTTP-Client und kein Live-Provider werden dort erstellt. Die normale CLOUD-Produktion bleibt mit `STAGE_UNAVAILABLE` sichtbar gesperrt; sie erzeugt keine Testvideos als echte Ergebnisse.

## Auftrag und Antwort

`plan_requests(context)` prüft CLOUD / `AI_GENERATED_VIDEO`, geordnete Szenen, Wan-Prompts, Szenendauer sowie Version und Dateihashes des Cloud-Bundles aus Schritt 20. Pro Szene werden `ceil(Szenendauer / (81/16))` Rohclips geplant. Sechs Sekunden benötigen zwei Clips, zwölf Sekunden drei. Jeder Clip erhält eine stabile UUID aus Lauf-ID, Szenen-ID und Clipindex; ein weiterer Versuch erzeugt keine neue Kennung. Seed wird daraus deterministisch abgeleitet.

`WanRequest`: `job_id`, `scene_position`, `clip_index`, ausschließlich `provider=WAN` / `media_type=AI_GENERATED_VIDEO`, feste Workflow-Version und ComfyUI-Commit, SHA-256 der Modell-Lockdatei, Prompt, Seed, 720 × 1280 / 81 Frames / 16 fps. Unbekannte Felder, ungültige Größen, nicht endliche Zahlen oder ungültige Seeds werden abgelehnt. Zugangsdaten gehören nicht in diesen Vertrag.

`WanResponse`: derselbe vollständige Auftrag, `execution`, relativer `result_path`, Dateigröße, SHA-256 und Rohclipdauer. Der Pfad muss exakt `wan/<job_id>/clip.mp4` sein; keine URL oder beliebiger Hostpfad. `execution=CONTROLLED_TEST` kennzeichnet synthetische Testdateien. `WAN_INFERENCE` ist für die spätere echte Herkunft vorgesehen, wird in Schritt 21 aber noch vor Übernahme abgewiesen.

## Transportgrenze

Ein Testprovider hat `execution=CONTROLLED_TEST` und implementiert:

```text
ensure_clip(request: WanRequest, *, timeout_seconds) -> WanResponse oder Dictionary
read_clip(response: WanResponse, *, timeout_seconds) -> Iterable[bytes]
```

`ensure_clip` muss dieselbe Kennung mit gleichem Payload wiederverwenden; derselbe Schlüssel mit anderem Payload ist ein Konflikt. Vor dessen Aufruf speichert der Host den vollständigen Auftrag atomar als `.request.json`. Nach einem Timeout bleibt dieser Auftrag erhalten. Der spätere echte Provider muss die Kennung vor externer Ausführung atomar in einem dauerhaften Register beanspruchen, unbekannte Ergebnisse zuerst auflösen und darf bei Retry keine neue Inferenz anlegen. Die vorhandene PostgreSQL-Sperre serialisiert Produktionsversuche derselben Stufe. **Ein stabiler Schlüssel allein ist noch keine bewiesene Idempotenz bei Modal:** Die Remote-Implementierung und Kostenprüfung folgen in 22/24.

Testtransfers bekommen höchstens 30 Sekunden pro Provideroperation. Der Provider muss auch blockierende Lese-/Antwortoperationen auf dieses Limit begrenzen; zusätzlich prüft der Host den Ablauf während der Byteübernahme. Maximal 150 MiB je Rohclip, Größenprüfung während des Schreibens, vollständige SHA-256-Prüfung und begrenzte lokale ffprobe-/Decodeprüfung. Der Produktionsprozess behält seine bestehende Stufen-/Gesamtfrist und wird bei Abbruch beendet.

## Ablage und Wiederaufnahme

Unter dem vom Betreiber gewählten `MEDIA_ROOT` beziehungsweise dem Pfad aus seiner privaten Worker-Konfiguration:

```text
projects/<project>/versions/<version>/runs/<run>/wan/
  scene-<position>/clip-<index>.request.json
  scene-<position>/clip-<index>.mp4
  scene-<position>/clip-<index>.json
  scene-<position>/scene.mp4
  manifest.json
```

Übernahme zunächst nach `.part`. Erst nach Größe, Hash, Profil und vollständigem Videodecode wird der Clip atomar aktiviert und sein Checkpoint geschrieben. Unterbrechung/beschädigte Datei erzeugt kein SCENES-Ergebnis und keinen neuen Datenbank-Artefaktcheckpunkt; `.part` wird entfernt. Bereits geprüfte Rohclips dürfen für Wiederaufnahme bestehen bleiben. Nach hartem Prozessende wird derselbe `.part`-Pfad beim nächsten Versuch neu geschrieben und erneut geprüft, niemals als fertiger Clip verwendet. Veränderte Auftragsdaten kollidieren mit dem gespeicherten Intent. Korrupter lokaler Cache wird aus demselben Providerauftrag repariert.

Mehrere geprüfte Rohclips werden auf der CPU mit FFmpeg ohne neue Videogenerierung aneinandergefügt und auf `ceil(Szenendauer × 16)` Frames geschnitten. Szenen sind H.264/MP4 mit 720 × 1280 und 16 fps; das spätere Masterprofil bleibt 24 fps. Keine Schleife/Verlangsamung einer zu kurzen Quelle. Eine vollständige Bewegungs-/Qualitätsprüfung mehrerer echter Wan-Clips bleibt 24.

SCENES liefert einen `SOURCE / AI_GENERATED_VIDEO`-Artefakteintrag pro Szene und `wan_sources` mit Szenendauer sowie geordneten Clipantworten. Die bestehende Ergebnis-JSON-Spalte speichert die Metadaten ohne Migration. Das zentrale Produktionsmodul prüft Wan-Manifeste nochmals gegen die freigegebenen Szenen; JSON-Persistierung verwendet `mode='json'` für UUIDs. STORAGE übernimmt vorhandene Wan-Metadaten später in das finale Manifest. Bestehende LOKAL-Manifeste werden dadurch nicht geändert.

## Fehler und nächste Schritte

Sichtbare Fehler: `STAGE_UNAVAILABLE`, `WAN_LIVE_DISABLED`, `MODE_MISMATCH`, `WAN_PLAN_INVALID`, `WAN_JOB_CONFLICT`, `WAN_RESPONSE_INVALID`, `WAN_CHECKSUM_MISMATCH`, `WAN_MEDIA_INVALID`, `WAN_TRANSFER_TIMEOUT`, `WAN_TIMEOUT_INVALID`. Abbruch bleibt `CANCELLED`. Kein Pexels-Fallback.

21 prüft lokale Antwort-/Datei-/Prozessgrenzen, nicht Modal-Netzwerk oder GPU. 22 ergänzt konfigurierbare Clip-/Zeit-/Parallelitäts-/Kostengrenzen **vor** teuren Aufrufen. 23 prüft den gesamten CLOUD-Browserlauf mit ausdrücklich gekennzeichneten Testdaten. 24 implementiert/prüft Remote-Ausführung erst nach nachgewiesenen Gratis-Credits und wirksamen 0 USD Nettokosten. Das behauptete Guthaben von 30 USD wurde hier weder abgefragt noch als Konto-/Kostenfreigabe verwendet.
