# API-Vertrag – Aufgaben 08, 10, 11 und 12

Basis: `/api`; interaktive OpenAPI unter `/api/docs`, Schema unter `/api/openapi.json`. JSON wird mit UTF-8 übertragen. UUIDs sind Server-IDs. `LOKAL` führt ausschließlich zu `STOCK_VIDEO`, `CLOUD` ausschließlich zu `AI_GENERATED_VIDEO`.

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
| `GET /api/projects/{id}/status` | Aktuelle Skriptversion, `script_approved`, `production_run_id`, `production_state`, sichere `production_error` (Text oder `null`) und finales Artefakt lesen. Eine neue Version beginnt ohne Freigabe und Lauf. | `200` Status |
| `GET /api/artifacts/{id}` | Metadaten ohne internen Speicherpfad lesen. | `200` Artefakt |
| `GET /api/artifacts/{id}/content` | Vertragsplatzhalter für Videowiedergabe. Existierendes Artefakt liefert bis Aufgabe 18 `501 MEDIA_NOT_AVAILABLE`. | Später Dateiantwort |

Skriptfreigaben werden vor RQ-Übergabe in PostgreSQL bestätigt. Ein Projekt-Lock serialisiert die Übergabe, `job_id=production_run_id` und Prüfung eines vorhandenen Jobs verhindern doppelte Queue-Einträge bei wiederholten Requests. [RQ-Job-ID und `fetch_job`](https://python-rq.org/docs/), [Ergebnisaufbewahrung](https://python-rq.org/docs/results/). Der aktuelle Einstieg prüft die freigegebene Version und setzt fehlende Produktionsstufen sichtbar auf `FAILED`; erst Schritt 13 erweitert ihn zur Produktionskette. Wiederholte Freigabe eines bereits gestoppten Laufs startet diesen nicht neu. `production_error` enthält sichere Betriebsmeldungen ohne interne Zugangsdaten. Prozessabbruch vor Übergabe benötigt derzeit bewusste erneute Übergabe derselben Version; automatische Wiederaufnahme bleibt Schritt 13. [Abnahme und Grenzen](step12-acceptance.md).

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

**Umsetzungsgrenze:** Der Vertragsendpunkt speichert den Produktionslauf als `QUEUED`, startet aber noch keinen RQ-Produktionsjob. Das geschieht in Aufgabe 12/13. Automatische Gemini-Pro-Erzeugung und vollständiger versionierter Browsereditor sind in Aufgaben 10/11 implementiert und auf Windows live geprüft. Alte Skriptversionen bleiben beim Bearbeiten unverändert; der Editor erhält den Entwurf bei `409` und bietet bewusstes Neuladen an. Der Dateiabruf und berechtigtes Playback folgen mit persistentem konfigurierbarem Medienspeicher in Aufgabe 18. Die aktuelle Compose-Konfiguration bindet die Weboberfläche nur an Loopback; Authentifizierung und ein öffentlicher Remote-Betrieb sind noch nicht implementiert und dürfen nicht als abgeschlossen gelten.

**Prüfung:** `docker compose -p step8check up -d --build --wait api worker`; `docker compose -p step8check exec -T api python -m unittest app.test_api app.test_database -v`. `app.test_api` legt ein isoliertes PostgreSQL-Schema an und entfernt es nach den HTTP-/OpenAPI-Vertragstests.

**Aktuelle Prüfung 30.09.:** Vier API-Vertragstests mit echter PostgreSQL-Datenbank, einschließlich vollständiger LOKAL-/CLOUD-Edits, Metadatenerhalt, alter Version und Validierungs-/Versionsfehler. Insgesamt 29 Backendtests mit Redis/RQ/PostgreSQL und acht Projekttests bestanden; Web-Build, echte Pro-Browserläufe und Freigabe-Browserabnahme erfolgreich. [Skript-/Editorabnahme](step10-acceptance.md), [Freigabeabnahme](step12-acceptance.md).
