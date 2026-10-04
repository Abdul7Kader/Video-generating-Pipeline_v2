# Schritt 19 – Produktionsstatus und Videoprüfung

Stand: 04.10.2026. **Entwicklung, technische Abnahme und Betreiber-Inhaltsabnahme abgeschlossen.** Kriterien in [todo.md](todo.md) bleiben verbindlich.

## Benutzerergebnis

- Die ursprüngliche Idee steht direkt beim fertigen Video.
- Vergleich öffnet Sprechertext und Bildvorgaben mit anklickbaren Szenenzeitpunkten aus der tatsächlichen Grafikzeitachse.
- Zwei Prüfpunkte bestätigen Erzählung/Stimme/Untertitel sowie Bildpassung/Wiederholungen. Zweite Freigabe ist sichtbar und nach Neuladen gespeichert. Fehler bleiben erneut versuchbar; neue Version über den Editor.
- Freigabe verlangt die vorhandene Betreiber-Mediensitzung, gleiche Herkunft, aktuelle Version, abgeschlossene Produktion und eine echte unveränderte FINAL-Datei. Projektlock verhindert Versionswechsel während der Freigabe. Wiederholung idempotent. Kein Publikationsauftrag, auch nach Freigabe; Plattformaufträge folgen in 26.
- Pexels-Auswahl/Wiederaufnahme verhindert gleiche Video-IDs und Datei-SHA-256. Suchkandidaten bleiben auf zehn je Abfrage und höchstens vier Abfragen je Szene begrenzt; Downloads/Dauer/Hostlimits bleiben erhalten. Ohne eindeutigen Treffer sichtbarer Änderungsbedarf `PEXELS_DUPLICATE_ONLY`. Alte abgeschlossene Videos bleiben unverändert, doppelte Quellen sperren eine neue Freigabe.
- Die Prüfung erkennt identische Dateien/Provider-IDs, keine ähnlichen Motive unter verschiedenen IDs oder neu codierten Dateien. Semantische Bildpassung und störende Ähnlichkeit müssen am Video beurteilt werden; keine automatische Bildverständnisbehauptung.

## Tatsächliche Eingabe und Ausgabe

Der Betreiber hatte ausdrücklich ein beliebiges Beispiel erlaubt und möchte seine tatsächliche Eingabe/Ausgabe sehen. Beispiel und freigegebenes Prüfsystemskript wurden für diese Abnahme vorbereitet; **kein neuer Antigravity-Aufruf** und keine Behauptung, dieses Skript sei automatisch erzeugt. Die automatische Skripterzeugung ist separat in 10 nachgewiesen.

> Eine kleine Gartenpause: Blüten betrachten, eine Pflanze eintopfen, gießen, Tomaten ernten, einen Schmetterling beobachten und durch den Garten gehen. Sechs verschiedene Aufnahmen; deutsche Stimme und Untertitel.

Skript: „Eine kleine Gartenpause“, de-DE, sechs Szenen à sechs Sekunden. Sprechertext/Bildvorgaben vor dem Produktionslauf:

| Zeit | Sprechertext | Bildvorgabe |
| --- | --- | --- |
| 0–6 s | Die Gartenpause beginnt bei den Blüten. | Nahaufnahme von blühenden Blumen im Garten. |
| 6–12 s | Eine neue Pflanze findet ihren Platz. | Hände pflanzen eine Pflanze in einen Blumentopf. |
| 12–18 s | Mit Wasser versorgen wir die Pflanzen. | Eine Person gießt Pflanzen mit einer Gießkanne. |
| 18–24 s | Reife Tomaten lassen sich frisch ernten. | Eine Hand pflückt rote Tomaten von einer Tomatenpflanze. |
| 24–30 s | Ein Schmetterling besucht eine Blüte. | Ein Schmetterling sitzt auf einer Blume. |
| 30–36 s | Ein kurzer Spaziergang rundet die Pause ab. | Eine Person geht auf einem Weg durch einen grünen Garten oder Park. |

Erste Version: Suchtreffer für „picking tomatoes“ zeigte einen Marktstand. Durch visuelle Prüfung entdeckt; als neue Version Suchbegriffe „harvesting tomatoes“, „tomato harvest“, „picking tomatoes garden“. **Version 2** zeigt Mutter/Tochter bei echter Tomatenernte an der Pflanze, einschließlich roter geernteter Tomate. Fünf andere Motive sind Blüten, Eintopfen, Gießen, Schmetterling und Spaziergang. Alle sechs Motive anhand tatsächlicher Videobilder geprüft, Ernte/Spaziergang zusätzlich an mehreren Zeitpunkten. Keine Titel, Szenenzähler oder Fortschrittsleisten eingeblendet, nur freigegebene Untertitel.

Normale Installation: Projekt `6defbc8a-23f3-444a-ae90-71fa714d4a49`, Version 2, Lauf `dea17aee-5795-4289-abe3-fb109f5f83f1`, FINAL `699c1b8e-cf6b-5311-9542-c9a1a054329f`, SHA-256 `524db42551a4ae3ac6ce66ca4eadba5ad18b944f79f235de1d9b25f61bb24ce3`. Alle fünf Stufen COMPLETED im ersten Versuch; 36 Sekunden, 720 × 1280, 24 fps, H.264/AAC. VIDEO-Freigabe bleibt dem Betreiber vorbehalten; bislang nicht gesetzt.

| Szene | Pexels-ID | Quelle |
| --- | --- | --- |
| 1 | 28183142 | [Pexels-Aufnahme](https://www.pexels.com/video/a-pink-flower-is-growing-in-a-garden-28183142/) |
| 2 | 4768633 | [Pexels-Aufnahme](https://www.pexels.com/video/woman-planting-a-plant-in-a-small-pot-4768633/) |
| 3 | 32236787 | [Pexels-Aufnahme](https://www.pexels.com/video/woman-watering-plants-in-backyard-garden-32236787/) |
| 4 | 5527770 | [Pexels-Aufnahme](https://www.pexels.com/video/mother-and-daughter-picking-tomatoes-5527770/) |
| 5 | 30777896 | [Pexels-Aufnahme](https://www.pexels.com/video/monarch-butterfly-on-vibrant-purple-flowers-30777896/) |
| 6 | 12372888 | [Pexels-Aufnahme](https://www.pexels.com/video/woman-walking-in-garden-12372888/) |

## Technische Prüfnachweise

- `npm run build --prefix web`: bestanden, TypeScript/Vite.
- Vollständige Backendprüfung: **85 Tests / 642,616 s / OK**, keine übersprungen. Danach neue echte Freigabeprüfung plus vier API-Vertragstests: **5 Tests / 73,489 s / OK**. Insgesamt **86 unterschiedliche Backendtests**.
- Zehn Projekttests: bestanden. `git diff --check`: bestanden.
- Echte PostgreSQL-/Redis-/RQ-/Piper-/Remotion-/FFmpeg-Prüfungen: Hash-/ID-Doppelungen, beschädigte FINAL-Datei ohne Freigabe, falsche Prüfsumme, fehlende Medien-Sitzung, fremdes Origin, fehlende Prüfpunkte, alte Version, idempotente Freigabe. Null `platform_publications` vor und nach Freigabe. Native normale Produktion für beide Beispielversionen erfolgreich; nur STOCK_VIDEO-Szenen.
- Separater echter Chrome-Browser + Testschema: Skriptfreigabe über UI startet alle fünf realen Adapter, keine fertigen Checkpoints vorgegeben. Echte Pexels-Clips, keine Farbbilder im Browserbeleg. Medienpasswort ausschließlich kontrollierte Testdatenbank, kein persönliches Betreiberpasswort gesetzt.
- Browser: laufende Stufen/Ladeanzeige, 36/36 s vollständig abgespielt, tatsächliche Eingabe, sechs Vergleiche, Szenensprung zu 18 s, Freigabe erst nach beiden Prüfpunkten. Kontrollierter HTTP-503 vor Speichern erhält Prüfpunkte, echter zweiter Versuch erfolgreich. Neuladen zeigt gespeicherte Freigabe ohne erneuten Freigabebutton, Editor öffnet neue Version. Projektlink lädt/persistiert richtig. 320 px ohne Überlauf, null Konsolenfehler.
- Prüfergebnisse lokal/ignoriert: `.data/step19-tests.log`, `step19-focused.log`, `step19-browser-result.json`, `step19-live-context.json`. Screenshots separat im Codex-Visualisierungsordner. Medien, Modelle und private Worker-Konfiguration nicht committet.

## Betreiberabnahme und nächster Schritt

Der Betreiber bestätigt den Vergleich der genannten Eingabe mit der korrigierten MP4: **„Ja, das passt auf jeden Fall.“** Alle Kriterien von Schritt 19 damit erfüllt. Auf seine Rückfrage erklärt: LOKAL montiert Pexels-Aufnahmen passend zum vorher festgelegten Skript; CLOUD soll Wan-Szenen selbst erzeugen. Dieses Beispiel ist ein manuell vorbereitetes Prüfskript, kein neuer automatischer Pro-Lauf. Normale Medienzugangseinrichtung und eigentliche Videofreigabe sind Betreiberhandlungen; die Funktion wurde mit getrennter Testanmeldung vollständig geprüft. CLOUD-Live-Produktion, Social-Media-Adapter und vollständige weitere Betriebssysteminstallationen bleiben den späteren Aufgaben zugeordnet.

Nächste Aufgabe: 20 – ComfyUI-Wan-/Modal-Workflow statisch vorbereiten, keine Inferenz.
