# Remotion-Grafikvorlagen

Lokaler Renderer für Schritt 16: transparente PNG-Ebenen für Titel, Szenenuntertitel und Szenenzähler. React und Remotion **4.0.532**, lokale Noto-Sans-Schriften, Masterprofil **720 × 1280, 24 fps**. Node.js 24 LTS wird auf dem Installationsrechner benötigt.

## Installation

Im Checkout auf Windows, macOS oder Linux:

```sh
npm ci --prefix graphics
npm run install-browser --prefix graphics
```

Der zweite Befehl installiert den passenden Chrome Headless Shell in `graphics/.remotion/`. Abhängigkeiten und Browser sind von Git ausgeschlossen. Während eines Produktionsauftrags werden keine Browser oder Schriften heruntergeladen. Ein fehlender Browser stoppt die Grafikstufe sichtbar. Auf Linux braucht Chrome zusätzliche Systembibliotheken; die vollständige macOS-/Linux-Abnahme gehört zu Schritt 35.

Der Hostworker findet `node` im PATH. Alternativ in der privaten `worker.json` `REMOTION_NODE_PATH` auf eine absolute Node-Datei und optional `REMOTION_BROWSER_EXECUTABLE` auf einen installierten Chrome/Chromium setzen. Der Browser nutzt eine getrennte Sitzung ohne Google-Profil oder Anmeldung. Eingabe sind freigegebene Skriptdaten und gemessene Piper-Segmente.

## Vertrag und Zeitdaten

`app.graphics` prüft Audiohash, tatsächliche WAV-Frames und freigegebenen Szenentext. Es speichert einen Titel und je Szene einen Untertitel als `INTERMEDIATE / GRAPHICS_OVERLAY` sowie ein typisiertes Grafikmanifest. Ablage: `<MEDIA_ROOT>/graphics/<run-id>/`; atomare PNG-/Manifestdateien und Hashprüfungen erlauben Wiederaufnahme. Schriftgröße 22–42 Pixel. Unlesbare oder überlaufende Texte stoppen den Auftrag, ohne Text zu kürzen oder zu ändern.

Sichere Ränder: links 64, rechts 112, oben 96, unten 240 Pixel. Titel und Untertitel bleiben getrennt. Titel am Anfang für höchstens 96 Frames; Untertitel beginnen am Szenenanfang und laufen `ceil(Audiosekunden × 24)` Frames. Jede Szene dauert mindestens ihre geplante Dauer und mindestens die Sprachdauer; Haltezeiten bleiben erhalten. Gesamtdauer weiterhin 30–60 Sekunden. Schritt 17 setzt die Zeitdaten beim Videoschnitt um; Schritt 16 erzeugt keine finale MP4-Datei.

## Lizenz und Kosten

Remotion ist laut [Lizenz](https://github.com/remotion-dev/remotion/blob/main/packages/core/LICENSE.md) und [Preisübersicht](https://www.remotion.dev/docs/license/pricing) für Einzelpersonen, Unternehmen mit höchstens drei Mitarbeitern und gemeinnützige Organisationen kostenlos; die Evaluierung ist ebenfalls kostenlos. Für größere Unternehmen gelten andere Bedingungen. Kein kostenpflichtiger Renderingdienst oder Lizenzschlüssel wird eingerichtet. Noto Sans enthält seine OFL-Lizenz im npm-Paket. Bei geändertem Unternehmensbetrieb die Lizenzberechtigung prüfen.

API-Grundlagen: [renderStill](https://www.remotion.dev/docs/renderer/render-still), [openBrowser](https://www.remotion.dev/docs/renderer/open-browser), [ensureBrowser](https://www.remotion.dev/docs/renderer/ensure-browser). Geprüft am 01.10.2026.
