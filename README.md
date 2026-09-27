# Video-generating-Pipeline v2

Stand: Schritt 8. Web-Grundgerüst, PostgreSQL-Datenmodell und fachliche API für Projekte, Skriptversionen, Freigabe und Status sind implementiert. Die Oberfläche zur Ideeneingabe, automatische Skriptgenerierung, Videoproduktion und Veröffentlichung folgen in den nächsten Schritten.

**Weiterentwicklung in Codex Cloud:** Einstieg über [STATE.md](STATE.md). Dort stehen der geprüfte Stand, Aufgabe 09 als nächster Schritt, die Cloud-Einrichtung und die fehlenden Remote-Zugänge. [AGENTS.md](AGENTS.md) gibt Codex die Projektregeln automatisch mit. Der folgende `localhost`-Abschnitt beschreibt nur den bisherigen lokalen Nachweis von Schritt 6; neue Codearbeit soll ohne diesen Rechner am GitHub-Repository stattfinden.

Die geplante Anwendung nimmt eine Videoidee und den Modus `LOKAL` oder `CLOUD` in einer Weboberfläche entgegen. Ein Hintergrundauftrag soll mit dem vorhandenen Google-AI-Pro-Konto über die offizielle Antigravity CLI ein Skript erzeugen, ohne Gemini Developer API und ohne Codex zur Laufzeit. Nach Prüfung und Freigabe wird das Video erstellt. Social-Media-Veröffentlichungen folgen erst nach der Videoabnahme.

Der Prototyp unter [`tasks/`](tasks/) enthält den [Umsetzungsplan](tasks/plan.md), die [Aufgabenliste](tasks/todo.md), das [Skriptformat](tasks/script-probe.md) und vier geprüfte Beispielskripte. Zwei davon wurden automatisch mit Antigravity CLI erzeugt. Die [Pexels-Probe](tasks/pexels-probe.md) hat drei echte Suchtreffer und einen geprüften Download nachgewiesen. Der [Wan/Modal-Entwurf](tasks/wan-modal-design.md) beschreibt Workflow, Gewichte, Rücktransfer, unsichere Kostenwerte und die Sperre für einen kostenfreien Live-Test.

Der [API-Vertrag](tasks/api-contract.md) beschreibt die Endpunkte und Beispielpayloads aus Schritt 8. Die OpenAPI-Dokumentation liegt bei gestartetem Compose-Stack unter `/api/docs`. Die API speichert bei Skriptfreigabe bereits einen Produktionslauf als `QUEUED` und kann eine finale Datei per Prüfsumme freigeben; RQ-Ausführung, Dateiabruf und Publikationsaufträge folgen später.

## Webanwendung lokal starten

Voraussetzung: Docker Desktop mit Linux-Containern und Docker Compose. Im Projektordner:

```powershell
docker compose up --build -d --wait
```

Falls `docker` auf Windows nicht im PATH liegt, den installierten Befehl direkt aufrufen: `& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' compose up --build -d --wait`.

Danach [http://localhost:4177](http://localhost:4177) öffnen. Die Seite zeigt den aktuellen Status von PostgreSQL, Redis und dem RQ-Worker. Ein Healthcheck ist auch unter [http://localhost:4177/api/health/ready](http://localhost:4177/api/health/ready) erreichbar. Die API-Dokumentation liegt unter [http://localhost:4177/api/docs](http://localhost:4177/api/docs). Der Web-Port kann über `WEB_PORT` in der lokalen `.env` geändert werden.

```powershell
docker compose ps
docker compose down
```

`down` lässt die Datenbank- und Redis-Volumes bestehen. Die Weboberfläche ist der sichtbare Stand von Schritt 6; die Eingabe einer Videoidee folgt in Schritt 9. Vor dem produktiven Betrieb ein eigenes `POSTGRES_PASSWORD` in der ignorierten `.env` setzen. Das Passwort aus `.env.example` ist nur für lokale Entwicklung. Der Pexels-Key bleibt lokal in `.env` und wird in Schritt 6 noch keinem Container übergeben. Modal und Social-Media-Konten werden hier nicht verwendet.

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

Die Einbindung in die Weboberfläche ist als Aufgabe 10 geplant. Für ihre echte Live-Prüfung benötigt ein erreichbarer Remote-Worker eine eigene Google-AI-Pro-/Antigravity-Anmeldung; die bisherige lokale Anmeldung wird nicht über GitHub übertragen.
