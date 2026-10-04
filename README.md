# Video-generating-Pipeline v2

Stand: Schritte **01–20** abgeschlossen; Schritt 20 ausschließlich statisch, ohne Generierung. Nächste Aufgabe **21 – Cloud-Szenen und Rücktransfer mit Testdaten anbinden**. LOKAL erzeugt und speichert Pexels-Videos mit deutscher Stimme/Untertiteln. Die Weboberfläche erlaubt Speicherwechsel, Videoabruf, Eingabe-/Ausgabevergleich, Szenensprünge und eine zweite Freigabe für genau die geprüfte aktuelle Datei. Gleiche Pexels-Clips und identische Dateien werden bei Auswahl/Wiederaufnahme ausgeschlossen. Schritt 19 ist technisch und vom Betreiber inhaltlich abgenommen. [Prüfbericht 19](tasks/step19-acceptance.md).

**Schritt 20:** [Versioniertes Wan-/Modal-Bundle](cloud/README.md) mit festem ComfyUI-Commit, vier Modellrevisionen/Prüfsummen, Linux-Abhängigkeiten mit Hashes und expliziter `A100-80GB`. Sieben Cloudtests, fünf gezielte Backendtests, zehn Projekttests, Web-Build und Offline-SDK-Konstruktion bestanden. Keine lokale Wan-Installation, kein Deployment/GPU-Aufruf/Gewichtsdownload. CLOUD erzeugt noch keine Videos; Live-Build, Qualität und Kosten bleiben nach den vorgeschriebenen Kostenprüfungen Schritt 24. [Prüfbericht 20](tasks/step20-acceptance.md).

**Schritt 17 abgeschlossen (04.10.2026):** Erstes echtes LOKAL-Video: sechs Szenen, 36 Sekunden, Untertitel und Sprecherstimme. Neue Videos enthalten nach Benutzerkorrektur keinen Themenkasten oder Szenenzähler. Vollständige Wiedergabe und Sollprofil geprüft. Die Oberfläche zeigt Dauer, Format, Codecs und Dateigröße. MP4 liegt zunächst als Zwischenartefakt unter `<MEDIA_ROOT>/encoding/<run-id>/master.mp4`; STORAGE/FINAL-Ablage und reguläres Playback sind inzwischen in 18 ergänzt. [Prüfbericht](tasks/step17-acceptance.md), [FFmpeg einrichten](tasks/install-on-computer.md#9-ffmpeg-schnitt-und-encoding-ab-schritt-17).

**Schritt 16 abgeschlossen (04.10.2026):** Echte Dienstprüfung und normaler LOKAL-Auftrag speichern sechs Stockclips, sechs Sprachdateien und sieben Grafiken. Die Oberfläche zeigt Grafikprofil und Untertitelzeiten auch nach Neuladen und bei 320 Pixeln. Encoding ist in Schritt 17 ergänzt; der Auftrag stoppt bis Schritt 18 bei STORAGE. [Prüfbericht](tasks/step16-acceptance.md), [Remotion installieren](graphics/README.md).

**Schritt 15:** Lokale deutsche Piper-Sprachsegmente mit gemessenen Szenendauern, sichtbarer Fehlerblockade und Wiederaufnahme. Migration 0004, normale Produktion und Browseranzeige geprüft; die langsamere zweite Hörprobe ist vom Betreiber bestätigt. MP4-Encoding ist in 17 ergänzt; Endablage und reguläre Wiedergabe folgen in 18. [Prüfbericht](tasks/step15-acceptance.md), [Piper installieren](tasks/install-on-computer.md#7-piper-sprachsynthese-ab-schritt-15).

**Entwicklung auf Windows, Installation auf einem unterstützten Rechner:** Einstieg über [STATE.md](STATE.md). Code und kontrollierte Tests laufen zunächst am aktuellen Windows-Entwicklungsrechner über dieses GitHub-Repository. Die Anwendung soll auf Windows, macOS oder Linux mit den benötigten Laufzeitwerkzeugen installierbar sein; Ubuntu ist ein möglicher Zielrechner. [Installationsanleitung](tasks/install-on-computer.md). [AGENTS.md](AGENTS.md) enthält die Projektregeln.

Die Anwendung nimmt eine Videoidee und den Modus `LOKAL` oder `CLOUD` in einer Weboberfläche entgegen. Ein Hintergrundauftrag erzeugt mit dem vorhandenen Google-AI-Pro-Konto über die offizielle Antigravity CLI ein Skript, ohne Gemini Developer API und ohne Codex zur Laufzeit. Die Skriptfreigabe übergibt einen versionsgebundenen Produktionsauftrag an den Host-Worker. Dieser führt die persistente Produktionskette aus und meldet noch fehlende Medienadapter ausdrücklich. Nach Pexels-Beschaffung, Sprachsynthese und Grafiken ist der Videoschnitt aus 17 geprüft; Auslieferung ist in 18 ergänzt; CLOUD-Beschaffung folgt ab 21. Social-Media-Veröffentlichungen folgen erst nach der Videoabnahme.

Der Prototyp unter [`tasks/`](tasks/) enthält den [Umsetzungsplan](tasks/plan.md), die [Aufgabenliste](tasks/todo.md), das [Skriptformat](tasks/script-probe.md) und vier geprüfte Beispielskripte. Zwei davon wurden automatisch mit Antigravity CLI erzeugt. Die [Pexels-Probe](tasks/pexels-probe.md) hat drei echte Suchtreffer und einen geprüften Download nachgewiesen. Der [Wan/Modal-Entwurf](tasks/wan-modal-design.md) beschreibt Workflow, Gewichte, Rücktransfer, unsichere Kostenwerte und die Sperre für einen kostenfreien Live-Test.

Der [API-Vertrag](tasks/api-contract.md) beschreibt die Endpunkte und Beispielpayloads. Die OpenAPI-Dokumentation liegt bei gestartetem Compose-Stack unter `/api/docs`. Bei Skriptfreigabe speichert die API einen `QUEUED`-Produktionslauf und übergibt ihn an RQ; der Status zeigt Freigabe, Schritte, Versuche und sichere Fehlerursache. Wiederzustellung nach Broker-/Worker-Ausfall erfolgt automatisch; bewusste Wiederaufnahme und Abbruch sind im Browser möglich. Geschützter Dateiabruf ist verfügbar; Publikationsaufträge folgen später.

Die Oberfläche zeigt Wartezeiten durch Ladebalken und unterscheidet Aktionen, deaktivierte Buttons und Statusanzeigen durch ihre Gestaltung. Der Editor bietet eine mitlaufende Speicherleiste, Tastaturfokus und Schutz ungespeicherter Änderungen beim Neuladen. Langsame oder fehlgeschlagene Anfragen bleiben erneut ladbar. [UI-Prüfbericht](tasks/ui-interaction-acceptance.md).

## Nutzung aus Sicht des Betreibers

1. **Du bestimmst das Thema:** Gib deine Videoidee und gewünschte Aussage ein. Die Beispielthemen sind Testdaten, keine Vorgabe und keine aus deinem Verhalten abgeleitete Vorliebe.
2. **Du prüfst den Vorschlag:** Die App schlägt Sprechertext und eine Bildfolge vor. Ändere Texte und Bildbeschreibungen vor der Freigabe. Der Projektname dient zur Verwaltung und wird nicht oben ins Video geschrieben.
3. **Du gibst die Produktion frei:** Im Modus LOKAL sucht die App echte Stockaufnahmen passend zu den Szenen, erzeugt die Stimme und zeigt denselben Sprechertext als Untertitel. Szenennummern werden nicht automatisch eingeblendet oder in Texte eingefügt; im freigegebenen Text enthaltene Wörter werden jedoch unverändert gesprochen.
4. **Du beurteilst das Ergebnis:** Verständlichkeit, Bildauswahl und Inhalt sind getrennte Prüfungen. Öffne „Speicher & Videos“, lege beim ersten Mal dein Passwort fest und sieh das fertige Video direkt im Projekt an. Dort lässt sich der Medienpfad jederzeit ändern, sobald keine Produktion läuft.

Das erste Video aus Schritt 17 war ausdrücklich eine **Funktionsprobe** mit einem gespeicherten, manuell präzisierten Testskript. Drei Motive kamen je zweimal vor. Seit Schritt 19 werden gleiche Pexels-IDs und identische Dateien bei neuen Produktionen/Freigaben ausgeschlossen; die korrigierte Probe mit sechs verschiedenen Aufnahmen wurde vom Betreiber akzeptiert. Die Stocksuche prüft Suchtreffer und Dateieigenschaften, versteht den Bildinhalt jedoch nicht automatisch. Nach Benutzerentscheidung vom 04.10.2026 enthalten neue Videos keinen Themenkasten, Szenenzähler oder Szenenfortschrittsstreifen. [Aktueller Prüfbericht](tasks/step19-acceptance.md).

## Webanwendung lokal starten

Für echte Skripte zuerst die [Host-Worker-Installation](tasks/install-on-computer.md) mit CLI-Anmeldung und privater Konfiguration abschließen. Danach die Dienste mit `docker compose -f compose.yaml -f compose.host-worker.yaml up -d --build --wait db redis api web` starten und den angemeldeten Host-Worker ausführen. Auf Windows steht dafür `deploy/start-worker.ps1` bereit. Der Hintergrundstart ist für die aktuelle Windows-Sitzung geprüft; Login-/Neustartverhalten und weitere Betriebssysteme bleiben Aufgabe 35.

Voraussetzung für kontrollierte Entwicklungstests: Docker mit Linux-Containern und Docker Compose ([Installation](https://docs.docker.com/compose/install/)). Die folgende Standardvariante enthält einen Container-Worker ohne Pro-Anmeldung und prüft vor allem Fehler-/Dienstverhalten:

```powershell
docker compose up --build -d --wait
```

Falls `docker` auf Windows nicht im PATH liegt, den installierten Befehl direkt aufrufen: `& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' compose up --build -d --wait`.

Danach [http://localhost:4177](http://localhost:4177) öffnen. Eine Videoidee eingeben, `LOKAL` oder `CLOUD` wählen und „Projekt speichern“ drücken. Die Seite startet den Skriptauftrag und zeigt seinen Status, das gespeicherte Skript oder einen Fehler mit bewusster Wiederholung. „Skript bearbeiten“ öffnet Titel, Texte, Dauer und Bildvorgaben; Speichern erstellt eine neue Version. Ohne Antigravity-CLI, angemeldetes Pro-Konto und wirksam deaktivierte AI-Credit-Überziehung wird kein Modellaufruf gestartet. Eine LOKAL-MP4 kann erzeugt, dauerhaft abgelegt und nach Entsperren in der App abgespielt werden. [Healthcheck](http://localhost:4177/api/health/ready), [API-Dokumentation](http://localhost:4177/api/docs). Der Web-Port kann über `WEB_PORT` in der lokalen `.env` geändert werden.

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

### Videoabnahme in der Oberfläche

Nach Produktion unter „Video prüfen“ die tatsächliche Idee mit Sprechertext/Bildvorgaben und dem Player vergleichen. Die Zeitbuttons springen zu einzelnen Szenen. Beide Prüfpunkte bestätigen und „Video freigeben“ wählen; der gespeicherte Status übersteht Neuladen. Bei falschem Inhalt eine neue Skriptversion bearbeiten und produzieren. Mehrfach verwendete Clips blockieren die Freigabe, passende Suchwörter ersetzen keine visuelle Prüfung. Plattformwahl und Veröffentlichung folgen später.
