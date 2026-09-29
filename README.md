# Video-generating-Pipeline v2

Stand: Schritt 10 in Arbeit. Die Weboberfläche legt Projekte in PostgreSQL an und startet nach dem Speichern automatisch einen Skriptauftrag über Redis/RQ. Kontrollierte Skriptantworten werden validiert und gespeichert; die echte Antigravity-Probe auf einem angemeldeten Installationsrechner ist noch offen. Videoproduktion und Veröffentlichung folgen später.

**Entwicklung auf Windows, Installation auf einem unterstützten Rechner:** Einstieg über [STATE.md](STATE.md). Code und kontrollierte Tests laufen zunächst am aktuellen Windows-Entwicklungsrechner über dieses GitHub-Repository. Die Anwendung soll auf Windows, macOS oder Linux mit den benötigten Laufzeitwerkzeugen installierbar sein; Ubuntu ist ein möglicher Zielrechner. [Installationsanleitung](tasks/install-on-computer.md). [AGENTS.md](AGENTS.md) enthält die Projektregeln.

Die geplante Anwendung nimmt eine Videoidee und den Modus `LOKAL` oder `CLOUD` in einer Weboberfläche entgegen. Ein Hintergrundauftrag soll mit dem vorhandenen Google-AI-Pro-Konto über die offizielle Antigravity CLI ein Skript erzeugen, ohne Gemini Developer API und ohne Codex zur Laufzeit. Nach Prüfung und Freigabe wird das Video erstellt. Social-Media-Veröffentlichungen folgen erst nach der Videoabnahme.

Der Prototyp unter [`tasks/`](tasks/) enthält den [Umsetzungsplan](tasks/plan.md), die [Aufgabenliste](tasks/todo.md), das [Skriptformat](tasks/script-probe.md) und vier geprüfte Beispielskripte. Zwei davon wurden automatisch mit Antigravity CLI erzeugt. Die [Pexels-Probe](tasks/pexels-probe.md) hat drei echte Suchtreffer und einen geprüften Download nachgewiesen. Der [Wan/Modal-Entwurf](tasks/wan-modal-design.md) beschreibt Workflow, Gewichte, Rücktransfer, unsichere Kostenwerte und die Sperre für einen kostenfreien Live-Test.

Der [API-Vertrag](tasks/api-contract.md) beschreibt die Endpunkte und Beispielpayloads aus Schritt 8. Die OpenAPI-Dokumentation liegt bei gestartetem Compose-Stack unter `/api/docs`. Die API speichert bei Skriptfreigabe bereits einen Produktionslauf als `QUEUED` und kann eine finale Datei per Prüfsumme freigeben; RQ-Ausführung, Dateiabruf und Publikationsaufträge folgen später.

## Webanwendung lokal starten

Voraussetzung: Docker mit Linux-Containern und Docker Compose ([Installation](https://docs.docker.com/compose/install/)). Im Projektordner für kontrollierte Entwicklungstests:

```powershell
docker compose up --build -d --wait
```

Falls `docker` auf Windows nicht im PATH liegt, den installierten Befehl direkt aufrufen: `& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' compose up --build -d --wait`.

Danach [http://localhost:4177](http://localhost:4177) öffnen. Eine Videoidee eingeben, `LOKAL` oder `CLOUD` wählen und „Projekt speichern“ drücken. Die Seite startet den Skriptauftrag und zeigt seinen Status, das gespeicherte Skript oder einen Fehler mit bewusster Wiederholung. Ohne Antigravity-CLI, angemeldetes Pro-Konto und ausdrücklich deaktivierte AI-Credit-Überziehung auf dem Worker wird kein Modellaufruf gestartet. Es entsteht noch kein Video. Ein Healthcheck ist unter [http://localhost:4177/api/health/ready](http://localhost:4177/api/health/ready) erreichbar. Die API-Dokumentation liegt unter [http://localhost:4177/api/docs](http://localhost:4177/api/docs). Der Web-Port kann über `WEB_PORT` in der lokalen `.env` geändert werden.

```powershell
docker compose ps
docker compose down
```

`down` lässt die Datenbank- und Redis-Volumes bestehen. Vor dem produktiven Betrieb ein eigenes `POSTGRES_PASSWORD` in der ignorierten `.env` setzen. Das Passwort aus `.env.example` ist nur für lokale Entwicklung. Der Pexels-Key bleibt lokal in `.env` und wird noch keinem Container übergeben. Modal und Social-Media-Konten werden hier nicht verwendet.

Beim Start der API wird Migration 0001 automatisch auf PostgreSQL angewandt. Für einen separaten Datenbanktest nach `docker compose up -d --wait db`:

```powershell
docker compose run --rm api python -m app.migrate up
docker compose run --rm api python -m unittest app.test_database -v
docker compose run --rm api python -m unittest app.test_api -v
```

Die Rückmigration `python -m app.migrate down` löscht alle sieben Fachtabellen und ist nur für eine **wegwerfbare Testdatenbank** vorgesehen.

## Lokale Prüfung

```powershell
python -m unittest discover -s tasks -p test_script_probe.py -v
python tasks/script_probe.py validate --mode LOKAL --file tasks/response-balkon-agy.json
python tasks/script_probe.py validate --mode CLOUD --file tasks/response-regen-agy.json
```

Für eine neue automatische Skriptprobe muss die offizielle Antigravity CLI (`agy`) installiert und mit dem gewünschten Google-Konto angemeldet sein. Der Prototyp verweigert eine aktivierte automatische AI-Credit-Überziehung und verwendet keinen Gemini-API-Key.

```powershell
python tasks/agy_script_probe.py --idea "Ein Regentag in der Stadt" --mode CLOUD --out tasks/neues-skript.json
```

Für die echte Live-Prüfung von Aufgabe 10 kann ein unterstützter Windows-, macOS- oder Linux-Rechner eingerichtet werden. Die [Installationsanleitung](tasks/install-on-computer.md) beschreibt den angemeldeten Host-Worker, die [Compose-Zusatzdatei](compose.host-worker.yaml) und den Start im Hintergrund je Betriebssystem. Auf **diesem** Rechner muss die [Antigravity CLI](https://antigravity.google/docs/cli/install/) mit dem gewünschten Google-AI-Pro-Konto angemeldet sein. `~/.gemini/antigravity-cli/settings.json` muss ausdrücklich `"useG1Credits": false` enthalten; `modelProvider` darf nicht gesetzt sein. Die Standard-Compose-Worker-Umgebung enthält keine CLI oder Anmeldung und dient der kontrollierten Fehler- und Integrationsprüfung. Keine Gemini API und kein API-Key als Ersatz. Anmeldungen werden nicht über GitHub übertragen. Windows- und macOS-Hostbetrieb sowie die Live-Abnahme sind noch ungeprüft.
