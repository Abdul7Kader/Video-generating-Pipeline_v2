# Schritt 15 – Piper-Sprachsegmente

Stand: **1. Oktober 2026 – abgeschlossen**.

## Umsetzung

- Offline-Piper 1.8.0 auf der Hostworker-CPU, deutsche Standardstimme `de_DE-thorsten-high`, langsameres Tempo (`length_scale=1.15`) nach Betreiber-Hörprüfung. Modellrevision und SHA-256 im Installer festgelegt; Gewichte bleiben in ignorierten lokalen Ordnern. Das Tempo ist Teil der Segmentmetadaten und des Wiederaufnahme-Fingerabdrucks.
- Ein Segment pro Szene, gemessene WAV-Framezahl/Abtastrate und unabhängige ffprobe-Dauer; Stimme, Text, Hashes und Engineversion im Manifest. Keine geschätzten Zeitdaten.
- Validierung blockiert leere Texte, Stille, beschädigte/ungültige WAVs, fehlendes Modell und Synthesefehler vor dem nachfolgenden Renderjob. Fehlermeldungen enthalten keine internen Providerdetails.
- Atomare Dateien und pro Szene geprüfte Wiederaufnahme. Metadaten sind über Produktions-/Status-API abrufbar; die UI zeigt Szenendauern und Sprachsumme. Datei-/Videowiedergabe bleibt Schritt 18.
- Migration 0004 erlaubt `SPEECH_AUDIO` ausschließlich als Zwischenartefakt beider Modi; Quellen und finale Videos behalten ihre bisherigen Grenzen. Rückmigration verweigert vorhandene Audioartefakte, statt sie zu löschen. Workerstart verlangt Version 4.

## Nachgewiesen

- Echter Download des 113.895.201-Byte-Modells einschließlich Konfiguration/Modellkarte, SHA-256 geprüft. Echte Piper-Synthese mit deutscher Umlaut-Hörprobe auf Windows: **152.576 Frames / 22.050 Hz = 6,919546 Sekunden**; ffprobe bestätigt die Dauer innerhalb einer Sampleperiode.
- Beide vorhandenen echten Pro-Beispieltexte direkt mit Piper vertont (ursprüngliches Tempo 1.0): LOKAL sechs Segmente / **36,153 Sekunden**, CLOUD sechs Segmente / **32,322 Sekunden**. Jede Dauer erneut mit ffprobe verglichen; erneuter Adapteraufruf liefert dieselben überprüften Dateien und Metadaten.
- Fünf Audiotests bestehen: beide Modi/Dateiwiederaufnahme, gezielte Reparatur eines beschädigten Segments, leere Texte, fehlendes Modell/falsche Sprache sowie Stille/Synthesefehler ohne veröffentlichte Audioartefakte.
- 17 gezielte Backendtests für Audio/Pexels/Worker und zehn Projekttests einschließlich Installer bestehen. Web-Build (`npm run build --prefix web`) erfolgreich.
- Nach Docker-Update/Administrator-Neustart: **alle 58 Backendtests bestanden, keine übersprungen** (124,857 s). Migration up/down/up, Audio-/Modusgrenzen und verweigernder Rollback bei bestehenden Audiodaten tatsächlich mit PostgreSQL geprüft. Echte Redis-/RQ-/Piper-Prozesse für beide Modi, persistente API-Metadaten, Wiederaufnahme ohne erneute Synthese und blockierte Grafikstufe bei Leer-/Stille-/Synthesefehler bestanden.
- Im normalen Auftrag ein Windows-Kodierungsfehler gefunden und behoben: Medienprozess-Standardstreams explizit UTF-8. Ergänzte Regression mit deutschen Umlauten und erzwungener cp1252-Startumgebung: drei Speech-Integrationstests erneut bestanden (38,541 s).
- Normaler Hostworker mit geprüfter CLI/Kostensperre/Migration 4 gestartet. Neues Testprojekt `501f8d0a-1bf6-4c6e-9516-9b2812178003`, Lauf `203303af-c2cf-4ae5-b3ac-58834344111a`: sechs echte Pexels-Clips und sechs Piper-WAVs, insgesamt **17,218 Sekunden** Sprache beim korrigierten Tempo. Alle Audiodauern erneut mit ffprobe verglichen. Wiederaufnahme nach Kodierungskorrektur verwendet die bereits erzeugten Sprachdateien; Schrittzustände `COMPLETED / COMPLETED / FAILED / PENDING / PENDING`, Fehler `STAGE_UNAVAILABLE` ausschließlich für die noch offene Grafikstufe 16. Kein finales Artefakt. Healthcheck HTTP 200.
- Echte Chrome-Abnahme: sechs Sprachdauern/Stimme/Summe sichtbar, nach Neuladen erhalten, sechs Quellen weiterhin vorhanden, passive Audiodaten ohne falsche Buttons/Links. Bei 320 Pixeln keine horizontale Überbreite, keine Browser-Ausnahmen. Desktop-/Mobilansicht geprüft.

## Hörabnahme

- Bei der ersten Probe war der Anfang (ca. 1–1,5 Sekunden) laut Betreiber unverständlich, der Rest verständlich. Kodierung geprüft, Tempo reduziert und neue Probe bereitgestellt: `<Checkout>/.data/step15-listening-v2.wav`, **172.032 Frames / 22.050 Hz = 7,801905 Sekunden**. Der Betreiber hat die zweite Probe einschließlich des Anfangs angehört und bestätigt: **„Ja, jetzt verständlich“**. Die geforderte Hörprüfung ist damit erfüllt.

## Grenzen

Kein neues Gemini-/Antigravity-Modellgespräch, kein Modal-/GPU-Aufruf, keine bezahlte API. Direkte Audiosynthese ist für beide Modi neutral; die vollständige CLOUD-Szenenproduktion ist weiterhin Schritt 21/24. Grafik, Video-Encoding und Browserwiedergabe folgen in 16–18. Vollständige Linux-/macOS-Installation bleibt 35.

## Offizielle Quellen

[Piper Python-API](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md), [Paket 1.8.0](https://pypi.org/project/piper-tts/), [festgelegte Stimmenkarte](https://huggingface.co/rhasspy/piper-voices/blob/c10ece1aade47bb51c153c893d14e5bf8e5b7117/de/de_DE/thorsten/high/MODEL_CARD). Piper: GPL-3.0-or-later; Thorsten-Sprachdaten laut Karte: CC0.
