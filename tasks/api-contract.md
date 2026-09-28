# API-Vertrag – Aufgabe 08

Basis: `/api`; interaktive OpenAPI unter `/api/docs`, Schema unter `/api/openapi.json`. JSON wird mit UTF-8 übertragen. UUIDs sind Server-IDs. `LOKAL` führt ausschließlich zu `STOCK_VIDEO`, `CLOUD` ausschließlich zu `AI_GENERATED_VIDEO`.

| Methode und Pfad | Verhalten | Erfolg |
| --- | --- | --- |
| `POST /api/projects` | Idee und Modus speichern; Medientyp wird serverseitig abgeleitet. | `201` Projekt |
| `GET /api/projects/{id}` | Projekt lesen. | `200` Projekt |
| `POST /api/projects/{id}/script-generation` | Einen RQ-Auftrag für die automatische Antigravity-Erzeugung starten; ein bereits aktiver Auftrag wird idempotent zurückgegeben. Nach einem Fehler startet nur ein neuer bewusster Aufruf einen weiteren Versuch. | Neu `202`, aktiv `200` |
| `GET /api/projects/{id}/script-generation` | Letzten Erzeugungsstatus samt verständlichem Fehler oder gespeicherter Skriptversion lesen. | `200` Auftrag |
| `GET /api/projects/{id}/scripts` | Unveränderliche Skriptversionen absteigend auflisten. | `200` Liste |
| `POST /api/projects/{id}/scripts` | Neue Version mit 6–10 geordneten Szenen speichern; `expected_version` muss der aktuellen Version entsprechen (`0` für die erste). Der Editor sendet nur die zum Projektmodus passende Quelle. Bearbeiten bedeutet, eine weitere Version anzulegen; die Vorversion bleibt unverändert. | `201` Skript |
| `GET /api/projects/{id}/scripts/{version}` | Version mit geordneten Szenen lesen. | `200` Skript |
| `POST /api/projects/{id}/scripts/{version}/approval` | Nur aktuelle vollständige Version freigeben und genau einen `QUEUED`-Produktionslauf speichern; wiederholter Aufruf liefert denselben Lauf. | Erstes Mal `201`, danach `200` |
| `POST /api/projects/{id}/videos/{artifact_id}/approval` | Finale Datei mit passender SHA-256-Prüfsumme nach abgeschlossenem Produktionslauf freigeben; Wiederholung liefert dieselbe Freigabe. | Erstes Mal `201`, danach `200` |
| `GET /api/projects/{id}/status` | Aktuelle Skriptversion, Skripterzeugung, Freigabe, Produktionszustand und finales Artefakt lesen. | `200` Status |
| `GET /api/artifacts/{id}` | Metadaten ohne internen Speicherpfad lesen. | `200` Artefakt |
| `GET /api/artifacts/{id}/content` | Vertragsplatzhalter für Videowiedergabe. Existierendes Artefakt liefert bis Aufgabe 18 `501 MEDIA_NOT_AVAILABLE`. | Später Dateiantwort |

Beispiel für `POST /api/projects`:

```json
{"idea":"Ein bienenfreundlicher Stadtbalkon","mode":"LOKAL"}
```

Beispiel für `POST /api/projects/{id}/scripts`:

```json
{
  "expected_version": 0,
  "title": "Bienenfreundlicher Balkon",
  "narration": "Ein kurzer Film über einen bienenfreundlichen Balkon.",
  "scenes": [
    {"narration":"Ein leerer Balkon.","visual_description":"Karger Stadtbalkon","pexels_query":"empty city balcony"},
    {"narration":"Wir wählen Blüten.","visual_description":"Blühpflanzen im Laden","pexels_query":"flower plants shop"},
    {"narration":"Jetzt wird gepflanzt.","visual_description":"Hände pflanzen Blumen","pexels_query":"planting balcony flowers"},
    {"narration":"Wasser hilft beim Anwachsen.","visual_description":"Pflanzen werden gegossen","pexels_query":"watering balcony plants"},
    {"narration":"Die erste Biene kommt.","visual_description":"Biene auf Blüte","pexels_query":"bee on flower"},
    {"narration":"Der Balkon blüht.","visual_description":"Bunter Balkon","pexels_query":"flowering city balcony"}
  ]
}
```

Bei `CLOUD` steht in jeder Szene `wan_prompt` anstelle von `pexels_query`. Die API weist gemischte oder fehlende modusspezifische Angaben mit `422 MODE_MISMATCH` ab. Leere Texte, falsche Moduswerte, zusätzliche Felder und Szenenzahlen außerhalb von 6–10 ergeben `422 VALIDATION_ERROR`.

Fehler haben die Form `{"error":{"code":"VERSION_CONFLICT","message":"..."}}`. `404` bedeutet unbekanntes Projekt/Skript/Artefakt. `409 VERSION_CONFLICT` bedeutet überholte `expected_version` oder Freigabe einer alten Version. Datenbank-Konflikte geben `409 CONFLICT` beziehungsweise `409 STATE_CONFLICT` zurück. Wiederholte aktuelle Skriptfreigaben sind idempotent und behalten Freigabe- und Produktionslauf-ID.

Die Videofreigabe erwartet `{"checksum_sha256":"<64 kleine Hex-Zeichen>"}`. Eine abweichende Prüfsumme oder eine nicht finale Datei führt zu `409 ARTIFACT_CONFLICT`; ein noch nicht abgeschlossener Produktionslauf zu `409 STATE_CONFLICT`. Wiederholtes Freigeben derselben Datei liefert dieselbe Freigabe-ID. Veröffentlichungsaufträge entstehen erst in Aufgabe 26.

**Umsetzungsgrenze:** Der Skripterzeugungs-Endpunkt reiht seit Aufgabe 10 einen RQ-Auftrag ein; dessen kontrollierte Logik ist getestet, die echte Dienstintegration und Antigravity-Anmeldung sind noch nicht abgenommen. Die Skriptfreigabe speichert einen Produktionslauf als `QUEUED`, startet aber noch keinen RQ-Produktionsjob. Das geschieht in Aufgabe 12/13. Der Dateiabruf und berechtigtes Playback folgen mit persistentem Remote-Medienspeicher in Aufgabe 18. Die aktuelle Compose-Konfiguration bindet die Weboberfläche nur an Loopback; Authentifizierung und ein öffentlicher Remote-Betrieb sind noch nicht implementiert und dürfen nicht als abgeschlossen gelten.

**Prüfung:** `docker compose -p step8check up -d --build --wait api worker`; `docker compose -p step8check exec -T api python -m unittest app.test_api app.test_database -v`. `app.test_api` legt ein isoliertes PostgreSQL-Schema an und entfernt es nach den HTTP-/OpenAPI-Vertragstests.
