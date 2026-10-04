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
| `.venv\Scripts\python.exe -m pip install -r backend/requirements-worker.txt` | `.venv/bin/python -m pip install -r backend/requirements-worker.txt` |

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

## 5. Produktionskette ab Schritt 13

Die API muss die Migrationen einschließlich 0003 (`production_steps`/`production_attempts`) 0004 (`SPEECH_AUDIO`) und 0005 (`GRAPHICS_OVERLAY`) angewendet haben, bevor der aktualisierte Hostworker startet. `--check` prüft auch diese Voraussetzung. Der normale Start über `python -m app.worker` prüft die persistente Zustellliste beim Start und im Leerlauf ungefähr alle fünf Sekunden. PostgreSQL speichert den fachlichen Zustand und erfolgreiche Checkpoints; Redis/RQ transportiert die Aufträge. Der bisherige unveränderte `rq worker` im Container ist eine Entwicklungsvariante und stellt diese Hostworker-Wiederaufnahme nicht bereit.

Auf Windows läuft RQ weiterhin als `SimpleWorker`, doch jeder Produktionsschritt erhält nun einen eigenen begrenzten Medienprozess und eine Schrittsperre. Bei Elternprozess-Abbruch verhindert diese Sperre parallele Ausführung bis zum Ende oder eigenen Watchdog des Medienprozesses. Prozessbäume werden bei Timeout/Abbruch beendet. Auf Linux/macOS sind die entsprechenden Prozessgruppen implementiert; ihre vollständige Live-Abnahme bleibt Aufgabe 35.

Die Oberfläche zeigt fünf Schrittzustände, Versuche, Fehler, Ladebalken sowie Wiederaufnahme/Abbruch. Höchstens drei Versuche pro Schritt und drei Stunden Gesamtlaufzeit ab erstem Start; Wiederaufnahme erweitert diese Grenzen nicht. Fehlende Medienadapter führen zu einem sichtbaren Fehler und werden nicht automatisch erneut gestartet. Nach Pexels in Schritt 14 folgen weitere Medienadapter in 15–18/21. [Windows-Abnahme der Produktionskette](step13-acceptance.md).

## 6. Pexels-Clips ab Schritt 14

Auf dem **gewählten Installationsrechner** FFmpeg mit `ffprobe` installieren und im Worker-PATH bereitstellen. Alternativ `FFPROBE_PATH` als absoluten Pfad zur ausführbaren Datei in der privaten `worker.json` setzen. Der kostenlose Pexels-Key gehört dort als `PEXELS_API_KEY` hinein oder in die ignorierte Checkout-`.env`; nie in Git, Chat oder Web-Bundle. Diese optionalen Worker-Variablen können auch über die Umgebung gesetzt werden; vorhandene JSON-Werte haben Vorrang.

| Variable | Bedeutung |
| --- | --- |
| `PEXELS_API_KEY` | Kostenloser privater Pexels-Key. Fallback nur zur lokalen `.env`, nie zu einem anderen Mediendienst. |
| `MEDIA_ROOT` | Absoluter beschreibbarer Ordner. Standard: `<Checkout>/.data/media`, von Git ausgeschlossen. |
| `FFPROBE_PATH` | Absoluter Pfad zu ffprobe; sonst Suche im PATH. |

Hostworker nach Konfigurationsänderungen neu starten. Ohne Key/ffprobe meldet der Produktionslauf einen sichtbaren Einrichtungsfehler; die allgemeine `--check`-Prüfung bestätigt weiterhin ausschließlich CLI/Kostensperre/DB/Redis. Freigabe einer LOKAL-Version lädt pro Szene geeignete Hochformat-MP4s mit Mindestdauer und speichert Herkunft/Hash. Bei fehlendem Treffer Suchbegriffe/Bildbeschreibung bearbeiten und die neue Version bewusst freigeben. 24-Stunden-Suchcache berücksichtigt auch leere Treffer. Bereits geprüfte Clips werden beim Retry kontrolliert wiederverwendet. Die Beschaffung übergibt an die Sprachsynthese aus Schritt 15. Kein fertiges Video oder Dateistream in Schritt 14. [Abnahme](step14-acceptance.md).

## 7. Piper-Sprachsynthese ab Schritt 15

Im Checkout die Host-Abhängigkeiten aus `backend/requirements-worker.txt` installieren (Piper **1.8.0**); der API-Container benötigt kein Stimmenmodell. Danach die deutsche Standardstimme installieren:

| Windows PowerShell | macOS / Linux |
| --- | --- |
| `.venv\Scripts\python.exe deploy/install-piper.py` | `.venv/bin/python deploy/install-piper.py` |

Der Installer lädt `de_DE-thorsten-high.onnx`, dessen Konfiguration und die Modellkarte aus einer festgelegten Revision der offiziellen Piper-Stimmenablage. Er prüft SHA-256 vor dem atomaren Speichern; eine erneute Installation mit unveränderten Dateien benötigt keinen Download. Standardordner: `<Checkout>/.data/models`, etwa 114 MB. Gewichte und erzeugte Audiodateien gehören nicht in Git. Ein alternativer Ordner wird mit `--model-dir` eingerichtet; anschließend `PIPER_MODEL_PATH` als absoluten Pfad zur `.onnx` in der privaten `worker.json` oder Umgebung setzen. Die passende `.onnx.json` muss unmittelbar daneben liegen.

Piper verarbeitet deutsche Skripte (`de-DE`) vollständig lokal auf der **CPU**, ohne Konto, API oder GPU. Pro Szene entsteht eine Mono-PCM-WAV-Datei mit 22.050 Hz für die Standardstimme. WAV-Frames und ffprobe bestimmen die tatsächliche Dauer; Stimme, Modell-/Konfigurationshash und Engineversion bleiben in den Segmentdaten. Die Oberfläche zeigt nach erfolgreichem Sprachschritt die gemessenen Szenendauern und ihre Summe. Diese Summe ist noch keine fertige Videolänge; Bildanpassung und Zusammensetzung folgen in Schritt 17. Audio ist ein Zwischenartefakt für beide Modi und verändert deren visuelle Quellenregel nicht.

Leere Texte, stille/beschädigte Audiodateien, fehlendes Modell und Synthesefehler stoppen die Produktion sichtbar vor der Grafikstufe. Wiederaufnahme prüft vorhandene Audiosegmente; beschädigte Segmente werden einzeln erneut erzeugt, abgeschlossene Sprachschritte bleiben erhalten. Nach erfolgreicher Sprache rendert die Grafikstufe (16) Titel und Untertitel; Videoschnitt folgt in 17. Browserwiedergabe und persistente Medienauslieferung folgen in Schritt 18. Die allgemeine Workerprüfung führt keine Synthese aus; fehlende Medienvoraussetzungen erscheinen am betroffenen Produktionsschritt.

Das feste Sprechtempo ist gegenüber dem Modellstandard reduziert (`length_scale=1.15`) und Teil der Segmentmetadaten. Medienprozesse verwenden ausdrücklich UTF-8, auch auf Windows mit älterer Systemkodierung. Nach einem Update müssen API und Hostworker denselben Code-/Metadatenvertrag verwenden: Compose-API aktualisieren, anschließend den ruhenden Hostworker neu starten.

Quellen: [Piper Python-API](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md), [Piper-Paket und unterstützte Wheels](https://pypi.org/project/piper-tts/), [Stimmen-Modellkarte](https://huggingface.co/rhasspy/piper-voices/blob/c10ece1aade47bb51c153c893d14e5bf8e5b7117/de/de_DE/thorsten/high/MODEL_CARD). Piper steht unter **GPL-3.0-or-later**; die Thorsten-Sprachdaten sind laut Modellkarte **CC0**. Diese unterschiedlichen Lizenzen bei späterer Weitergabe berücksichtigen. Windows ist mit normaler Audioproduktion geprüft; vollständige macOS-/Linux-Installation bleibt Aufgabe 35. [Stand der Abnahme](step15-acceptance.md).

## 8. Remotion-Grafikvorlagen ab Schritt 16

Node.js 24 LTS auf dem Installationsrechner installieren und im Worker-PATH bereitstellen. Im Checkout `npm ci --prefix graphics` und `npm run install-browser --prefix graphics` ausführen. Der passende lokale Chrome Headless Shell und die npm-Abhängigkeiten liegen unter `graphics/`, sind ignoriert und werden während der Produktion nicht heruntergeladen. Noto Sans wird lokal gebündelt; keine Online-Schrift oder Google-Anmeldung für Remotion nötig.

Optional `REMOTION_NODE_PATH` oder `REMOTION_BROWSER_EXECUTABLE` als absolute Dateipfade in der privaten `worker.json` setzen und den Hostworker neu starten. Migration 0005 muss vorher durch die aktualisierte API angewendet sein. Ohne Node, Remotion oder Browser meldet die Grafikstufe einen sichtbaren Einrichtungs-/Renderfehler; die allgemeine Workerprüfung ersetzt keine Medienprobe. Linux-Systembibliotheken und vollständige macOS-/Linux-Installation bleiben in 35 offen.

Die Grafiken erhalten den Typ `INTERMEDIATE / GRAPHICS_OVERLAY` und liegen unter `<MEDIA_ROOT>/graphics/<run-id>/`. Titel, Untertitel und Szenenzähler verwenden 720 × 1280 bei 24 fps und sichere Ränder. Untertitelzeiten folgen den geprüften Sprachsegmenten; die Oberfläche zeigt nach Abschluss Anzahl, Format und Zeitbereiche. Noch keine finale MP4 oder Wiedergabe aus Schritt 16. [Rendervertrag und Lizenz](../graphics/README.md), [Prüfstand](step16-acceptance.md).

Windows-Abnahme am 04.10.2026: Migration 0005, normaler nativer Worker mit Node/ffprobe, echte Pexels-/Piper-/Remotion-Produktion und Browserstatus erfolgreich geprüft. Das ist keine vollständige Installationsabnahme für macOS/Linux oder den Login-/Neustartbetrieb; diese bleibt Aufgabe 35. [Prüfbericht](step16-acceptance.md).


## 9. FFmpeg-Schnitt und Encoding ab Schritt 17

FFmpeg und ffprobe aus einer geeigneten Distribution installieren; der FFmpeg-Build benötigt `libx264` und den AAC-Encoder sowie scale/crop/fps/overlay/aresample/apad/atrim/concat. Beide Programme müssen im PATH des Hostworkers liegen. Optional absolute Pfade `FFMPEG_PATH` und `FFPROBE_PATH` in der privaten `worker.json` setzen, danach den Worker neu starten. `ffmpeg -version` und `ffprobe -version` lokal prüfen. Die allgemeine Workerprüfung prüft die Dienste/CLI; eine tatsächliche Medienprobe ist zusätzlich nötig.

Die CPU-Pipeline schneidet und normalisiert jede Szene auf 720 × 1280 / 24 fps, legt die gespeicherten Remotion-PNGs zeitlich darüber und encodiert H.264 (`libx264`, CRF 20, preset veryfast, zwei Threads). Audio wird separat szenenweise auf 48 kHz gebracht, bis zum geplanten Szenenende mit Stille ergänzt und einmal kontinuierlich in AAC mono / 128 kbit/s encodiert. Ton aus Quellenclips wird nicht übernommen. Die endgültige MP4 erhält `faststart`; jedes Ergebnis wird mit ffprobe und vollständigem Decode geprüft.

Zwischenclips, Prüfsummencheckpoints, Fehlerlog und `master.mp4` liegen unter `<MEDIA_ROOT>/encoding/<run-id>/`. Die Stufe behält ihr 30-Minuten-Limit innerhalb der unverlängerten Drei-Stunden-Gesamtfrist; Abbruch/Timeout beendet den gesamten Medienprozessbaum. Lokale Medien, private Pfade und Logdateien bleiben ignoriert. Dauer/Format sind im Browser sichtbar; persistente Endablage und berechtigter Videoabruf bleiben Schritt 18. macOS-/Linux-Installation bleibt Aufgabe 35.

Referenzen: [FFmpeg-Filter](https://ffmpeg.org/ffmpeg-filters.html), [MP4/faststart und concat](https://ffmpeg.org/ffmpeg-formats.html), [ffprobe](https://ffmpeg.org/ffprobe.html). Lizenzen des gewählten FFmpeg-Builds einschließlich GPL/libx264 vor einer späteren Bündelung beachten; dieses Repository bündelt keine FFmpeg-Binärdatei.

Windows-Nachweis 04.10.2026: FFmpeg 9.0.2 mit libx264/AAC, normaler Hostworker, echte 36-Sekunden-Pexels-MP4 und vollständige lokale Browserwiedergabe geprüft. Weitere Betriebssysteme bleiben Aufgabe 35. [Abnahme Schritt 17](step17-acceptance.md).

## 10. Speicher und Videozugriff ab Schritt 18

Nach Aktualisierung der API (Migration 0006) den ruhenden nativen Hostworker neu starten. In „Speicher & Videos“ zunächst ein eigenes Passwort mit mindestens zehn Zeichen festlegen; danach Videos und Speichereinstellungen entsperren. Die HttpOnly-Sitzung gilt vier Stunden und übersteht ein Neuladen. Das Passwort gehört weder in den Chat noch in Git. Die erste Einrichtung setzt das Passwort dieser Installation; jede Installation hat ihren eigenen Zugang.

Der vollständige Medienpfad lässt sich in derselben Weboberfläche ändern. Beispiele: `D:\VideoPipeline\Medien`, `/home/benutzer/VideoPipeline/Medien` oder `/Users/benutzer/VideoPipeline/Medien`. Der Ordner gehört dem Worker-Benutzer, muss beschreibbar sein und genügend Platz für die vollständige Kopie bieten. Einen eigenen leeren Ordner wählen, kein ganzes Laufwerk, keinen fremden gefüllten Ordner und keine Verknüpfung. Während einer Produktion ist der Wechsel gesperrt.

„Speicherort übernehmen“ kopiert alle Medien und Manifeste und zeigt den geprüften Anteil als Ladebalken. Erst nach erfolgreicher SHA-256-Prüfung aller Dateien wird die private `worker.json` atomar aktualisiert. Der bisherige Ordner bleibt erhalten; abweichende Zieldateien werden nicht überschrieben. Nach einer Unterbrechung wird der gespeicherte Auftrag automatisch wieder zugestellt, höchstens drei Versuche. Fehlgeschlagene Änderungen lassen den aktuellen Speicher aktiv.

Neue Mediendateien liegen unter `<MEDIA_ROOT>/projects/<project-id>/versions/<version>/runs/<run-id>/<stage>/`. STORAGE schreibt die geprüfte `master.mp4` und `manifest.json` und veröffentlicht das FINAL-Artefakt. Vorhandene ältere relative Pfade bleiben lesbar und werden beim Speicherwechsel unverändert mitkopiert. Modellgewichte liegen weiterhin separat im Modellordner.

Der native Worker liefert angeforderte Medienblöcke über den bestehenden Redis-Dienst an die API. Keine neue öffentliche Host-Schnittstelle und keine wechselnde Laufwerksfreigabe für den Container nötig. Der Hostworker muss auch zum Abspielen laufen. Redis-Zugriff bleibt lokal wie in `compose.host-worker.yaml`; allgemeine Härtung und Backup bleiben 32/35. Der Browser nutzt ausschließlich die Artefakt-ID und eine Sitzung, keine freigegebenen Hostpfade oder URL-Tokens. Vollständige macOS-/Linux-Installation bleibt 35. [Prüfstand 18](step18-acceptance.md).

## 11. Video vergleichen und freigeben ab Schritt 19

Nach fertiger Produktion zeigt „Video prüfen“ die ursprüngliche Eingabe und den Player. Medienzugang unter „Speicher & Videos“ entsperren. „Sprechertext und Bildvorgaben vergleichen“ öffnen; die Zeitbuttons springen zur tatsächlichen Szene. Stimme, Untertitel, Bilder und Wiederholungen prüfen, beide Prüfpunkte bestätigen und „Video freigeben“ wählen. Die Bestätigung bleibt nach Neuladen gespeichert und gilt nur für diese Datei/versionierte Produktion.

Bei falschen Motiven „Skript für neue Version bearbeiten“ verwenden und die neue Version erneut freigeben. Passende Suchwörter garantieren keine passende Aufnahme. Mehrfach verwendete Pexels-IDs/identische Dateien blockieren neue Freigaben; alte Videos werden dabei nicht geändert. Die Videofreigabe startet in diesem Entwicklungsstand keine Veröffentlichung. [Prüfstand 19](step19-acceptance.md).

## 12. CLOUD-Vorbereitung ab Schritt 20

Das [versionierte Cloud-Bundle](../cloud/README.md) lässt sich auf dem Entwicklungs-/Installationsrechner mit `python -m cloud.validate` und `python -m unittest cloud.test_workflow -v` offline prüfen. Dafür sind weder Modal-Anmeldung noch lokale Wan-/ComfyUI-/PyTorch-Installation nötig. Linux-/CUDA-Abhängigkeiten im Verzeichnis `cloud/` beschreiben nur das spätere Remote-Image; sie gehören nicht in die normale Hostworker-Umgebung oder Compose-Installation.

Noch kein Modal-Deployment oder echtes CLOUD-Video verfügbar. Schritt 21 bindet kontrollierte Testdateien an, 22 prüft Auftragsgrenzen und Kosten, 23 den Browserablauf. Erst 24 startet nach nachgewiesenen Gratis-Credits und wirksamen 0 USD Nettokosten einen echten Remote-Build/Modelltransfer/GPU-Test. Diese Vorbereitung benötigt keinen eingeschalteten Ubuntu-Rechner. [Prüfstand 20](step20-acceptance.md).
