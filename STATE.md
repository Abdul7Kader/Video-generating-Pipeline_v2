# Projektzustand – Übergabe an Codex Cloud

Stand: **27. September 2026**. Repository: [Abdul7Kader/Video-generating-Pipeline_v2](https://github.com/Abdul7Kader/Video-generating-Pipeline_v2), Branch `main`. Diese Datei ist der Einstieg für neue Cloud-Chats; [tasks/todo.md](tasks/todo.md) enthält die verbindlichen Abnahmekriterien und [tasks/plan.md](tasks/plan.md) die Produktentscheidungen. Den tatsächlichen Git-Stand vor neuer Arbeit prüfen.

## Wo die Entwicklung steht

- **Aufgaben 01–07 erledigt.** Produktparameter, kostenfreier Skriptweg, echte Gemini-Pro-/Antigravity-Skriptprobe, echte Pexels-Probe und Wan/Modal-Entwurf sind dokumentiert. React, FastAPI, RQ-Worker, PostgreSQL und Redis wurden in Aufgabe 06 aus einem frischen Checkout per Compose gebaut und gestartet. Aufgabe 07 ergänzt sieben Fachtabellen mit Migration, Freigabe- und Zustandsregeln. Prüfberichte: [Skript](tasks/script-probe.md), [Pexels](tasks/pexels-probe.md), [Wan/Modal](tasks/wan-modal-design.md).
- **Nächste Aufgabe: 08 – API-Vertrag.** FastAPI-Schemas und Endpunkte für Projektanlage, Lesen/Bearbeiten von Skriptversionen, Freigaben, Status und Medienabruf definieren. Versionskonflikt, Validierungsfehler und wiederholte Freigabe brauchen definierte Antworten und OpenAPI-/Vertragstests. Danach folgen Idee-/Modusformular (09) und echte Skriptintegration (10).
- **Prüfnachweis für Aufgabe 07:** `backend/app/migrations/0001_initial.sql` auf leerer PostgreSQL-17-Datenbank angewandt, mit `0001_initial.down.sql` zurückgenommen und erneut angewandt; sieben Fachtabellen und Migrationsversion 1 abgefragt. Vier echte PostgreSQL-Integrationstests in `backend/app/test_database.py` bestanden. Compose-API meldete `ready` für DB, Redis und Worker. Acht vorhandene Python-Tests und `npm run build --prefix web` erfolgreich. Die Migration startet bei Compose-API-Start automatisch. Noch keine fachlichen API-Endpunkte oder Eingabeoberfläche.
- **Noch nicht gebaut:** Idee eingeben, Skript in der Weboberfläche, Videoerstellung, Videovorschau und Social-Media-Veröffentlichung. Die bestehende React-Seite zeigt nur den Infrastrukturstatus. `LOKAL` bezeichnet den Pexels-Videomodus, nicht den Standort der Entwicklung.

## Cloud-Arbeitsplatz einrichten

1. Der Betreiber verbindet in [Codex Cloud](https://learn.chatgpt.com/docs/cloud) sein GitHub-Konto mit **diesem Repository** und erstellt dafür eine [Cloud-Umgebung](https://learn.chatgpt.com/docs/environments/cloud-environment). Diese Kontoverbindung kann ein Git-Commit nicht selbst herstellen; ihr Status wurde hier noch nicht verifiziert.
2. Die Umgebung checkt `main` aus. Für den Code passen **Python 3.12** und **Node 22** zu den Dockerfiles. Als Setup-Skript genügen zunächst `python -m pip install -r backend/requirements.txt` und `npm ci --prefix web`. Für Datenbank-Vertragstests braucht die Cloud-Umgebung einen erreichbaren PostgreSQL-Testdienst. Ob Docker/Compose dort verfügbar ist, muss der Cloud-Chat prüfen; ein Docker-Test darf nur als bestanden gelten, wenn er tatsächlich ausgeführt wurde.
3. Nächsten Cloud-Chat mit diesem Auftrag starten: **„Lies `AGENTS.md`, `STATE.md`, `tasks/plan.md` und `tasks/todo.md`. Setze Aufgabe 08 vollständig um: FastAPI-Vertrag auf Grundlage der Migration 0001, dokumentierte Fehlerantworten und Vertragstests. Prüfe mit PostgreSQL, aktualisiere den Projektzustand und erstelle einen prüfbaren GitHub-PR.“** Codex Cloud zeigt Änderungen als Diff; der Betreiber prüft und übernimmt sie über GitHub. [Offizielle Anleitung](https://learn.chatgpt.com/docs/cloud)

Für Codeprüfungen ohne externe Konten: `npm run build --prefix web` und `python -m unittest discover -s tasks -p 'test_*.py' -v`. Für echte Datenbankregeln nach Migration: `docker compose up -d --wait db`, `docker compose run --rm api python -m app.migrate up` und `docker compose run --rm api python -m unittest app.test_database -v` in einer isolierten Testumgebung. Ein Compose-Integrationstest bleibt zusätzlich nötig, wenn die Aufgabe Dienste oder Datenbankverhalten ändert. Das frühere `http://localhost:4177` ist **nur auf dem Windows-Rechner** erreichbar und keine Cloud-Vorschau.

## Zugänge und Daten, die nicht im Git-Checkout liegen

| Abhängigkeit | Zustand und Vorgehen |
| --- | --- |
| `.env`, Pexels-Key, heruntergeladener Probeclip | Nur lokal vorhanden und absichtlich von Git ausgeschlossen. Aufgaben 08–09 benötigen sie nicht. Spätere Pexels-Live-Tests brauchen einen neu im **Remote-Laufzeitsystem** bereitgestellten Key; keine Zugangsdaten in Git, Chat oder Browser-Bundle. Kontrollierte Tests können die versionierten Beispielantworten verwenden. |
| Google-AI-Pro-/Antigravity-Anmeldung | Die frühere Prototyp-Sitzung war auf dem Windows-Rechner angemeldet. Sie ist **nicht** in Codex Cloud oder auf einem Remote-Worker vorhanden. Aufgabe 10 kann in der Cloud implementiert und mit kontrollierten Antworten getestet werden; die echte End-to-End-Abnahme benötigt eine eigene, bestätigte Anmeldung auf einem erreichbaren Worker. Keine Gemini Developer API, kein bezahlter Fallback und keine automatische Credit-Überziehung. |
| Remote-Testbetrieb und persistente Medien | Noch nicht eingerichtet/nachgewiesen. Vor der echten Videoprüfung in Aufgabe 19 und Aufgabe 24 braucht die Anwendung einen erreichbaren Server mit persistentem Speicher und Browserzugang, vorzugsweise den vorgesehenen Ubuntu-Server. Das ist von der Codex-Cloud-**Entwicklungsumgebung** getrennt. Aufgabe 18 erfasst diese Voraussetzung; Aufgabe 35 schließt den produktiven Betrieb ab. |
| Modal | Konto, Credits, Zahlungsmethode und wirksames Limit von **0 USD Nettokosten** sind nicht nachgewiesen. Keine echte Wan-/Modal-GPU-Generierung vor Aufgabe 24 und vor bestätigter Kostensperre. |
| YouTube, TikTok, Meta, X | Konten/Rechte/Reviews noch offen und erst **nach** echter Videoabnahme relevant. Keine kostenpflichtigen APIs ohne neue Entscheidung. |

Codex-Cloud-[Secrets](https://learn.chatgpt.com/docs/environments/cloud-environment) sind laut offizieller Dokumentation nur im Setup-Skript verfügbar und vor der Agentenphase entfernt. Darum keine Annahme treffen, dass ein dort eingetragener Key automatisch für App-Laufzeit oder spätere Agent-Tests verfügbar ist. Produktionsgeheimnisse gehören in die Secret-Verwaltung des **Remote-Laufzeitsystems**.

## Verbindliche Produktregeln

- Idee → automatisches strukturiertes Skript über bestehendes Gemini-Pro-Abo via Antigravity CLI → Benutzerfreigabe → Videoproduktion → abspielbare Vorschau. **Codex ist kein Bestandteil der Laufzeit.**
- `LOKAL`: ausschließlich Pexels-Stockvideos (`STOCK_VIDEO`). `CLOUD`: ausschließlich Wan 2.2 T2V-A14B über ComfyUI auf Modal `A100-80GB` (`AI_GENERATED_VIDEO`). Nie Quellen in einem Video mischen oder still auf eine andere Quelle wechseln.
- Zuerst echte Videos ansehen; Social-Media-Adapter folgen danach. Keine kostenpflichtigen APIs; Modal nur innerhalb belegter Gratis-Credits mit wirksamer Null-Nettokosten-Grenze.
- Nach jedem abgeschlossenen Schritt [tasks/todo.md](tasks/todo.md), [tasks/plan.md](tasks/plan.md) und diese Datei aktualisieren. Erledigung nur mit benanntem Prüfnachweis markieren.
