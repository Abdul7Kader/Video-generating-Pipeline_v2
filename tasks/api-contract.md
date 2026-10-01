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
| `GET /api/artifacts/{id}/content` | Vertragsplatzhalter für Videowiedergabe. Existierendes Artefakt liefert bis Aufgabe 18 `501 MEDIA_NOT_AVAILABLE`. | Später Dateiantwort |

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

Die Videofreigabe erwartet `{"checksum_sha256":"<64 kleine Hex-Zeichen>"}`. Eine abweichende Prüfsumme oder eine nicht finale Datei führt zu `409 ARTIFACT_CONFLICT`; ein noch nicht abgeschlossener Produktionslauf zu `409 STATE_CONFLICT`. Wiederholtes Freigeben derselben Datei liefert dieselbe Freigabe-ID. Veröffentlichungsaufträge entstehen erst in Aufgabe 26.

**Umsetzungsgrenze:** Skriptfreigabe übergibt automatisch an die wiederaufnehmbare RQ-Produktionskette. Die Stufengrenzen sind implementiert, die konkreten Medienadapter folgen in 14–18/21. Ohne sie entstehen weder Video noch gültiges Artefakt. Dateiabruf und berechtigtes Playback folgen in 18; Publikationsjobs in 26. Die Anwendung ist an Loopback gebunden; Authentifizierung und öffentlicher Remote-Betrieb bleiben offen. Antigravity-/Pro-Skripte und Editor sind auf Windows live abgenommen, weitere Zielsysteme noch nicht.

**Prüfung:** `docker compose -p step8check up -d --build --wait api worker`; `docker compose -p step8check exec -T api python -m unittest app.test_api app.test_database -v`. `app.test_api` legt ein isoliertes PostgreSQL-Schema an und entfernt es nach den HTTP-/OpenAPI-Vertragstests.

**Aktuelle Prüfung 30.09.:** 37 Backendtests mit echter PostgreSQL-/Redis-/RQ-Integration und acht Projekttests bestanden; Web-Build, Worker-Kill/Neustart ohne doppelte Testartefakte und echte Chrome-Bedienabnahme für beide Modi mit Wiederaufnahme/Abbruch erfolgreich. [Produktionsketten-Abnahme](step13-acceptance.md). Frühere echte Pro-Browserläufe und Freigabeabnahme: [Skript-/Editorabnahme](step10-acceptance.md), [Freigabeabnahme](step12-acceptance.md).

## Grafikmanifest ab Schritt 16

`GET /api/projects/{id}/production-runs/{run_id}` ergänzt `graphics`, `GET /api/projects/{id}/status` ergänzt `production_graphics`. Beide sind `null`, solange kein abgeschlossener GRAPHICS-Checkpoint vorliegt. Bei Erfolg: Breite 720, Höhe 1280, fps 24, Gesamtdauer in Frames, Titel, Titelartefaktschlüssel/-dauer, sichere Ränder, Renderer-/Vorlagenversion und geordnete Szenen mit Text, Artefaktschlüssel, Startframe, Szenen-/Untertitelframes und gemessener Audiodauer. Positions-/Text-/Zeitdaten müssen zur freigegebenen Version und SPEECH passen; keine Wort-für-Wort-Zusage.

Grafiken erscheinen in Artefaktmetadaten als `INTERMEDIATE / GRAPHICS_OVERLAY`; `content_available` bleibt bis zur Medienauslieferung in 18 false. Kein finaler Videostatus oder Videoartefakt aus dieser Stufe. Sichtbare Fehler: `GRAPHICS_SPEECH_REQUIRED`, `GRAPHICS_TIMELINE_INVALID`, `REMOTION_REQUIRED`, `GRAPHICS_RENDER_FAILED`, `GRAPHICS_OUTPUT_INVALID`, `GRAPHICS_STORAGE_FAILED`; vorhandene Schritt-/Laufzeitgrenzen bleiben unverändert. [Prüfstand](step16-acceptance.md).
