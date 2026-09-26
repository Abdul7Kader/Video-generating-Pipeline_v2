# Video-generating-Pipeline v2

Stand: Schritt 6. Das Web-Grundgerüst mit React, FastAPI, RQ-Worker, PostgreSQL und Redis ist implementiert. Skriptintegration, Videoproduktion und Veröffentlichung folgen in den nächsten Schritten.

Die geplante Anwendung nimmt eine Videoidee und den Modus `LOKAL` oder `CLOUD` in einer Weboberfläche entgegen. Ein Hintergrundauftrag soll mit dem vorhandenen Google-AI-Pro-Konto über die offizielle Antigravity CLI ein Skript erzeugen, ohne Gemini Developer API und ohne Codex zur Laufzeit. Nach Prüfung und Freigabe wird das Video erstellt. Social-Media-Veröffentlichungen folgen erst nach der Videoabnahme.

Der Prototyp unter [`tasks/`](tasks/) enthält den [Umsetzungsplan](tasks/plan.md), die [Aufgabenliste](tasks/todo.md), das [Skriptformat](tasks/script-probe.md) und vier geprüfte Beispielskripte. Zwei davon wurden automatisch mit Antigravity CLI erzeugt. Die [Pexels-Probe](tasks/pexels-probe.md) hat drei echte Suchtreffer und einen geprüften Download nachgewiesen. Der [Wan/Modal-Entwurf](tasks/wan-modal-design.md) beschreibt Workflow, Gewichte, Rücktransfer, unsichere Kostenwerte und die Sperre für einen kostenfreien Live-Test.

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

Die Einbindung in die Weboberfläche ist als Aufgabe 10 geplant. Sobald eine lauffähige Oberfläche mit sichtbarer Skript- oder Videovorschau vorliegt, kann sie vorgeführt werden.
