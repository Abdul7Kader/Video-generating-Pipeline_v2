# Video-generating-Pipeline v2

Stand: Schritte **01–17** und Meilenstein M1 abgeschlossen. Nach Skriptbearbeitung/Freigabe beschafft LOKAL Pexels-Clips, Piper erzeugt deutsche Sprache und Remotion Titel/Untertitel. FFmpeg setzt daraus jetzt eine echte MP4 zusammen: 720 × 1280, 24 fps, H.264/AAC. 72 Backendtests ohne Überspringen, zehn Projekttests, Web-Build und echte Produktions-/Browserprüfung bestanden. Nächster Schritt: **18 – Endablage und berechtigter Videoabruf**.

**Schritt 17 abgeschlossen (04.10.2026):** Erstes echtes LOKAL-Video: sechs Szenen, 36 Sekunden, Titel, Untertitel und Sprecherstimme. Vollständige Wiedergabe und Sollprofil geprüft. Die Oberfläche zeigt Dauer, Format, Codecs und Dateigröße. MP4 liegt zunächst als Zwischenartefakt unter `<MEDIA_ROOT>/encoding/<run-id>/master.mp4`; STORAGE/FINAL-Ablage und reguläres Playback in der App fehlen noch. [Prüfbericht](tasks/step17-acceptance.md), [FFmpeg einrichten](tasks/install-on-computer.md#9-ffmpeg-schnitt-und-encoding-ab-schritt-17).

**Schritt 16 abgeschlossen (04.10.2026):** Echte Dienstprüfung und normaler LOKAL-Auftrag speichern sechs Stockclips, sechs Sprachdateien und sieben Grafiken. Die Oberfläche zeigt Grafikprofil und Untertitelzeiten auch nach Neuladen und bei 320 Pixeln. Encoding ist in Schritt 17 ergänzt; der Auftrag stoppt bis Schritt 18 bei STORAGE. [Prüfbericht](tasks/step16-acceptance.md), [Remotion installieren](graphics/README.md).

**Schritt 15:** Lokale deutsche Piper-Sprachsegmente mit gemessenen Szenendauern, sichtbarer Fehlerblockade und Wiederaufnahme. Migration 0004, normale Produktion und Browseranzeige geprüft; die langsamere zweite Hörprobe ist vom Betreiber bestätigt. MP4-Encoding ist in 17 ergänzt; Endablage und reguläre Wiedergabe folgen in 18. [Prüfbericht](tasks/step15-acceptance.md), [Piper installieren](tasks/install-on-computer.md#7-piper-sprachsynthese-ab-schritt-15).

**Entwicklung auf Windows, Installation auf einem unterstützten Rechner:** Einstieg über [STATE.md](STATE.md). Code und kontrollierte Tests laufen zunächst am aktuellen Windows-Entwicklungsrechner über dieses GitHub-Repository. Die Anwendung soll auf Windows, macOS oder Linux mit den benötigten Laufzeitwerkzeugen installierbar sein; Ubuntu ist ein möglicher Zielrechner. [Installationsanleitung](tasks/install-on-computer.md). [AGENTS.md](AGENTS.md) enthält die Projektregeln.

Die Anwendung nimmt eine Videoidee und den Modus `LOKAL` oder `CLOUD` in einer Weboberfläche entgegen. Ein Hintergrundauftrag erzeugt mit dem vorhandenen Google-AI-Pro-Konto über die offizielle Antigravity CLI ein Skript, ohne Gemini Developer API und ohne Codex zur Laufzeit. Die Skriptfreigabe übergibt einen versionsgebundenen Produktionsauftrag an den Host-Worker. Dieser führt die persistente Produktionskette aus und meldet noch fehlende Medienadapter ausdrücklich. Nach Pexels-Beschaffung, Sprachsynthese und Grafiken ist der Videoschnitt aus 17 geprüft; Auslieferung folgt in 18 und CLOUD-Beschaffung ab 21. Social-Media-Veröffentlichungen folgen erst nach der Videoabnahme.

Der Prototyp unter [`tasks/`](tasks/) enthält den [Umsetzungsplan](tasks/plan.md), die [Aufgabenliste](tasks/todo.md), das [Skriptformat](tasks/script-probe.md) und vier geprüfte Beispielskripte. Zwei davon wurden automatisch mit Antigravity CLI erzeugt. Die [Pexels-Probe](tasks/pexels-probe.md) hat drei echte Suchtreffer und einen geprüften Download nachgewiesen. Der [Wan/Modal-Entwurf](tasks/wan-modal-design.md) beschreibt Workflow, Gewichte, Rücktransfer, unsichere Kostenwerte und die Sperre für einen kostenfreien Live-Test.

Der [API-Vertrag](tasks/api-contract.md) beschreibt die Endpunkte und Beispielpayloads. Die OpenAPI-Dokumentation liegt bei gestartetem Compose-Stack unter `/api/docs`. Bei Skriptfreigabe speichert die API einen `QUEUED`-Produktionslauf und übergibt ihn an RQ; der Status zeigt Freigabe, Schritte, Versuche und sichere Fehlerursache. Wiederzustellung nach Broker-/Worker-Ausfall erfolgt automatisch; bewusste Wiederaufnahme und Abbruch sind im Browser möglich. Dateiabruf und Publikationsaufträge folgen später.

Die Oberfläche zeigt Wartezeiten durch Ladebalken und unterscheidet Aktionen, deaktivierte Buttons und Statusanzeigen durch ihre Gestaltung. Der Editor bietet eine mitlaufende Speicherleiste, Tastaturfokus und Schutz ungespeicherter Änderungen beim Neuladen. Langsame oder fehlgeschlagene Anfragen bleiben erneut ladbar. [UI-Prüfbericht](tasks/ui-interaction-acceptance.md).

## Webanwendung lokal starten

Für echte Skripte zuerst die [Host-Worker-Installation](tasks/install-on-computer.md) mit CLI-Anmeldung und privater Konfiguration abschließen. Danach die Dienste mit `docker compose -f compose.yaml -f compose.host-worker.yaml up -d --build --wait db redis api web` starten und den angemeldeten Host-Worker ausführen. Auf Windows steht dafür `deploy/start-worker.ps1` bereit. Der Hintergrundstart ist für die aktuelle Windows-Sitzung geprüft; Login-/Neustartverhalten und weitere Betriebssysteme bleiben Aufgabe 35.

Voraussetzung für kontrollierte Entwicklungstests: Docker mit Linux-Containern und Docker Compose ([Installation](https://docs.docker.com/compose/install/)). Die folgende Standardvariante enthält einen Container-Worker ohne Pro-Anmeldung und prüft vor allem Fehler-/Dienstverhalten:

```powershell
docker compose up --build -d --wait
```

Falls `docker` auf Windows nicht im PATH liegt, den installierten Befehl direkt aufrufen: `& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' compose up --build -d --wait`.

Danach [http://localhost:4177](http://localhost:4177) öffnen. Eine Videoidee eingeben, `LOKAL` oder `CLOUD` wählen und „Projekt speichern“ drücken. Die Seite startet den Skriptauftrag und zeigt seinen Status, das gespeicherte Skript oder einen Fehler mit bewusster Wiederholung. „Skript bearbeiten“ öffnet Titel, Texte, Dauer und Bildvorgaben; Speichern erstellt eine neue Version. Ohne Antigravity-CLI, angemeldetes Pro-Konto und wirksam deaktivierte AI-Credit-Überziehung wird kein Modellaufruf gestartet. Eine LOKAL-MP4 kann erzeugt werden; die reguläre Endablage und Videowiedergabe in der App fehlen bis Schritt 18. [Healthcheck](http://localhost:4177/api/health/ready), [API-Dokumentation](http://localhost:4177/api/docs). Der Web-Port kann über `WEB_PORT` in der lokalen `.env` geändert werden.

```powershell
docker compose ps
docker compose down
```

`down` lässt die Datenbank- und Redis-Volumes bestehen. Vor dem produktiven Betrieb ein eigenes `POSTGRES_PASSWORD` in der ignorierten `.env` setzen. Das Passwort aus `.env.example` ist nur für lokale Entwicklung. Der Pexels-Key bleibt lokal in `.env` und wird noch keinem Container übergeben. Modal und Social-Media-Konten werden hier nicht verwendet.

Beim Start der API werden die versionierten Migrationen automatisch auf PostgreSQL angewandt. Für einen separaten Datenbanktest nach `docker compose up -d --wait db`:

```powershell
docker compose run --rm api python -m app.migrate up
docker compose run --rm api python -m unittest app.test_database -v
docker compose run --rm api python -m unittest app.test_api -v
```

Die Rückmigration `python -m app.migrate down` entfernt Daten oder Spalten der zurückgenommenen Migration und ist nur für eine **wegwerfbare Testdatenbank** vorgesehen.

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

Jeder Installationsrechner benötigt seine eigene [Antigravity-Anmeldung](https://antigravity.google/docs/cli/install/) unter dem Worker-Benutzer. AI-Credits in gültigen Settings deaktivieren; `modelProvider` darf nicht gesetzt sein. Die CLI entfernt Standardwerte beim Speichern: Laut [CLI-Referenz](https://antigravity.google/docs/cli/reference/) bedeutet ein fehlender `useG1Credits`-Schlüssel in einer gültigen Datei den Standard `false`. Fehlende/ungültige Dateien, aktive Credits und API-Provider blockieren die Anwendung. Die standalone Probe verwendet dieselben Laufzeitgrenzen wie der Worker. Keine Gemini API und kein API-Key als Ersatz; Anmeldungen werden nicht über GitHub übertragen. Die Windows-Live-Abnahme ist abgeschlossen, vollständige macOS-/Linux-Installation sowie Login-/Neustarttests sind noch offen.
