# Schritt 17 – FFmpeg-Pipeline

Stand: **04.10.2026 – abgeschlossen.** Beide Kriterien aus [todo.md](todo.md) erfüllt. Nächste Aufgabe: **18 – portabler persistenter Medienspeicher und berechtigter Videoabruf**, noch nicht begonnen. [Projektstatus](../STATE.md#pause-und-genauer-wiedereinstieg).

## Was der Schritt tut

Nach Skriptfreigabe verarbeitet der Hostworker die geprüften Szenen, Piper-Sprachdateien und Remotion-Grafiken. FFmpeg schneidet/normalisiert jede Szene auf 720 × 1280 / 24 fps und legt Titel/Untertitel anhand des gespeicherten Frameplans darüber. Sprechertext beginnt am Szenenanfang; geplante Restzeit enthält Stille. Ton aus Pexels-/Wan-Quellen wird nicht übernommen. Ein kontinuierlicher AAC-Encode verhindert zusätzliche Encoder-Vorlaufzeiten an Szenenwechseln.

Ergebnis ist eine technisch geprüfte **MP4 mit H.264 (yuv420p, quadratische Pixel) und AAC mono / 48 kHz / 128 kbit/s**. CPU-Encode: libx264, CRF 20, preset veryfast, zwei Threads. MP4-faststart ermöglicht späteren progressiven Abruf. Die UI zeigt Dauer, Auflösung, Bildrate, Codecs und Dateigröße als passive Anzeige; bestehende Ladebalken und Bediengestaltung bleiben erhalten.

## Verträge und Wiederaufnahme

- Encoding verwendet exakt den erneut aus freigegebenem Skript und SPEECH aufgebauten GRAPHICS-Plan. Keine Text-/Zeitänderung während des Schnitts; kein stiller Quellenwechsel.
- LOKAL akzeptiert ausschließlich SOURCE / STOCK_VIDEO; CLOUD ausschließlich SOURCE / AI_GENERATED_VIDEO. Fehlende, doppelte oder falsche Artefaktschlüssel/-arten werden abgewiesen.
- Alle Dateien müssen unter dem aufgelösten MEDIA_ROOT liegen und ihren SHA-256-Werten entsprechen. WAV-/PNG-/Clipprüfung vor jedem Rendern. Quelle muss mindestens die gesamte geplante bzw. sprachbedingt verlängerte Szenendauer liefern; eine zu kurze Quelle stoppt den Schritt. Keine Schleife, Verlangsamung oder künstliche Verlängerung der Quelle.
- Szenenclips und Master werden über atomare `.part.mp4`-Dateien gespeichert. Fingerprint, Prüfsummen und vollständiger Decode sichern Szenencheckpoints und Mastercache. Beschädigte Ausgabe wird neu zusammengesetzt, geprüfte Szenenclips bleiben erhalten.
- Prozessstart ohne Shell; FFmpeg erhält nur eine begrenzte Laufzeitumgebung ohne API-/Datenbankgeheimnisse. Neue Video-/Concat-Eingänge erlauben nur lokale file/pipe-Protokolle. Unveränderte 30-Minuten-Stufengrenze innerhalb der Drei-Stunden-Auftragsfrist; vorhandener Abbruch-/Timeoutprozess beendet den gesamten Prozessbaum.
- `EncodingManifest` ergänzt StageResult, Produktions-API und Projektstatus. Profil/Dauer/Bildzahl werden auch an der Subprozessgrenze geprüft. Keine Datenbankmigration nötig: INTERMEDIATE / FINAL_VIDEO war bereits zulässig.

## Prüfnachweise

| Prüfung | Ergebnis |
| --- | --- |
| `npm run build --prefix web` | Bestanden; TypeScript und Vite. Aktualisierte Compose-API/Web ebenfalls gebaut und gesund. |
| Projektsuite `unittest discover -s tasks -p 'test_*.py' -v` | 10 bestanden, 0 übersprungen. |
| Vollständige Backend-Suite mit echten PostgreSQL-/Redis-Diensten | 72 bestanden, 0 übersprungen; 445,821 Sekunden. |
| Gezielte `app.test_encoding` | 5 bestanden; nach abschließender Einschränkung der Prozessumgebung erneut bestanden (61,567 Sekunden unter paralleler Last). |
| `app.test_encoding_production` | 2 bestanden; 98,888 Sekunden. Echte PostgreSQL-/Redis-/RQ-/Piper-/Remotion-/FFmpeg-Verarbeitung; außerdem in vollständiger Suite bestanden. |
| Normale LOKAL-Produktion | ENCODING abgeschlossen, echte MP4; alle 20 gespeicherten Auftragsdateien per SHA-256 geprüft. |
| App-Browserprüfung | Profilanzeige, Neuladen, 320 Pixel, Ladebalken bei verzögerter Antwort, 0 Laufzeitfehler. |
| Lokale vollständige Videowiedergabe | 36 Sekunden bis `ended`, 864 Videoframes, 720 × 1280, keine Medien-/Laufzeitfehler; alle sechs Szenen visuell geprüft. |

Die fünf Encodingtests prüfen Quellen-/Freigabeverträge, fehlende/duplizierte/veränderte Zeitdaten, Pfad-/Hashschutz, beschädigte WAVs/PNGs und zu kurze Clips. Tatsächliche farbige Video-/Ton-/Overlayfixtures werden zu MP4 encodiert. Pixelproben bestätigen Captionende nach Sprachdauer und Titelende bei Frame 96. Decodierte Audioproben bestätigen Sprachsignal und Stille in Haltezeiten; Quellenclipton wird nicht übernommen. Cacheprüfung und Reparatur einer beschädigten Masterdatei erhalten die Szenencheckpoints. Dateipfade mit Leerzeichen und Umlaut sind enthalten.

Die zwei Diensttests verwenden **kontrollierte Szenenclips**, aber echtes Piper, Remotion und FFmpeg, für beide Modi. API-/Datenbankartefakt, Wiederaufnahme ohne neue Datei oder Artefaktdublette und sichtbare Blockade bei zu kurzer Quelle bestanden. Die isolierte Grafik-Suite deaktiviert ENCODING ausdrücklich, damit ihre Szenenfixtures keine scheinbaren Produktionsmedien werden. **Kein echter Wan-/Modal-Nachweis aus diesen Tests.**

Die vollständige Backend-Suite prüft weiterhin Worker-Kill/Neustart, Abbruch, Fristen, Versuchsgrenzen, Modusregeln sowie frühere Skript-/Sprach-/Grafikverträge. Keine neuen Pro-/Modal-/bezahlten API-Aufrufe für Schritt 17.

## Erstes echtes LOKAL-Video

Projekt `501f8d0a-1bf6-4c6e-9516-9b2812178003`, freigegebene Skriptversion **2**, Lauf **`1068c048-24a5-47a3-b05e-e24a93659cab`**. Derselbe Auftrag aus Schritt 16 wurde über die normale Resume-API innerhalb seiner unveränderten Frist weiterverarbeitet. Keine erneute Skriptsynthese und keine erneute Beschaffung bereits abgeschlossener Stufen.

- SCENES, SPEECH, GRAPHICS abgeschlossen (je Versuch 1); ENCODING abgeschlossen (Versuch 2, nach dem früheren fehlenden Adapter). STORAGE scheitert erwartungsgemäß mit `STAGE_UNAVAILABLE` (Versuch 1).
- Sechs echte Pexels-Stockclips, sechs Piper-WAVs, sieben Remotion-PNGs und eine MP4: **20 Artefakte**, alle Hashwerte mit Dateien identisch. Drei bereits visuell geprüfte Motive werden entsprechend dem gespeicherten Abnahmeskript zweimal verwendet; keine neue redaktionelle Auswahl durch Encoding.
- MP4: **36,000 Sekunden / 864 Frames / 720 × 1280 / 24 fps / H.264 / AAC mono 48 kHz**, **13.058.280 Bytes (12,5 MiB)**. ffprobe und vollständiger Decode erfolgreich.
- SHA-256: `fc6db599fcc7249446e6aa26f390b45c7362adf9779d5cd4399e92eb9f41c31c`.
- Datei: `<MEDIA_ROOT>/encoding/1068c048-24a5-47a3-b05e-e24a93659cab/master.mp4` (hier lokal `.data/media/encoding/...`). Maschinenbeleg: `.data/step17-live-verified.json`.

## Sichtbares Ergebnis / Browser

Die App unter `http://127.0.0.1:4177/` zeigt **„MP4 zusammengesetzt und geprüft“**, **„36 s · 720 × 1280 · 24 fps“** und **„H.264 · AAC · 12,5 MB“**. Die Anzeige bleibt nach Neuladen erhalten, enthält keine falschen klickbaren Elemente und passt bei 320 Pixeln ohne horizontalen Überlauf. Vier Produktionsstufen sind sichtbar abgeschlossen. Fehler der noch fehlenden STORAGE-Stufe bleibt transparent. `.data/step17-browser-result.json` dokumentiert 0 Laufzeitfehler und erfolgreichen Ladebalkennachweis mit 1.200 ms Testlatenz.

Für die MP4-Abnahme wurde eine **separate, lokale Entwicklungsvorschau** unter `http://127.0.0.1:4178/` bereitgestellt, ausschließlich für diese Datei, mit Range-Unterstützung und Video-Steuerelementen. Der ignorierte Vorschauprozess beendet sich nach einer Stunde; die MP4 bleibt erhalten. Dies ist kein Produktionsadapter oder Nachweis für Schritt 18.

Das Video wurde im isolierten Chrome vollständig abgespielt (für die automatisierte Sichtprüfung stumm). Alle sechs Szenen bei etwa 0,84 / 6,74 / 12,70 / 18,79 / 24,87 / 30,77 Sekunden visuell betrachtet: lesbare Texte mit Umlauten, Titel zu Beginn, geordnete Szenenzähler, sichere Ränder, keine Überdeckung/abgeschnittenen Zeilen. Wiedergabe endet fehlerfrei bei Sekunde 36 mit 864 Frames. `.data/step17-playback-result.json` speichert den Beleg. Audiokorrektheit wurde technisch geprüft; die bestehende Piper-Hörabnahme aus Schritt 15 bleibt gültig. Zusätzlich wurde der Betreiber um Rückmeldung zum neuen Video gebeten; ohne Antwort wird keine neue persönliche Hörfreigabe behauptet.

Lokale Screenshots `step17-desktop.png`, `step17-mobile-encoding.png`, `step17-video-scene-1.png` bis `step17-video-scene-6.png` liegen im Codex-Visualisierungsordner `2026/10/04/01a106ed-85e3-74d1-83fe-727091e5bfb0`. Browserprofile, Medien, Logdateien und Zugangsdaten sind ignoriert und werden nicht committed.

## Noch offen

**18:** Projekt-/Versionspfade, persistente FINAL-Ablage, berechtigter Medienabruf mit Pfadschutz, Playback in der regulären Oberfläche und Containerneustartprobe. MP4 aus 17 ist noch `INTERMEDIATE / FINAL_VIDEO`; `content_available=false`, regulärer Abruf weiter 501, Gesamtauftrag nicht COMPLETED. **35:** vollständige plattformübergreifende Installation einschließlich macOS/Linux sowie Login-/Neustartbetrieb. CLOUD-Szenenbeschaffung und echte Wan-Generierung folgen später mit dem unveränderten Kostentor.

## Quellen / Installation

[FFmpeg-Filter](https://ffmpeg.org/ffmpeg-filters.html), [Concat/MP4-faststart](https://ffmpeg.org/ffmpeg-formats.html), [ffprobe](https://ffmpeg.org/ffprobe.html). Die Umsetzung folgt den vorhandenen Frameverträgen und diesen offiziellen Werkzeugverträgen; FFmpeg 9.0.2 ist der tatsächlich geprüfte Windows-Build. [API-Vertrag](api-contract.md#encodingmanifest-ab-schritt-17), [Installation und Lizenzen](install-on-computer.md#9-ffmpeg-schnitt-und-encoding-ab-schritt-17).
