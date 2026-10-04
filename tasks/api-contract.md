# API-Vertrag – Aufgaben 08, 10–14

Basis: `/api`; interaktive OpenAPI unter `/api/docs`, Schema unter `/api/openapi.json`. JSON wird mit UTF-8 übertragen. UUIDs sind Server-IDs. `LOKAL` führt ausschließlich zu `STOCK_VIDEO`, `CLOUD` ausschließlich zu `AI_GENERATED_VIDEO`.

Ab Schritt 14 enthält `GET /projects/{id}/production-runs/{run_id}` zusätzlich `sources`; Projektstatus enthält dieselben Metadaten als `production_sources`. Standard ist `[]`. Nach abgeschlossenem LOKAL-`SCENES` gibt es pro Szene `scene_position`, `artifact_key`, `media_type: STOCK_VIDEO`, `video_id`, `file_id`, `query`, `video_page`, `creator`, `creator_page`, `license_url`, `scene_duration_seconds`, `duration_seconds`, `width`, `height`, `fps`. Keine Keys, Downloadlinks oder internen Speicherpfade. Teilweise geladene Szenen bleiben vor Abschluss privat im Worker-Medienordner. Fehlender Treffer: `PEXELS_NO_MATCH` mit Szenennummer und Änderungsbedarf. Weitere Fehler: `PEXELS_KEY_REQUIRED`, `PEXELS_AUTH_FAILED`, `PEXELS_QUOTA_EXHAUSTED`, `PEXELS_UNAVAILABLE`, `FFPROBE_REQUIRED`, `MEDIA_STORAGE_FAILED`. Eine erfolgreiche Beschaffung bedeutet noch keinen finalen Produktionsabschluss. [Abnahme](step14-acceptance.md).

| Methode und Pfad | Verhalten | Erfolg |
| --- | --- | --- |
| `POST /api/projects` | Idee und Modus speichern; Medientyp wird serverseitig abgeleitet. | `201` Projekt |
| `GET /api/projects/{id}` | Projekt lesen. | `200` Projekt |
| `POST /api/projects/{id}/script-generations` | Ersten Antigravity-Skriptauftrag in Redis/RQ anlegen; laufender Auftrag wird wiederverwendet, nach Fehler bewusst erneut aufrufen. Bei vorhandener Skriptversion `409`. | Neuer Job `202`, aktiver Job `200` |
| `GET /api/projects/{id}/script-generations/{job_id}` | `QUEUED`, `RUNNING`, `FAILED` oder `COMPLETED`, sichere Fehlermeldung und gespeicherte Skriptversion lesen. | `200` Job |
| `GET /api/projects/{id}/scripts` | Unveränderliche Skriptversionen absteigend auflisten. | `200` Liste |
| `POST /api/projects/{id}/scripts` | Neue Version mit 6–10 geordneten Szenen speichern; `expected_version` muss der aktuellen Version entsprechen (`0` für die erste). Bearbeiten bedeutet, eine weitere Version anzulegen. | `201` Skript |
| `GET /api/projects/{id}/scripts/{version}` | Version mit geordneten Szenen lesen. | `200` Skript |
| `POST /api/projects/{id}/scripts/{version}/approval` | Nur aktuelle vollständige Version freigeben, genau einen `QUEUED`-Produktionslauf speichern und nach Commit an RQ übergeben. Wiederholung liefert denselben Lauf; ältere Version `409`. Brokerfehler `503`, Freigabe bleibt gespeichert und dieselbe Version kann erneut übergeben werden. | Erstes Mal `201`, danach `200` |
| `POST /api/projects/{id}/videos/{artifact_id}/approval` | Finale Datei mit passender SHA-256-Prüfsumme nach abgeschlossenem Produktionslauf freigeben; Wiederholung liefert dieselbe Freigabe. | Erstes Mal `201`, danach `200` |
| `GET /api/projects/{id}/status` | Aktuelle Version/Freigabe, Lauf und finales Artefakt sowie `production_steps`, sichere `production_error`/`production_error_code`, `production_can_resume` und `production_cancel_requested` lesen. Jede Stufe zeigt Name, Status, Versuche, Grenze und Fehler. Neue Version beginnt ohne Freigabe/Lauf. | `200` Status |
| `GET /api/projects/{id}/production-runs/{run_id}` | Lauf mit fünf geordneten Schritten, Versuchen, Fehlercode/-meldung, Zeitgrenzen und `can_resume` lesen; interne Ergebnis-/Speicherpfade werden nicht ausgegeben. | `200` Lauf |
| `POST /api/projects/{id}/production-runs/{run_id}/resume` | Fehlgeschlagenen aktuellen Lauf innerhalb verbleibender Versuche und Laufzeit wiederaufnehmen; abgeschlossene Schritte bleiben erhalten. Lauf-ID bleibt gleich, parallele Aufrufe erzeugen keine zweite fachliche Ausführung. Abbruch/überholte Version/verbrauchtes Budget `409`. Redisfehler `503`, Wiederaufnahme bleibt gespeichert. | `200` Lauf |
| `POST /api/projects/{id}/production-runs/{run_id}/cancel` | Aktiven Lauf abbrechen; laufender Medienprozess wird beendet. Wiederholung eines bereits angeforderten Abbruchs liefert denselben Zustand. Abgeschlossener Lauf `409`. | `200` Lauf |
| `GET /api/artifacts/{id}` | Metadaten ohne internen Speicherpfad lesen. | `200` Artefakt |
| `GET/HEAD /api/artifacts/{id}/content` | Passwortgeschütztes FINAL-MP4-Streaming mit Prüfsumme und Einzelbereich; nur abgeschlossene Speicherung. | 200/206 video/mp4 |

Skriptfreigaben und Wiederaufnahme werden vor RQ-Übergabe in PostgreSQL bestätigt. Eine Projekt-Sperre serialisiert die Übergabe; die anfängliche RQ-ID entspricht der Lauf-ID, Wiederzustellung erhält eine fortlaufende Nummer. Der angemeldete Hostworker stellt gespeicherte `QUEUED`-Läufe beim Start und im Leerlauf automatisch zu und setzt unterbrochene Versuche innerhalb fester Grenzen fort. Sitzungssperren schützen aktive Lauf-/Medienprozesse vor paralleler Ausführung. Erfolgreiche Schritte werden übersprungen, Ergebnisse atomar mit eindeutigen Artefaktschlüsseln bestätigt. [Abnahme Schritt 13](step13-acceptance.md), [RQ-Joboptionen](https://python-rq.org/docs/). Wiederholte Skriptfreigabe startet einen endgültig fehlgeschlagenen Lauf nicht neu; dafür dient bewusst `resume`. Fehlende Medienadapter bleiben als `STAGE_UNAVAILABLE` sichtbar und lösen keine automatische Wiederholung aus.

Beispiel für `POST /api/projects`:

```json
{"idea":"Ein bienenfreundlicher Stadtbalkon","mode":"LOKAL"}
```

Beispiel für `POST /api/projects/{id}/scripts`:

```json
{
  "expected_version": 0,
  "title": "Bienenfreundlicher Balkon",
  "language": "de-DE",
  "target_duration_seconds": 36,
  "narration": "Szene 1 zeigt unseren Balkon. Szene 2 zeigt unseren Balkon. Szene 3 zeigt unseren Balkon. Szene 4 zeigt unseren Balkon. Szene 5 zeigt unseren Balkon. Szene 6 zeigt unseren Balkon.",
  "scenes": [
    {
      "narration": "Szene 1 zeigt unseren Balkon.",
      "visual_description": "Blühender Balkon, Einstellung 1.",
      "duration_seconds": 6,
      "pexels_queries": [
        "balcony flowers scene 1",
        "urban garden scene 1"
      ]
    },
    {
      "narration": "Szene 2 zeigt unseren Balkon.",
      "visual_description": "Blühender Balkon, Einstellung 2.",
      "duration_seconds": 6,
      "pexels_queries": [
        "balcony flowers scene 2",
        "urban garden scene 2"
      ]
    },
    {
      "narration": "Szene 3 zeigt unseren Balkon.",
      "visual_description": "Blühender Balkon, Einstellung 3.",
      "duration_seconds": 6,
      "pexels_queries": [
        "balcony flowers scene 3",
        "urban garden scene 3"
      ]
    },
    {
      "narration": "Szene 4 zeigt unseren Balkon.",
      "visual_description": "Blühender Balkon, Einstellung 4.",
      "duration_seconds": 6,
      "pexels_queries": [
        "balcony flowers scene 4",
        "urban garden scene 4"
      ]
    },
    {
      "narration": "Szene 5 zeigt unseren Balkon.",
      "visual_description": "Blühender Balkon, Einstellung 5.",
      "duration_seconds": 6,
      "pexels_queries": [
        "balcony flowers scene 5",
        "urban garden scene 5"
      ]
    },
    {
      "narration": "Szene 6 zeigt unseren Balkon.",
      "visual_description": "Blühender Balkon, Einstellung 6.",
      "duration_seconds": 6,
      "pexels_queries": [
        "balcony flowers scene 6",
        "urban garden scene 6"
      ]
    }
  ]
}
```

Bei `CLOUD` steht in jeder Szene `wan_prompt` anstelle von `pexels_queries`. Vollständige Skripte enthalten `language=de-DE`, Gesamtdauer 30–60 Sekunden und Szenendauer 3–12 Sekunden; die Summe muss passen. Der gesamte Sprechertext entspricht den geordneten Szenentexten. LOKAL braucht 2–4 unterschiedliche Suchbegriffe pro Szene; gemischte Quellen bleiben gesperrt. Fehler im vollständigen Skript ergeben `422 INVALID_SCRIPT`. Ein bereits vollständig erzeugtes Skript darf beim Bearbeiten keine Metadaten verlieren. Für alte Aufgabe-08-Clients bleibt die Erstversion mit einem einzelnen `pexels_query` ohne Dauer kompatibel; der aktuelle Editor sendet stets den vollständigen Vertrag. Die API weist gemischte oder fehlende modusspezifische Angaben mit `422 MODE_MISMATCH` ab. Leere Texte, falsche Moduswerte, zusätzliche Felder und Szenenzahlen außerhalb von 6–10 ergeben `422 VALIDATION_ERROR`.

Fehler haben die Form `{"error":{"code":"VERSION_CONFLICT","message":"..."}}`. `404` bedeutet unbekanntes Projekt/Skript/Artefakt. `409 VERSION_CONFLICT` bedeutet überholte `expected_version` oder Freigabe einer alten Version. Datenbank-Konflikte geben `409 CONFLICT` beziehungsweise `409 STATE_CONFLICT` zurück. Wiederholte aktuelle Skriptfreigaben sind idempotent und behalten Freigabe- und Produktionslauf-ID.

Die Videofreigabe erwartet `{"checksum_sha256":"<64 kleine Hex-Zeichen>","reviewed_narration":true,"reviewed_visuals":true}`. Beide Prüfpunkte müssen wahr sein (`422` andernfalls). Eine gültige Medien-Sitzung und gleiches `Origin` sind erforderlich (`401`/`403`). Eine abweichende Prüfsumme oder eine nicht finale Datei führt zu `409 ARTIFACT_CONFLICT`; ein noch nicht abgeschlossener Produktionslauf zu `409 STATE_CONFLICT`. Die API sperrt das Projekt während der Freigabe, verlangt die aktuelle Skriptversion (`409 VIDEO_VERSION_OUTDATED`), prüft doppelte Quell-IDs/Dateihashes (`409 VIDEO_DUPLICATE_CLIPS`) und öffnet die wirkliche FINAL-Datei über den Worker mit Manifest-/SHA-Prüfung (`409 MEDIA_CORRUPT`; fehlender Worker `503`). Wiederholtes Freigeben derselben aktuellen unveränderten Datei liefert dieselbe Freigabe-ID. Veröffentlichungsaufträge entstehen erst in Aufgabe 26.

**Umsetzungsgrenze:** Skriptfreigabe übergibt automatisch an die wiederaufnehmbare RQ-Produktionskette. Die Stufengrenzen sind implementiert, die konkreten Medienadapter folgen in 14–18/21. Schritte 14–17 sind inzwischen geprüft: eine echte MP4 entsteht als ENCODING-Zwischenartefakt; STORAGE/FINAL-Ablage sowie berechtigtes Playback sind inzwischen in 18 implementiert; Publikationsjobs in 26. Die Anwendung ist an Loopback gebunden; Medien und Speicheränderungen sind passwortgeschützt; allgemeine Benutzerrollen und öffentlicher Remote-Betrieb bleiben offen. Antigravity-/Pro-Skripte und Editor sind auf Windows live abgenommen, weitere Zielsysteme noch nicht.

**Prüfung:** `docker compose -p step8check up -d --build --wait api worker`; `docker compose -p step8check exec -T api python -m unittest app.test_api app.test_database -v`. `app.test_api` legt ein isoliertes PostgreSQL-Schema an und entfernt es nach den HTTP-/OpenAPI-Vertragstests.

**Historische Prüfung 30.09.:** 37 Backendtests mit echter PostgreSQL-/Redis-/RQ-Integration und acht Projekttests bestanden; Web-Build, Worker-Kill/Neustart ohne doppelte Testartefakte und echte Chrome-Bedienabnahme für beide Modi mit Wiederaufnahme/Abbruch erfolgreich. [Produktionsketten-Abnahme](step13-acceptance.md). Frühere echte Pro-Browserläufe und Freigabeabnahme: [Skript-/Editorabnahme](step10-acceptance.md), [Freigabeabnahme](step12-acceptance.md).

## Grafikmanifest ab Schritt 16

**Produktentscheidung 04.10.2026:** Der bestehende Titelartefakt-/Zeitvertrag bleibt als interne Grafikmetadaten kompatibel. Er bedeutet keine Einblendung im Endvideo: neue Encodes verwenden ausschließlich die Untertitelgrafiken, ohne Szenenzähler oder Fortschrittsstreifen. Projektname/Titel bleiben im Editor sichtbar. Bereits abgeschlossene Videos und ihre Prüfsummen werden nicht nachträglich verändert; eine neue Gestaltung wird in einer neuen Version geprüft.

`template_version` akzeptiert historische `v1` und neue `v2`, neue Grafiken verwenden `v2`. Ein neuer Encode mit `v1`-Grafiken wird mit `GRAPHICS_STYLE_OUTDATED` blockiert und verlangt eine neue Skriptversion/Freigabe, damit alte Szenenzähler nicht wieder erscheinen. Vorhandene abgeschlossene Checkpoints bleiben lesbar und unverändert.

`GET /api/projects/{id}/production-runs/{run_id}` ergänzt `graphics`, `GET /api/projects/{id}/status` ergänzt `production_graphics`. Beide sind `null`, solange kein abgeschlossener GRAPHICS-Checkpoint vorliegt. Bei Erfolg: Breite 720, Höhe 1280, fps 24, Gesamtdauer in Frames, Titel, Titelartefaktschlüssel/-dauer, sichere Ränder, Renderer-/Vorlagenversion und geordnete Szenen mit Text, Artefaktschlüssel, Startframe, Szenen-/Untertitelframes und gemessener Audiodauer. Positions-/Text-/Zeitdaten müssen zur freigegebenen Version und SPEECH passen; keine Wort-für-Wort-Zusage.

Grafiken erscheinen in Artefaktmetadaten als `INTERMEDIATE / GRAPHICS_OVERLAY`; `content_available` bleibt für solche Zwischenartefakte false. Kein finaler Videostatus oder Videoartefakt aus dieser Stufe. Sichtbare Fehler: `GRAPHICS_SPEECH_REQUIRED`, `GRAPHICS_TIMELINE_INVALID`, `REMOTION_REQUIRED`, `GRAPHICS_RENDER_FAILED`, `GRAPHICS_OUTPUT_INVALID`, `GRAPHICS_STORAGE_FAILED`; vorhandene Schritt-/Laufzeitgrenzen bleiben unverändert. [Prüfstand](step16-acceptance.md).


## Encodingmanifest ab Schritt 17

`GET /api/projects/{id}/production-runs/{run_id}` ergänzt `encoding`, der Projektstatus `production_encoding`. Beide sind `null`, solange ENCODING nicht abgeschlossen ist. Bei Erfolg enthält das Manifest `width=720`, `height=1280`, `fps=24`, `duration_frames`, `duration_seconds`, `video_codec=h264`, `audio_codec=aac`, `sample_rate=48000`, `channels=1`, `size_bytes` und `artifact_key=encoded_master`. Es enthält keine privaten Dateipfade. Dauer und Bildzahl müssen dem geprüften GRAPHICS-/SPEECH-Plan entsprechen.

Die geprüfte MP4 ist zunächst `INTERMEDIATE / FINAL_VIDEO`, mit SHA-256 und ENCODING-Checkpoint. STORAGE aus Schritt 18 veröffentlicht anschließend ein eigenes FINAL-Artefakt; nur dieses erhält `content_available=true`. Das ENCODING-Zwischenartefakt bleibt nicht abrufbar. Ein abgeschlossener Schnitt ist kein abgeschlossener Produktionslauf, solange STORAGE fehlt. Die UI zeigt Dauer, Auflösung, Bildrate, Codecs und Dateigröße als passive Anzeige.

Fehler: `MODE_MISMATCH`, `ENCODING_INPUT_INVALID`, `ENCODING_SOURCE_INVALID`, `FFMPEG_REQUIRED`, `ENCODING_FAILED`, `ENCODING_OUTPUT_INVALID`. Fehlende/defekte Dateien, falsche Prüfsummen, veränderte Zeitdaten oder zu kurze Quellen blockieren den Schnitt. Keine Wiederholung/Verlangsamung oder künstliche Verlängerung einer zu kurzen Quelle. Mehrere Szenencheckpoints und ein Mastercache ermöglichen Wiederaufnahme; allgemeine Versuchs-, Abbruch- und Zeitgrenzen bleiben wirksam.

## Speicher und berechtigter Abruf ab Schritt 18

`GET /api/media-session` liefert ausschließlich `configured` und `authorized`. `POST` mit `{ "password": "<lokale Eingabe>" }` richtet den Zugang einmalig ein oder entsperrt ihn; 10–200 Zeichen, gesalzenes scrypt, globale Begrenzung auf zehn Versuche in fünf Minuten. Erfolg setzt eine vier Stunden gültige HttpOnly-/SameSite=Strict-Sitzung mit Pfad `/api` (unter HTTPS zusätzlich Secure). `DELETE` löscht die Browsersitzung. Schreibaufrufe benötigen einen passenden Origin-Header. Keine Passwort-/Tokenwerte in Antworten oder Artefakt-URLs.

`GET /api/storage` benötigt diese Sitzung und liefert den aktiven Hostpfad sowie den letzten Übernahmeauftrag. `POST /api/storage/changes` erhält `path` und `expected_path`, antwortet nach dauerhaftem Datenbank-Commit mit `202` und Auftrag. RQ-Zustellung kann nach Redis-Ausfall automatisch nachgeholt werden. `GET /api/storage/changes/{id}` liefert QUEUED/RUNNING/COMPLETED/FAILED, Bytezähler, Versuche und sichere Fehlermeldung. Eine Übernahme gleichzeitig; bestehende Produktion oder veränderter Ausgangspfad liefert `409`. Absolute plattformspezifische Pfade prüft der native Worker, der bisherige Speicher bleibt bis erfolgreicher Aktivierung gültig.

`GET`/`HEAD /api/artifacts/{id}/content` benötigen die Sitzung. Nur FINAL/FINAL_VIDEO aus COMPLETED-Lauf und COMPLETED-STORAGE sind abspielbar. Manifesthash und MP4-SHA-256 werden vor Abruf geprüft; sichere relative Pfade bleiben unter dem aktiven Medienroot. Erfolg: `video/mp4`, Content-Length, ETag=SHA-256, Accept-Ranges=bytes, private/no-store. Ein einzelner Bytebereich liefert `206`; ungültige/mehrfache Bereiche `416` mit Gesamtgröße. Abweichendes If-Range liefert das ganze Video. `401` verlangt Entsperren, `404` bedeutet fehlendes/nicht fertiges Video, `409` beschädigte Medien, `503` nicht erreichbaren Medienworker. `content_available` in Metadaten bezeichnet den veröffentlichten Checkpoint; eine tatsächliche Dateiprüfung erfolgt beim Abruf.

STORAGE bleibt innerhalb der vorhandenen 120-Sekunden-Stufengrenze und unverlängerten Drei-Stunden-Gesamtfrist. Der neue Manifestvertrag bindet Projekt, Version, Lauf, Eingangsprüfsummen, Quellen, Sprach-/Grafik-/Encodingprofile und FINAL-Datei; keine Zugangsdaten oder absoluten Hostpfade im Manifest. Eine Produktion oder ein verwaister Medienprozess hält eine gemeinsame Datenbanksperre; Übernahme erhält die exklusive Sperre. Dadurch wird während einer Medienerzeugung kein Speicher aktiviert.

## Videoprüfung ab Schritt 19

Der Status enthält `video_approved` für das FINAL der aktuellen Version. React zeigt Eingabe, Sprechertext/Bildvorgaben und Szenensprünge aus den tatsächlichen Grafik-Startframes. Änderungen speichern eine neue Version mit eigener Produktion/Freigabe. Pexels-Auswahl schließt gleiche Video-IDs und Datei-SHA-256 aus, einschließlich bereits gespeicherter Szenen. Ohne anderen geeigneten Treffer: `PEXELS_DUPLICATE_ONLY` mit Änderungsbedarf; keine fertige Wiederholungsfolge und kein Quellenwechsel. Kein automatisches semantisches Bildverständnis; Inhaltsprüfung erfolgt am Video. [Prüfbericht](step19-acceptance.md).

## Wan-Metadaten ab Schritt 21

`GET /api/projects/{id}/production-runs/{run_id}` ergänzt `wan_sources`, der Projektstatus `production_wan_sources`. Beide sind standardmäßig leer und werden nur aus einem abgeschlossenen SCENES-Checkpoint gelesen. Geordnete Einträge enthalten Szenenposition, Artefaktschlüssel, ausschließlich `AI_GENERATED_VIDEO`, geplante/gemessene Dauer und die geprüften Clipantworten: vollständiger Wan-Auftrag, stabile UUID, Seed/Prompt, Workflow-/ComfyUI-/Modell-Lockbezug, Herkunftskennzeichnung, relativer Ergebnispfad, SHA-256 und Bytes. Keine absoluten Hostpfade, URLs oder Zugangsdaten.

`sources`/`production_sources` bleiben die bestehenden Pexels-Felder; Wan wird additiv ergänzt. Keine Migration erforderlich. Aktuelle Tests verwenden ausdrücklich `execution=CONTROLLED_TEST`, keine reale Wan-Inferenz. Die normale CLOUD-Produktion meldet weiterhin `STAGE_UNAVAILABLE` und benutzt keinen Testprovider. Echte Aktivierung folgt erst nach Grenzen/Kostennachweisen; kompletter CLOUD-Browserlauf mit Testdaten bleibt 23. [Transportvertrag](cloud-transfer-contract.md), [Prüfstand 21](step21-acceptance.md).
