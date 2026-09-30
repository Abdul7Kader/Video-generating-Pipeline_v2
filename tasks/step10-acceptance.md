# Abnahme von Schritt 10 und 11

Stand: **30. September 2026 – abgeschlossen auf Windows.** Nächster Schritt: 12 (Skriptfreigabe). Die bestehenden Abnahmekriterien wurden vollständig geprüft; der dazu erforderliche Editor aus Schritt 11 wurde ergänzt.

## Voraussetzungen und Kompatibilitätskorrekturen

- Installationsrechner dieser Abnahme: aktueller Windows-Entwicklungsrechner. Betreiber bestätigt abgeschlossene Antigravity-Einrichtung und gewünschtes Google-AI-Pro-Konto; interaktive CLI danach beendet. Keine Zugangsdaten im Bericht.
- AI-Credits ausdrücklich deaktiviert, kein API-Provider. Antigravity entfernt ausgeschaltete Standardwerte beim Speichern. [Settings](https://antigravity.google/docs/cli/settings/) und [CLI-Referenz](https://antigravity.google/docs/cli/reference/) belegen Sparse Persistence und Credit-Standard **false**. Gültige Settings ohne Schlüssel sind ausgeschaltet; aktive/ungültige Werte, fehlende/ungültige Dateien und API-Provider bleiben gesperrt. Der Worker prüft vor jedem Modellaufruf und entfernt API-Key-Variablen aus der Kindprozessumgebung.
- Modell `gemini-3.1-pro-high`, Sandbox, modusspezifisches JSON-Schema und 180-/210-Sekunden-CLI-/Prozessgrenzen. Ein echter CLI-Aufruf lieferte `SUCCESS`, aber zusätzliche Textdaten neben einem separaten `structured_output`. Die korrigierte Auswertung bevorzugt das vollständig fachlich validierte Schemaergebnis; ungültige strukturierte Daten und doppelte JSON-Schlüssel werden abgewiesen. [Headless-Dokumentation](https://antigravity.google/docs/cli/headless/#structured-output-with-a-schema).
- Workerstart prüft CLI, wirksame Kostensperre, migriertes PostgreSQL und Redis. `--check` erzeugt kein Skript und zeigt keine Secrets. Die Installationsreihenfolge startet die migrierende API vor dem Worker. Die eigenständige CLI-Probe teilt diese Laufzeitgrenzen.

## Echte Skript- und Browserläufe

| Lauf | Nachweis | Ergebnis |
| --- | --- | --- |
| Direkte Pro-Probe | [Validierte Antwort](step10-response-lokal.json) | LOKAL, sieben Szenen, 40 Sekunden |
| LOKAL im Chrome-Browser | Projekt `03fb8835-e7e1-4fe7-bc0b-c0ac1b711c3d`, Job `dd4ae746-bdf4-4e38-bc9c-5aba9f2a544e` | Echtes Pro-Skript, sieben Szenen, 45 Sekunden |
| CLOUD im Chrome-Browser | Projekt `0258ed4c-48ca-46c9-b9a9-1981dd900c59`, Job `e10f427f-18bf-4d3f-9548-ea4d3b488894` | Echtes Pro-Skript, sieben Szenen, 42 Sekunden |
| Normale Anwendung, Port 4177 | Projekt `ace8b4fe-0ca5-4ec6-875d-d562f11c4929`, Job `82bdae4f-eade-4e3b-8ba2-d3b3703c01b3` | Nach Redis-Reparatur über Windows-Startvorlage automatisch erzeugt: sieben Szenen, 45 Sekunden; bearbeitet und als Version 2 neu geladen |

Beide Browserläufe: Idee/Modus im Formular absenden → Redis/RQ → angemeldeter nativer Windows-Host-Worker → Antigravity Pro → vollständig validiertes PostgreSQL-Skript mit geordneten Szenen → sichtbares Ergebnis und Neuladen. Kein manuelles Kopieren, kein Codex zur Laufzeit, keine Gemini API. CLOUD erzeugte ausschließlich ein Skript; Modal wurde nicht aufgerufen.

## Editor und kontrollierte Fehler

- Beide echten Ergebnisse im Browser bearbeitet: Titel, Szenensprechertext, Bildbeschreibung und Pexels-Suchbegriffe beziehungsweise Wan-Prompt. Version 2 gespeichert und erneut geladen. Vollständige Dauer-/Suchmetadaten erhalten; Version 1 vollständig unverändert.
- Parallel angelegte Version 3 führte bei einem alten Entwurf zu sichtbarem `409`-Konflikt. Eigene Eingaben blieben erhalten; bewusstes Verwerfen/Neuladen zeigte Version 3. Doppelte Pexels-Suchbegriffe wurden sichtbar abgewiesen.
- Kontrollierter Fehlerlauf im isolierten Stack: `AUTH_REQUIRED` → bewusster Retry → `QUOTA_EXHAUSTED` → bewusster Retry → `INVALID_SCRIPT` → bewusster Retry → gültige kontrollierte Antwort. Jeder Fehler war im Browser verständlich sichtbar, erzeugte keine Skriptversion und ein Klick erzeugte eine neue Job-ID. Fehler und der abschließende Antwort-Datensatz waren simuliert; die erfolgreichen LOKAL-/CLOUD-Läufe oben waren echte Modellaufrufe. Keine automatische Modellwiederholung oder kostenpflichtiger Fallback.
- API-Integration prüft zusätzlich inkonsistente Dauer, fehlende Metadaten, abweichenden Gesamtsprechertext, falschen Modus und unveränderliche Versionen.

## Integration und Hintergrundbetrieb

- `npm run build --prefix web`: bestanden.
- `python -m unittest discover -s backend/app -p 'test_*.py' -v`: **25 Tests bestanden**, echte PostgreSQL-/Redis-/RQ-Integration gegen isolierten Compose-Stack (Web 14177, DB 15433, Redis 16380).
- `python -m unittest discover -s tasks -p 'test_*.py' -v`: **acht Tests bestanden**.
- Vier API-Vertragstests zusätzlich im final gebauten API-Container bestanden; Testdaten benötigen keine Dateien außerhalb des Backend-Images.
- Nativer Windows-Worker verarbeitete einen echten Redis-Auftrag auch nach kontrollierter Unterbrechung seines Warteschlangenzugriffs. Beim längeren normalen Hintergrundstart trat tatsächlich ein Redis-Sockettimeout auf; RQ 2.3.2 beendet dafür die Arbeitsschleife. Die Worker-Erweiterung wiederholt ausschließlich den Warteschlangenzugriff mit fünf Sekunden Abstand und lässt Modellfehler weiter bewusst bestätigen. [RQ-Verbindungen](https://python-rq.org/docs/connections/), [Quellcode 2.3.2](https://github.com/rq/rq/blob/v2.3.2/rq/worker.py).
- Nach der Reparatur trat am 30.09. um 11:32:15 erneut ein echter Redis-Timeout im längeren Windows-Hintergrundlauf auf. Um 11:32:20 setzte derselbe Worker die Arbeitsschleife fort; die normale Bereitschaftsprüfung meldete anschließend wieder DB, Redis und Worker als bereit. Kein Prozessneustart und kein zusätzlicher Modellaufruf nötig.
- Normale Anwendung auf `http://127.0.0.1:4177/` mit vorhandenen Datenbank-/Redis-Volumes wieder gestartet. Privates `~/.config/video-pipeline/worker.json` liegt außerhalb des Repositorys, nur für Betreiber/SYSTEM lesbar. Alter Container-Worker entfernt; Host-Worker über `deploy/start-worker.ps1` unsichtbar für die aktuelle Benutzersitzung gestartet. Bereitschaft zeigt DB, Redis und Worker.
- Docker Desktop 29.8.0 läuft nach vollständigem Betreiber-Neustart wieder. Zuvor unzugängliche AF-Unix-Sockets wurden reversibel in ausschließlich mit Laufzeit-Sockets belegten Ordnern gesichert: `%LOCALAPPDATA%/Docker/run-step10-recovery` und `%LOCALAPPDATA%/docker-secrets-engine-step10-recovery`. Containerdaten wurden dabei nicht gelöscht; kein Factory Reset.
- Die Codex-Browsersteuerung scheiterte lokal mit `helper_unknown_error`; die UI-Abnahme erfolgte deshalb mit echtem isoliertem Chrome über CDP. Die Browseransicht wurde visuell geprüft. Testskripte, Sitzungsdateien und Testbrowserprofil wurden entfernt; der isolierte Compose-Stack einschließlich seiner Testvolumes wurde ebenfalls entfernt. Die normale Anwendung und ihr Host-Worker laufen weiter.

## Offen außerhalb dieser Schritte

- Aufgabe 12: Skriptfreigabe im Browser und danach Produktionskette, echte Videos, Medienwiedergabe und Social Media.
- Aufgabe 35: vollständige macOS-/Linux-Installation sowie automatischer Start nach Login/Neustart und Betrieb ohne entsperrte Benutzersitzung. Die geprüfte Windows-Sitzung belegt diese anderen Betriebsarten nicht. [Installationsanleitung](install-on-computer.md).
- Modal bleibt gesperrt, bis Gratis-Credits und eine wirksame Grenze von 0 USD Nettokosten belegt sind.
