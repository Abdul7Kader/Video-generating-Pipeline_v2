# Aufgabe 04 – Pexels-Probe

Stand: 26. September 2026. **Live-Probe abgeschlossen:** Drei echte Videosuchen lieferten Dateien mit Quell-ID, Dauer und Auflösung. Ein Clip wurde heruntergeladen, mit `ffprobe` geprüft und visuell gesichtet. Der API-Key liegt nur in der ignorierten lokalen `.env`.

## Verifizierte Anbieterregeln

- Die [Pexels Video API](https://www.pexels.com/api/documentation/) ist kostenlos. Ein Pexels-Konto kann einen API-Key sofort beantragen. Der Key gehört in den serverseitigen `Authorization`-Header, nicht in Browsercode oder Git. Die Videosuche läuft über `GET https://api.pexels.com/v1/videos/search`; der ältere Pfad ohne `/v1/` soll entfallen.
- Standardlimits sind [200 Anfragen pro Stunde und 20.000 pro Monat](https://www.pexels.com/api/documentation/). Erfolgreiche Antworten liefern `X-Ratelimit-Limit`, `X-Ratelimit-Remaining` und `X-Ratelimit-Reset`. Bei HTTP 429 muss die Anwendung warten statt weitere Anfragen zu senden. Pexels empfiehlt, Suchergebnisse zu [cachen](https://help.pexels.com/hc/en-us/articles/900006470063-What-steps-can-I-take-to-avoid-hitting-the-rate-limit).
- Die Antwort enthält Video-ID, Quellseite, Urheberprofil, Dauer und `video_files` mit Dateivarianten, Auflösung, Bildrate, Format und Downloadlink. Diese Daten werden im Herkunftsbericht gespeichert; signierte Downloadlinks werden dort nicht dauerhaft abgelegt. [API-Felder](https://www.pexels.com/api/documentation/)
- Die [Pexels-Lizenz](https://www.pexels.com/license/) erlaubt kostenlose Nutzung und Bearbeitung, auch kommerziell und in Social-Media-Videos. Eine Urhebernennung ist nach der allgemeinen Lizenz nicht verpflichtend. Für **API-Nutzung** verlangt die [API-Richtlinie](https://www.pexels.com/api/documentation/) jedoch einen gut sichtbaren Pexels-Link und empfiehlt, Urheber mit Link zur Quellseite zu nennen. Das muss später in der Weboberfläche und beim Videoexport berücksichtigt werden. Unbearbeitete Weiterverteilung als Stockmaterial und irreführende Werbung mit erkennbaren Personen oder Marken sind ausgeschlossen.

## Technische Probe

Die Datei [pexels_probe.py](pexels_probe.py) sucht für drei Szenen aus [response-balkon-agy.json](response-balkon-agy.json) nach Hochformatvideos. Pro Szene probiert sie die vorhandenen Suchbegriffe, verlangt MP4, mindestens 720 × 1280 Pixel und eine Quelldauer mindestens so lang wie die Szene. Da die API keinen Videotitel liefert, dient der URL-Text als konservativer Themenhinweis; die eigentliche visuelle Eignung bleibt eine eigene Prüfung. Die Probe speichert Video- und Datei-ID, Pexels-Seite, Urheber und Metadaten. Einen Clip lädt sie begrenzt auf 150 MB herunter, bildet SHA-256 und prüft Videostream, Codec, Auflösung und Dauer mit `ffprobe`. Bericht und Clip liegen unter `tasks/pexels-probe-output/` und bleiben aus Git ausgeschlossen.

| Szene | Suchbegriff | Pexels-Quelle und Urheber | Videodatei | Einschätzung |
| --- | --- | --- | --- | --- |
| 1: Biene auf Lavendel | `bee on lavender` | [Video 33296684](https://www.pexels.com/video/macro-shot-of-bees-on-lavender-flowers-33296684/) von Hao Le | Datei-ID 14182363, 720 × 1280, 20 s | Standbild angesehen: Biene auf Lavendel, passend; Stadtbalkon nicht sichtbar. |
| 2: Blumenkasten am Balkon | `flower box balcony` | [Video 34157136](https://www.pexels.com/video/vibrant-balcony-flowers-in-autumn-setting-34157136/) von Damir K | Datei-ID 14481775, 1080 × 1812, 35 s | Vorschaubild angesehen: bepflanzter Behälter am Balkongeländer; das Einhängen durch eine Person ist nicht zu sehen. |
| 3: Blumenerde einfüllen | `potting soil` | [Video 6911644](https://www.pexels.com/video/person-putting-potting-soil-in-a-flowerpot-6911644/) von Teona Swift | Datei-ID 10222607, 720 × 1280, 11 s | Quellseite beschreibt das Einfüllen von Erde; Bewegtbild noch nicht gesichtet. |

**Download und ffprobe:** Datei `pexels-33296684-14182363.mp4`, 7.191.894 Bytes, SHA-256 `77de8bad1f43cbe7a684bc2152cfa4615c8ed185aabcab54031f0a967d45d7d0`. `ffprobe` meldet H.264-Videostream, 720 × 1280 Pixel und 20,233333 Sekunden. Das Standbild zeigt die erwartete Biene auf Lavendel. Der API-Antwortheader meldete für diesen Key `X-Ratelimit-Limit: 25000` und nach dem Hauptlauf `X-Ratelimit-Remaining: 24988`; das ist die tatsächlich beobachtete Monatsquote dieses Keys, während die Dokumentation den Standardwert 20.000 nennt. Die Stundenquote wurde im Test nicht ausgereizt.

**Grenze der Probe:** Die Szene 2 zeigt den bepflanzten Balkon, aber nicht die im Skript gewünschte Einhängebewegung. Für die spätere Produktionsauswahl in Aufgabe 14 müssen alle konkreten Clips im Bewegtbild geprüft und nötigenfalls andere Suchbegriffe oder Szenenbilder gewählt werden. Die Pexels-API liefert technische Metadaten, aber keine Garantie für inhaltliche Übereinstimmung.

1. `.env.example` nach `.env` kopieren und den kostenlosen `PEXELS_API_KEY` nur dort eintragen. Den Key weder in Git noch im Chat teilen.
2. In einem neuen Terminal `python tasks/pexels_probe.py` ausführen. Wenn FFmpeg im aktuellen Prozess noch nicht im PATH liegt, kann `FFPROBE_PATH` auf die lokale `ffprobe.exe` zeigen.
3. `tasks/pexels-probe-output/report.json` und den heruntergeladenen Clip prüfen. Bei der Produktionsauswahl zusätzlich die Bewegtbilder aller gewählten Quellen ansehen.

**Lokale Prüfung:** Acht Tests bestanden. Der Aufruf ohne Key endet erwartungsgemäß mit einer klaren Fehlermeldung. `ffprobe` wurde über `winget` installiert; zusätzlich zu dem echten Clip wurde der Aufruf zuvor mit einem lokal erzeugten Testclip geprüft.
