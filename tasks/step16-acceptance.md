# Schritt 16 – Remotion-Grafikvorlagen

Stand: **04.10.2026 – abgeschlossen.** Die am 01.10.2026 angeordnete Pause ist aufgehoben; die damals offenen Dienst- und Browserprüfungen wurden im neuen Chat erfolgreich nachgeholt. Die vorhandene Implementierung (`271c323`) benötigte keine funktionalen Änderungen. Nächste Aufgabe: **17 – FFmpeg-Pipeline**, noch nicht begonnen. [Projektstatus](../STATE.md#pause-und-genauer-wiedereinstieg).

## Ergebnis

- Remotion 4.0.532 rendert lokal einen Titel und einen Untertitel je Szene als transparente PNG-Ebenen, einschließlich Szenenzähler und Fortschrittsgrafik.
- Fester Rahmen: 720 × 1280, 24 fps, lokale Noto-Sans-Schrift, sichere Ränder 64/112/96/240 Pixel. Gemessene Textgrenzen verhindern Abschneiden und gegenseitige Überdeckung. Titel bis vier Sekunden, Untertitel szenengenau aus tatsächlicher Piper-Dauer; geplante Haltezeiten bleiben erhalten.
- Typisiertes Manifest, Hash-/WAV-/PNG-Prüfungen, atomare Speicherung und Cache-Wiederaufnahme. `GRAPHICS_OVERLAY` ist ein neutrales `INTERMEDIATE`-Artefakt. Visuelle Quellen bleiben in LOKAL ausschließlich `STOCK_VIDEO`, in CLOUD ausschließlich `AI_GENERATED_VIDEO`.
- Migration 0005 ergänzt den Medientyp mit Modus-/Artefaktprüfung und verweigert verlustbehaftetes Rollback. API und UI zeigen Grafikprofil, Anzahl und Untertitelzeiten.
- Beide Kriterien aus [todo.md](todo.md) erfüllt. Noch keine finale MP4: Encoding und Auslieferung folgen in 17/18.

## Prüfungen am 04.10.2026

| Prüfung | Ergebnis |
| --- | --- |
| `npm run build --prefix web` | Bestanden; Web-Container ebenfalls neu gebaut. |
| `.venv/Scripts/python.exe -m unittest discover -s tasks -p 'test_*.py' -v` | 10 bestanden, 0 übersprungen. |
| Vollständige Backend-Suite `backend/app/test_*.py` mit privaten lokalen Dienst-URLs | 65 bestanden, 0 übersprungen; 354,237 Sekunden. |
| Gezielte Suite `app.test_graphics_production` | 3 bestanden; 114,812 Sekunden. |
| Compose-Stack mit `compose.host-worker.yaml` | PostgreSQL, Redis, API, Web gesund; Migration 0005 angewendet. |
| `python -m app.worker --check` und `/api/health/ready` | Native Worker-Konfiguration geprüft; Datenbank, Redis und normaler Hostworker bereit. Kein Modellaufruf für diese Prüfung. |

Die Backend-Suite prüft unter anderem tatsächlichen Worker-Kill/Neustart, Abbruch, Zeitlimits, Wiederaufnahme, Quellenregeln und die Grafikstufe. Dienst-URLs und private Konfiguration wurden nur lokal eingelesen und nicht ausgegeben oder versioniert.

### Echte Grafik-Integration beider Modi

Die drei Tests aus `backend/app/test_graphics_production.py` verwenden echte PostgreSQL-, Redis-/RQ-, Piper- und Remotion-Verarbeitung. Nur die visuellen Szenenquellen dieser isolierten Tests sind kontrollierte Fixtures; das ist kein echter Wan-/Modal-Nachweis.

- Beide Modi erzeugen sieben geprüfte Grafikartefakte aus gespeichertem Titel, Szenentext und tatsächlich erzeugter Sprache. Timing und Manifest stimmen überein; API, Dateien und Cache geprüft.
- Cache funktioniert ohne erneuten Node-Aufruf. Wiederaufnahme überspringt abgeschlossene Stufen ohne doppelte Datenbankartefakte oder Dateien.
- Veränderte Sprachtexte blockieren GRAPHICS und die Weitergabe an ENCODING.
- Migration 0005: up/down/up, Modus-/Medientypregeln und Verweigerung eines verlustbehafteten Rollbacks mit vorhandenen Grafikartefakten bestanden.

### Normaler LOKAL-Produktionsauftrag

Projekt `501f8d0a-1bf6-4c6e-9516-9b2812178003`, freigegebene Skriptversion **2**, Lauf **`1068c048-24a5-47a3-b05e-e24a93659cab`**. Der frühere Lauf war abgelaufen; seine Drei-Stunden-Frist wurde nicht verlängert. Das bereits gespeicherte Skript wurde unverändert als neue Version gespeichert und über die normale API freigegeben. Keine neue Pro-Skriptgenerierung.

Der normale native `pipeline-worker` durchlief echte Pexels-Beschaffung, Piper-Synthese und Remotion-Rendering:

| Stufe | Ergebnis |
| --- | --- |
| SCENES | COMPLETED, Versuch 1; 6 echte Pexels-Clips als SOURCE / STOCK_VIDEO. |
| SPEECH | COMPLETED, Versuch 1; 6 WAVs als INTERMEDIATE / SPEECH_AUDIO, zusammen 17,485 Sekunden. |
| GRAPHICS | COMPLETED, Versuch 1; 1 Titel + 6 Untertitel als INTERMEDIATE / GRAPHICS_OVERLAY. |
| ENCODING | FAILED, Versuch 1, erwartetes `STAGE_UNAVAILABLE`: Adapter aus Schritt 17 fehlt. |
| STORAGE | PENDING; keine FINAL-Datei und kein fertiges Video behauptet. |

Alle **19 gespeicherten Dateien** stimmen per SHA-256 mit ihren Datenbankartefakten überein. Die sieben PNGs sind einschließlich CRC und ffprobe-Profil geprüft. Das gespeicherte Grafikmanifest entspricht dem aus Skript und geprüften Sprachdaten neu berechneten Plan: **36 Sekunden / 864 Frames bei 24 fps**, 720 × 1280. Die tatsächliche Sprachdauer wird auf volle Frames aufgerundet; übrige geplante Szenenzeit bleibt als Haltezeit erhalten.

| Untertitel | Zeitraum in Sekunden, UI-Rundung |
| --- | --- |
| 1 | 0,00–2,58 |
| 2 | 6,00–9,29 |
| 3 | 12,00–14,96 |
| 4 | 18,00–20,50 |
| 5 | 24,00–27,29 |
| 6 | 30,00–33,00 |

Titel-PNG und erste Untertitelgrafik des echten Auftrags visuell geprüft: vollständiger Titel, „Szene 1: Bestäuber an violetten Blüten.“ lesbar, sichere Ränder, keine Überdeckung oder abgeschnittenen Zeichen. Dateien liegen lokal unter `.data/media/graphics/<run-id>/` und bleiben ignoriert. Maschinenbeleg: `.data/step16-live-verified.json`.

### Browserabnahme

Echte Chrome-Probe gegen die normale Anwendung unter `http://127.0.0.1:4177/`, mit eigenem isoliertem Testprofil:

- Anzeige „1 Titel · 6 Untertitel · 720 × 1280 · 24 fps“ und alle sechs korrekten Zeitbereiche; sechs Quellen- und sechs Sprachzeilen, drei abgeschlossene Stufen.
- Grafikstatus bleibt nach Neuladen erhalten. Er ist eine passive Anzeige ohne Buttons oder Links; bestehende Bediengestaltung bleibt erhalten.
- Bei **320 Pixeln** stimmen Dokument- und Fensterbreite überein, kein horizontaler Überlauf. Zeitbereiche lesbar und getrennt angeordnet.
- **0 Laufzeitfehler** in der Browserprüfung. Bei tatsächlich verzögerter Netzwerkantwort (1.200 ms Testlatenz) erscheint ein Ladebalken; danach wird der gespeicherte Status wieder angezeigt.
- Lokaler Maschinenbeleg: `.data/step16-browser-result.json`. Screenshots: `step16-desktop.png`, `step16-mobile.png`, `step16-mobile-graphics.png` unter dem lokalen Codex-Visualisierungsordner `2026/10/04/01a106ed-85e3-74d1-83fe-727091e5bfb0`. Diese Dateien werden nicht ins Repository übernommen.

## Bereits bestandene Text-/Rendererprüfungen

Diese Sichtprüfungen stammen vom 01.10.2026; der Renderer ist seitdem unverändert. Die zugehörigen automatisierten Grafiktests bestehen erneut in der vollständigen Suite vom 04.10.2026.

- Drei Timingtests: beide Modi, Audioframes/Haltezeiten, geänderte/fehlende/doppelte Sprachmetadaten, zu lange Gesamtdauer.
- Vier Grafiktests mit tatsächlichem lokalem Renderer: sieben PNGs je Lauf, Cache ohne Node-Aufruf, beschädigte PNG erkannt und neu gerendert, beschädigtes Audio blockiert. Die Audiodaten dieser isolierten Rendererprüfung sind kontrollierte WAVs; echte Piper-Produktion ist zusätzlich oben nachgewiesen.
- PNG-Proben mit langem Titel, kurzer Zeile, 400 Zeichen deutschem Fließtext und `ÄÖÜ äöü ß <Text> & "Anführungszeichen"` gerendert. ffprobe bestätigt 720 × 1280/RGBA; Sichtprüfung zeigt vollständige Zeichen, Zeilenumbruch und sichere Ränder. Titel: 32 px, Rechteck (64,96)–(608,374.94); lange Untertitel: 28 px, (64,449.61)–(608,1040). Unlesbarer Extremfall aus 400 ungetrennten `W` wird ausdrücklich abgewiesen.
- npm-Abhängigkeiten sind per Lockfile fixiert. Browser, Medien und Modelle bleiben ignoriert.

## Historische Pause und verbleibender Umfang

Am 01.10.2026 blockierte der Docker-Startfehler an `docker-secrets-engine/engine.sock` die Dienstabnahme. Damals bestanden 32 Backendtests; 33 Diensttests wurden übersprungen. Auf Betreiberwunsch wurde dokumentiert und pausiert, ohne Containerdaten zu löschen oder Kriterien zu senken. **Dieser alte Prüfstand ist durch die vollständige Abnahme vom 04.10.2026 ersetzt.** Docker 29.8.1 und die Projektcontainer laufen jetzt wieder.

Offen bleiben **17: FFmpeg-Schnitt/Encoding**, **18: persistente Ablage/Browserwiedergabe** und **35: vollständige Installation einschließlich macOS/Linux sowie Login-/Neustartbetrieb**. Kein Modal-/bezahlter API-Aufruf für diese Abnahme. Die CLOUD-Quellenintegration und echte Wan-Generierung bleiben ihre eigenen späteren Aufgaben mit Kostentor.

## Implementierungsentscheidung

Statische, wiederverwendbare Remotion-Ebenen mit framegenauem Manifest halten Renderzeit und Speicher gering. Schritt 17 legt sie anhand derselben Zeitdaten über die geprüften Szenen. Eine zusätzliche große Zwischenvideodatei oder PNG-Bildfolge pro Frame ist für die festgelegten statischen Texte nicht nötig. [Installation, Rendervertrag und Lizenz](../graphics/README.md).
