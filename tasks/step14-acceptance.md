# Schritt 14 – Pexels-Szenenbeschaffung

Stand: **01.10.2026**. Schritt 14 abgenommen. 50 Backendtests, acht Projekttests, Web-Build sowie echte Pexels-/Browserprüfungen bestanden. Kein fertiges Video; nächste Aufgabe **15 – Piper-Sprachsynthese**.

## Ergebnis

`SCENES` beschafft im Modus `LOKAL` echte Pexels-MP4s zu jeder freigegebenen Szene. `CLOUD` erhält weiterhin `STAGE_UNAVAILABLE`; kein Pexels-/Wan-Fallback. Herkunft umfasst Szenenposition, Suchbegriff, Video-/Datei-ID, Pexels-Seite, Urheber/Profil, Lizenzlink, tatsächlich geprüfte Dauer/Auflösung/FPS. Relative Medienpfade und SHA-256 liegen im Quellenmanifest und den Artefakten. Der vollständig geprüfte Szenensatz wird atomar als PostgreSQL-Checkpoint gespeichert; API und Browser zeigen Quellen auch nach Neuladen.

Pro Szene höchstens vier Suchbegriffe, je zehn Suchtreffer und zwei geeignete Kandidaten pro Begriff. MP4 im Hochformat, mindestens 720 × 1280 und mindestens die freigegebene Szenendauer. Ein Titelindiz verlangt mindestens die Hälfte der relevanten Suchwörter im Pexels-Seitenslug. Das ist **keine automatische Bildanalyse**: komplexe Bildhandlungen können von Stocktreffern abweichen. Die Clipframes des Erfolgsbeispiels wurden deshalb angesehen. Ein Balkontreffer zeigt Blumen vor einem Geländer, keinen Blumenkasten; das Testskript wurde ausdrücklich als neue Version 2 auf tatsächlich sichtbare Motive präzisiert. Das ursprüngliche Pro-Skript wurde unverändert separat geprüft.

Downloads: ausschließlich HTTPS auf `videos.pexels.com`, keine Redirects und keine API-Authorization auf dem Medienhost. Grenze 150 MB/Clip, endliche HTTP-/ffprobe-Zeitlimits und bestehendes Stufen-/Gesamtzeitlimit. `.part` wird erst nach ffprobe/Hashprüfung atomar ersetzt. Unvollständige/beschädigte Dateien werden nicht als gültige Artefakte veröffentlicht. Einzelne geprüfte Szenen behalten private Checkpoints; Wiederaufnahme prüft Hash und Datei, bevor sie Such-/Downloadaufrufe überspringt. Ein abgeschlossenes `SCENES` wird bei Wiederaufnahme späterer Stufen unverändert übernommen.

Suchantworten, einschließlich leerer Treffer, liegen für 24 Stunden im Medienordnercache. HTTP 401/403 bei Suche zeigt ein Konfigurationsproblem, 429 ein erschöpftes Kontingent ohne automatischen Retry. Netzwerk-/5xx-Fehler benutzen höchstens die drei bereits festgelegten Stufenversuche. Keine zusätzlichen Keys, Quellenwechsel oder Quota-Umgehung. Providerfehlermeldungen und Keys werden nicht in Benutzerfehler übernommen.

## Prüfungen

- Zehn Adaptertests mit kontrolliertem HTTP und tatsächlich erzeugten MP4s/ffprobe: Manifest, Download, per-Szene-Wiederaufnahme, beschädigte Datei, fehlende Treffer, Cacheablauf, Key/ffprobe fehlen, Auth/429/5xx/Timeout, Größen-/Redirect-/CDN-/Dauer-/Auflösungs-/Relevanzgrenzen und Modustrennung.
- Drei neue Integrationsprüfungen mit eigener PostgreSQL-Schema-/Redis-Queue und echten Medien-Kindprozessen: sechs Quellen persistiert, Wiederaufnahme überspringt `SCENES`, kein finales Video, Kein-Treffer ohne Artefakt/Fallback, CLOUD ohne Pexels-Zugriff.
- Gesamtsuite: **50 Tests erfolgreich, 153,849 Sekunden**, mit tatsächlicher PostgreSQL-/Redis-/RQ-Integration einschließlich Worker-Kill/Neustart; acht `tasks`-Tests und `npm run build --prefix web` erfolgreich. Keine übersprungenen Tests.
- Echte kostenlose Pexels-Aufrufe im normalen Windows-Hostworker; keine neuen Antigravity-, Gemini-API- oder GPU-Aufrufe.
- API/Web neu gebaut und gesund, nativer Hostworker mit endgültigem Code neu gestartet. Anschließendes echtes `resume` behält `SCENES` bei Versuch 1 und alle sechs Clipgrößen/Änderungszeiten; ausschließlich `SPEECH` wird als Versuch 2 erneut geprüft und meldet den fehlenden Adapter. Quellen bleiben gespeichert, Health `ready`.
- Echter isolierter Chrome gegen die normale Anwendung: sechs Quellen/Urheberlinks, Fehleranzeige, Neuladen, 320 Pixel ohne horizontales Überlaufen, keine JavaScript-Ausnahme. Links sind unterstrichen; Farben an das dunkle Design angepasst. Screenshots und Frames im lokalen Codex-Visualisierungsordner; keine Medien im Git.
- Fehlertransport im separaten Medienprozess korrigiert: eigener Moduleinstiegspunkt verhindert unterschiedliche Exceptiontypen durch `python -m`. Datenbankzugriff vom HTTP-Modul getrennt, damit Medienprozesse nicht sämtliche API-Modelle laden. Produktions-Integrationstests leeren ausschließlich ihr eigenes Testschema pro Fall, damit ein fehlgeschlagener Testlauf nicht in die Queue des nächsten Falls gelangt. Der zunächst fehlgeschlagene Gesamt-Testlauf wurde vollständig erfolgreich wiederholt. Produktgrenzen und Abnahmekriterien unverändert.

## Live-Läufe

| Fall | Projekt / Lauf | Befund |
| --- | --- | --- |
| Positiv, visuell präzisierte Version 2, sechs Szenen / 36 Sekunden | `2c73b4e7-afd9-4346-ad24-f0d381a48635` / `cf022169-6a52-425f-9270-d3f143d022fb` | `SCENES COMPLETED`, sechs `SOURCE`-/`STOCK_VIDEO`-Artefakte; danach sichtbarer Stopp bei noch fehlendem `SPEECH` aus Schritt 15. |
| Absichtlich nicht auffindbare Suchbegriffe | `f12b5d02-3ac7-415d-a5ce-e4e2aabcbec6` / `3511f88a-ec2e-4bce-8e5c-7700f68b73a3` | `PEXELS_NO_MATCH`, Szene 1, Aufforderung zur Skriptänderung/neuen Freigabe, keine Artefakte. |
| Unveränderte sieben zuvor erzeugte/bearbeitete Pro-Szenen | `93cfd159-8e2b-4e06-910a-8e66c97478af` / `8748b9f8-0681-4ed6-a01c-ff6fc79fb1ef` | Fünf Clipdateien geprüft; Szene 6 „Insektenhotel“ ohne geeigneten Treffer. Kein vollständiger Szenencheckpoint, kein Video, keine Ersatzquelle. |

Erfolg nutzt drei geprüfte Pexels-Motive jeweils zweimal; Mehrfachnutzung ist explizit im Manifest sichtbar, keine Garantie unterschiedlicher Clips pro Szene:

| Szenen | Pexels-Video | Urheber | ffprobe |
| --- | --- | --- | --- |
| 1, 4 | [33296684](https://www.pexels.com/video/macro-shot-of-bees-on-lavender-flowers-33296684/) | [Hao Le](https://www.pexels.com/@haole) | 720 × 1280; 20,233333 s |
| 2, 5 | [18523335](https://www.pexels.com/video/a-balcony-with-flowers-and-a-view-of-the-city-18523335/) | [ROMAN MKRTCHIAN](https://www.pexels.com/@roman-mkrtchian-435441125) | 720 × 1280; 6,038333 s |
| 3, 6 | [6911644](https://www.pexels.com/video/person-putting-potting-soil-in-a-flowerpot-6911644/) | [Teona Swift](https://www.pexels.com/@teona-swift) | 720 × 1280; 10,760750 s |

## Installation und verbleibender Umfang

Der native Hostworker erhält `PEXELS_API_KEY`, optional `MEDIA_ROOT` und `FFPROBE_PATH` aus seiner privaten JSON-Konfiguration oder Umgebung. Für den Key wird alternativ die ignorierte Repository-`.env` gelesen. `ffprobe` muss auf dem Installationsrechner installiert sein; keine Zugangsdaten im Browser oder Git. Absolutes `MEDIA_ROOT`, sonst vorläufig `<Checkout>/.data/media`. Diese Quelldateien sind nach Worker-Neustart vorhanden und von Git ausgeschlossen. Umzug/Backup, Aufbewahrung, finaler Medienspeicher, API-Dateiabruf und Browserwiedergabe bleiben **Schritt 18**. Vollständige macOS-/Linux-Abnahme bleibt **35**.

**Nächster Schritt 15:** Piper-Sprachsynthese. Grafik, Encoding, finale Ablage, vollständige Video-/Browserabnahme und CLOUD-Beschaffung bleiben 16–24. Ein bestandener Schritt 14 ist noch kein fertiges Video.

Quellen: [Pexels API und Richtlinien](https://www.pexels.com/api/documentation/) (kostenfreier Key, Standardlimit 200/Stunde und 20.000/Monat, prominenter Pexels-Link und Urhebernennung), [Pexels-Lizenz](https://www.pexels.com/license/). Neue Video-API unter `/v1/videos/search`; kein Ausweichen auf den veralteten Pfad.
