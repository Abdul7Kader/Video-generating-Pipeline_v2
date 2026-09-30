# Installation auf einem eigenen Rechner – Schritt 10

Ziel ist eine installierbare Anwendung auf einem **unterstützten Windows-, macOS- oder Linux-Rechner**. Ubuntu ist ein möglicher Installationsort, keine feste Voraussetzung. Der Rechner benötigt Docker mit Compose für Web/API/PostgreSQL/Redis, Python 3.12 für den Host-Worker und die offizielle Antigravity CLI. Die CLI läuft unter dem Benutzer, der sich mit Google AI Pro angemeldet hat; dessen Betriebssystem-Schlüsselspeicher muss für den Worker zugänglich sein. Für die erste lokale Nutzung sind weder SSH noch öffentliche Ports nötig. Jede Installation besitzt zunächst ihre eigene Datenbank und eigene Medien; eine Synchronisierung zwischen Rechnern ist nicht implementiert. Die spätere Videoverarbeitung erfordert zusätzliche Werkzeuge und genügend Speicher; deren Installation und plattformübergreifende Prüfung gehören zu den Aufgaben 15–18 und 35.

## 1. Dienste auf dem Installationsrechner starten

Docker Compose und Python 3.12 gemäß Betriebssystem installieren, das GitHub-Repository auschecken und im Checkout ein starkes `POSTGRES_PASSWORD` in einer ignorierten `.env` setzen. [Docker Compose](https://docs.docker.com/compose/install/) gibt es für Windows, macOS und Linux. Die Zusatzdatei [`compose.host-worker.yaml`](../compose.host-worker.yaml) lässt den nicht angemeldeten Container-Worker weg und bindet PostgreSQL/Redis nur an `127.0.0.1`:

```sh
docker compose -f compose.yaml -f compose.host-worker.yaml up -d --build --wait db redis api
docker compose -f compose.yaml -f compose.host-worker.yaml config --services
```

In der Serviceliste soll `worker` ohne Profil `container-worker` fehlen. Standardports: `5433` (PostgreSQL), `6380` (Redis), später `4177` (Web); über `HOST_POSTGRES_PORT`, `HOST_REDIS_PORT` und `WEB_PORT` in `.env` änderbar. Diese Ports nicht öffentlich freigeben.

## 2. Antigravity und Python-Worker einrichten

Die [offizielle CLI](https://antigravity.google/docs/cli/install/) für **diesen** Benutzer auf dem Installationsrechner installieren und sich dort im Browser mit dem gewünschten Google-AI-Pro-Konto anmelden. Google dokumentiert Windows Credential Manager, macOS Keychain und Linux Secret Service als Anmeldespeicher. `agy` muss für den Hintergrundprozess im `PATH` sein. Keine Gemini-API-Key-Anmeldung verwenden.

In `~/.gemini/antigravity-cli/settings.json` (unter Windows im Benutzerprofil) `"useG1Credits": false` setzen und `modelProvider` entfernen. Die CLI entfernt beim Speichern Werte, die dem Standard entsprechen. Laut [CLI-Referenz](https://antigravity.google/docs/cli/reference/) ist der Standard von `useG1Credits` **false**; daher ist ein später fehlender Schlüssel in einer gültigen Konfigurationsdatei ebenfalls ausgeschaltet. Die Anwendung prüft dies vor jedem Aufruf: `true`, ungültige Werte, eine fehlende/ungültige Datei und jeder API-Provider werden abgewiesen. Das festgelegte Pro-Modell vor dem Live-Test mit `agy models` prüfen. Eine Modellliste bestätigt noch kein angemeldetes Pro-Konto. Keine Tokens, Profilordner oder OAuth-Codes in Git oder Chat kopieren.

Im Checkout eine Python-3.12-Umgebung und die Backend-Abhängigkeiten installieren:

| Windows PowerShell | macOS / Linux |
| --- | --- |
| `py -3.12 -m venv .venv` | `python3.12 -m venv .venv` |
| `.venv\Scripts\python.exe -m pip install -r backend/requirements.txt` | `.venv/bin/python -m pip install -r backend/requirements.txt` |

Die Vorlage [`deploy/worker.example.json`](../deploy/worker.example.json) als `~/.config/video-pipeline/worker.json` **außerhalb des Checkouts** ablegen (Windows: `$HOME\.config\video-pipeline\worker.json`). `CHANGE_ME` durch das URL-kodierte Passwort aus `.env` ersetzen; bei geänderten Host-Ports die URLs anpassen. Die Datei nur für den angemeldeten Benutzer lesbar machen. `DATABASE_URL` und `REDIS_URL` können stattdessen als Umgebungsvariablen gesetzt werden; eine vorhandene private JSON-Datei hat Vorrang. Auf Linux/macOS nutzt der Worker RQs `SpawnWorker`. Auf Windows nutzt er wegen Fehlern des `SpawnWorker` in der festgelegten RQ-Version einen `SimpleWorker` mit Timer für Jobgrenzen. Dadurch gibt es dort keine Isolation durch einen separaten RQ-Kindprozess; der Antigravity-Aufruf selbst hat weiterhin einen eigenen Prozess und ein Zeitlimit.

Die API muss bereits gestartet sein, weil sie die Datenbankmigrationen ausführt. Vor dem Workerstart aus `backend` die Voraussetzungen prüfen:

| Windows PowerShell | macOS / Linux |
| --- | --- |
| `..\.venv\Scripts\python.exe -m app.worker --check` | `../.venv/bin/python -m app.worker --check` |

Diese Prüfung kontrolliert CLI im PATH, die wirksame Kostensperre, die migrierte PostgreSQL-Datenbank und Redis. Sie führt keinen Modellaufruf aus und bestätigt noch keine Kontoanmeldung. Fehler werden ohne Zugangsdaten ausgegeben. Der normale Workerstart führt dieselbe Prüfung aus und nimmt bei fehlenden Voraussetzungen keine Aufträge an. [Kosteneinstellung](https://antigravity.google/docs/cli/credits/), [Anmeldung](https://antigravity.google/docs/cli/install/#authentication-workflows).

Danach den Worker starten:

| Windows PowerShell | macOS / Linux |
| --- | --- |
| `..\.venv\Scripts\python.exe -m app.worker` | `../.venv/bin/python -m app.worker` |

Der Prozess muss als `pipeline-worker` in Redis erscheinen. Redis-Antworttimeouts beim Warten auf Arbeit werden mit fünf Sekunden Abstand erneut versucht; dies startet keine automatische Wiederholung fehlgeschlagener Modellaufträge. RQs Einstellungen für Socket-/Wartezeiten werden beibehalten ([Verbindungen](https://python-rq.org/docs/connections/)). Danach Web im Checkout starten:

```sh
docker compose -f compose.yaml -f compose.host-worker.yaml up -d --build --wait web
```

## 3. Nach Anmeldung im Hintergrund starten

- **Windows:** [`deploy/start-worker.ps1`](../deploy/start-worker.ps1) im Task Scheduler beim **Anmelden dieses Benutzers** starten lassen, mit Startverzeichnis im Checkout und Neustart bei Fehlern. Die Aufgabe nur ausführen, wenn der Benutzer angemeldet ist, bis der Zugriff auf Windows Credential Manager bei anderen Betriebsarten geprüft wurde. Die Vorlage ergänzt den üblichen Antigravity-Pfad im Benutzerprofil.
- **Linux mit systemd:** [`deploy/video-script-worker.service`](../deploy/video-script-worker.service) nach `~/.config/systemd/user/` kopieren; `REPO_CHECKOUT` und `VENV_PYTHON` durch absolute Pfade ersetzen. Dann `systemctl --user daemon-reload` und `systemctl --user enable --now video-script-worker.service`. Status und Fehler: `systemctl --user status video-script-worker.service`, `journalctl --user -u video-script-worker.service -n 50 --no-pager`.
- **macOS:** [`deploy/com.video-pipeline.worker.plist`](../deploy/com.video-pipeline.worker.plist) als LaunchAgent unter `~/Library/LaunchAgents/` ablegen. `REPO_CHECKOUT`, `VENV_PYTHON` und `HOME_LOCAL_BIN` durch absolute Pfade ersetzen; danach mit `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.video-pipeline.worker.plist` starten und den Zustand prüfen.

Diese Hintergrundstarts setzen eine Benutzersitzung mit entsperrtem Schlüsselspeicher voraus. Ein automatischer Modellaufruf nach Neustart **ohne** Anmeldung ist auf keinem System nachgewiesen und darf nicht vorausgesetzt werden.

## 4. End-to-End-Abnahme

Auf demselben Rechner `http://127.0.0.1:4177/` (oder den konfigurierten Web-Port) öffnen. Idee und Modus speichern, ohne weitere Eingabe ein echtes Pro-Skript erhalten und Speicherung nach Neuladen prüfen. Fehlende Anmeldung, erschöpftes Kontingent und ungültige Antworten müssen sichtbar scheitern; Wiederholung nur nach bewusstem Klick. Keine Gemini API und keine zusätzlichen AI-Credits aktivieren.

**Abgenommen am 30.09.2026:** Windows-Host-Worker mit privater Konfiguration und `deploy/start-worker.ps1` im Hintergrund für die aktuelle Sitzung; echte Pro-Skripte für beide Modi, Bearbeitung, Versionierung und Neuladen sowie kontrollierte Fehler/Retry. [Prüfbericht](step10-acceptance.md). **Noch offen in Aufgabe 35:** automatischer Start nach Login/Neustart, Betrieb ohne entsperrte Benutzersitzung und vollständige macOS-/Linux-Installation. Startvorlagen allein sind kein Prüfnachweis für diese Betriebsarten.
