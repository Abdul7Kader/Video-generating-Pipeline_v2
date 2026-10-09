# Aufgaben und Abnahmekriterien – Version 1

Bezug: [Umsetzungsplan](plan.md). Reihenfolge ist verbindlich, soweit Abhängigkeiten angegeben sind. Größen: S = ein fokussierter kleiner Schritt, M = ein fokussierter Funktionsabschnitt. Ein Haken wird erst nach der genannten Prüfung gesetzt. Externe Plattformfreigaben bleiben offen, bis ein echter öffentlicher Upload belegt ist.

**Stand 9. Oktober 2026:** Aufgaben 01–21 und M1 sind abgeschlossen; 20 statisch, 21 mit kontrollierten Testdaten. 22 funktional und mit Diensten geprüft, echte Modal-Kontonachweise offen. 23 bis zur finalen Test-MP4 und zum geschützten Abruf funktional nachgewiesen; Betreiber-Bedienungsabnahme offen. Kein Modal-Aufruf. Erstes Ziel ist lokale Nutzung; Codex prüft Funktionen, Betreiber ist Haupttester. Entwicklung am Windows-Rechner/GitHub; Installationsziel bleiben unterstützte Windows-, macOS- und Linux-Rechner. [STATE.md](../STATE.md) enthält den aktuellen Stand. `LOKAL` ist der Pexels-Videomodus, keine Vorgabe für den Entwicklungsort. Echte Live-Abnahmen bleiben ausdrücklich offen; späterer Code darf mit kontrollierten Daten entwickelt werden.

## M0 – Machbarkeit und Vertrag

**18 abgeschlossen.** Speicherpfad in der Weboberfläche editierbar; Kopie vor Aktivierung, geschütztes Playback, Neustart und Prüfsummen nachgewiesen. [Prüfbericht](step18-acceptance.md).

### 01. V1-Produktparameter fixieren (S; abhängig von: keine)
- [x] Ziellänge, Szenenzahl, Sprache/Stimme, Format, Kostenlimit, Rollen und Aufbewahrung als konkrete Arbeitswerte in `plan.md` dokumentiert.
- [x] Zwei repräsentative Abnahmeideen mit erwarteten Szenen und Publikationszielen in `plan.md` beschrieben.
- [x] Die Arbeitswerte und Beispiele sind als V1-Startvorgaben dokumentiert; die spätere Änderung „erst Videos, dann Social Media“ ist im Plan als neue Produktentscheidung festgehalten.
- **Prüfung:** Werte, Beispiele und Änderungskontrolle in `plan.md` dokumentiert; Aufgabe 01 im Management-Index abgehakt.

### 02. Anbieteranforderungen und kostenfreien Skriptweg prüfen (M; abhängig von: 01)
- [x] In [access-matrix.md](access-matrix.md) sind benötigte Konten, Rechte, Limits, Kosten, Authentifizierung und Review-Anforderungen anhand offizieller Quellen dokumentiert.
- [x] Pro Plattform sind Kontotyp, Weg zur öffentlichen Veröffentlichung, Zuständigkeit und Antragsweg erfasst; Konten und Anträge werden nach der Videoabnahme in Aufgaben 25–31 geprüft.
- [x] Kostenwunsch dokumentiert: keine kostenpflichtigen APIs; Modal nur aus nachgewiesenen Gratis-Credits mit wirksamer Null-Nettokosten-Grenze. Social Media folgt nach den Videotests.
- [x] Betreiber hat **Gemini Pro ohne Gemini API** als Skriptweg festgelegt. Die zunächst vorgesehene manuelle Übergabe wurde am 26. September 2026 durch einen automatischen Antigravity-CLI-Aufruf ersetzt; die Anwendung validiert und zeigt das Skript danach zur Bearbeitung. Kein Gemini-Key, kein API-Billing.
- **Prüfung:** Anbieteranforderungen und gewählter Übergabeweg sind in `plan.md` und `access-matrix.md` dokumentiert; Aufgabe 02 im Management-Index abgehakt. Tatsächliche Pexels-, Modal- und Social-Konten werden vor ihren jeweiligen echten Tests bestätigt.

### 03. Gemini-Pro-Skriptprobe ohne API (S; abhängig von: 01–02)
- [x] Für beide Beispielideen liefert Gemini Pro eine Antwort, die sich als strukturierte Daten parsen lässt; derselbe Auftrag wurde mit der vorhandenen Abo-Anmeldung über Antigravity CLI für beide Modi erfolgreich automatisch ausgeführt.
- [x] Pflichtfelder und Grenzen für Sprechertext, Szenen, Bildbeschreibung, Wan-Prompt und Pexels-Suchbegriff sind festgelegt.
- **Prüfung:** Zwei echte Webantworten und zwei automatisch erzeugte Antigravity-Pro-Antworten gegen das Schema validiert; Fehl-/Teilausgabe in fünf lokalen Tests abgewiesen. [Prüfbericht](script-probe.md). Kein Gemini-API-Aufruf.

### 04. Pexels-Probe (S; abhängig von: 01–02)
- [x] Videosuche liefert zu drei Testszenen verwendbare Dateien mit Auflösung, Dauer und Quellen-ID.
- [x] Rate-Limit, Download, Namensnennung und Nutzungsbedingungen sind für den geplanten Einsatz dokumentiert.
- **Prüfung:** [Prüfbericht](pexels-probe.md); einen echten Clip heruntergeladen, mit ffprobe geprüft und Herkunft gespeichert. Die visuelle Abweichung bei Szene 2 ist für die spätere Produktionsauswahl notiert.

### 05. Wan/Modal-Entwurfsprüfung ohne Generierung (S; abhängig von: 01–02)
- [x] Offizielle ComfyUI-/Wan-/Modal-Dokumentation bestätigt benötigten T2V-Workflow, Modellgewichte, `A100-80GB`, mögliche Clipgrößen und Transferweg.
- [x] Erwartete Ressourcen, Gratis-Guthaben und Laufzeit sind als unsichere Planwerte notiert; offene technische Risiken für den ersten Live-Test in Aufgabe 24 erfasst.
- **Prüfung:** [Entwurfs- und Prüfbericht](wan-modal-design.md) mit Quellen, Workflow und Risikoentscheidungen. Kein Modal/Wan-Testclip und kein Cloud-Video vor Aufgabe 24.

**Checkpoint M0:** [x] Produktparameter und kostenfreier Skriptweg fixiert; gewählter Skriptweg und Pexels real geprüft; Wan/Modal dokumentenbasiert vorbereitet. Social-Zugänge sind für die Videoabnahme keine Voraussetzung.

## M1 – Skriptfreigabe

### 06. Projektgerüst und Compose (M; abhängig von: 01)
- [x] React, FastAPI, RQ-Worker, PostgreSQL und Redis starten reproduzierbar per Docker Compose.
- [x] Beispielkonfiguration, lokale `.env` für das Datenbankpasswort und Entwicklungsanleitung liegen vor; der Pexels-Key bleibt in Schritt 06 außerhalb der Container.
- **Prüfung:** Frischer lokaler Git-Checkout **ohne `.env`**: Compose-Build und Start erfolgreich, alle fünf Container gesund, Web und API-Bereitschaft mit HTTP 200. API-Dokumentation ebenfalls HTTP 200. Ein gestoppter Worker bewirkt HTTP 503 und wird nach Neustart wieder als bereit gemeldet. Die temporären Testcontainer und Volumes wurden entfernt.

### 07. Datenmodell und Zustandsmaschine (M; abhängig von: 01, 06)
- [x] Tabellen für Projekt, Skriptversion, Szene, Freigabe, Produktionslauf, Artefakt und Plattformpublikation samt Migrationen existieren.
- [x] Erlaubte Zustandsübergänge verhindern Produktion/Publikation ohne passende Freigabe; Modus und Medientyp sind konsistent.
- **Prüfung:** Migration 0001 auf leerer PostgreSQL-17-Testdatenbank, Rückmigration und erneute Migration erfolgreich; sieben Fachtabellen vorhanden. Vier echte PostgreSQL-Integrationstests prüfen Modus/Medientyp, vollständige unveränderliche Skriptversion, Freigaben, Dateiprüfsumme, Übergänge und Dubletten. Compose-API, DB, Redis und Worker gesund; acht bestehende Python-Tests und Web-Build erfolgreich. [Migration](../backend/app/migrations/0001_initial.sql), [Tests](../backend/app/test_database.py).

### 08. API-Vertrag (S; abhängig von: 07)
- [x] FastAPI-Schemas/Endpunkte für Anlegen, Lesen, Bearbeiten durch neue Skriptversion, Skript- und Videofreigabe, Status und Medienmetadaten/-abruf dokumentiert.
- [x] Versionskonflikt, Validierungsfehler und wiederholte Freigabe haben definierte Antworten.
- **Prüfung:** [API-Vertrag](api-contract.md) mit Beispielpayloads; OpenAPI- und HTTP-Vertragstests gegen isoliertes PostgreSQL-Schema bestanden (3 Tests), darunter idempotente Skript-/Videofreigaben; dazu 4 Datenbanktests, 8 bestehende Python-Tests, Web-Build und gesunder Compose-Stack. Produktionslauf wird als `QUEUED` gespeichert; RQ-Übergabe ist seit Aufgabe 12 implementiert, Produktionsstufen sind in 13 implementiert; konkrete Medienadapter folgen ab 14. Medieninhalt liefert bis Aufgabe 18 ausdrücklich `501`; Veröffentlichungsaufträge folgen in Aufgabe 26.

### 09. Idee- und Modusformular (S; abhängig von: 08)
- [x] React erfasst Idee und Dropdown `CLOUD`/`LOKAL` und zeigt den gewählten Medientyp an.
- [x] Fehlerhafte oder leere Eingaben werden verständlich abgewiesen.
- **Prüfung:** Echter Chrome-Browserlauf gegen den gesunden Fünf-Container-Compose-Stack: Leere Idee abgewiesen; `CLOUD` → `AI_GENERATED_VIDEO` und `LOKAL` → `STOCK_VIDEO`; beide Projekte über das Formular angelegt, aus PostgreSQL geladen und nach Neuladen erneut angezeigt. Web-Build und Python-Tests bestanden. Die UI erzeugt noch kein Skript und kein Video.

### 10. Automatische Gemini-Pro-Skriptintegration (M; abhängig von: 03, 07–08)
- [x] Die Oberfläche startet aus Idee und Modus einen Hintergrundauftrag. Ein Worker ruft Antigravity CLI mit der Google-AI-Pro-Anmeldung auf, validiert und speichert Skript und geordnete Szenen; kein beliebiger Freitext wird als valides Skript akzeptiert. Codex und manuelles Kopieren sind zur Laufzeit nicht erforderlich.
- [x] Ungültige oder unvollständige Antworten, fehlende Anmeldung und erschöpftes Kontingent führen zu verständlichen Fehlern mit bewusster Wiederholung. Automatische AI-Credit-Überziehung ist nachweislich deaktiviert; es gibt keinen stillen Wechsel zu einer kostenpflichtigen API.
- **Prüfung:** Entwicklung mit kontrollierten Antworten; Live-Abnahme auf einem unterstützten, vollständig eingerichteten Rechner mit eigener, bestätigter Google-AI-Pro-/Antigravity-Anmeldung: Idee im Browser absenden, ohne weitere Eingabe echtes Skript erhalten und bearbeiten; kontrollierte Fehlerfälle. Kein Gemini-API-Aufruf. Eine Anmeldung auf einem anderen Rechner wird nicht durch Git übertragen.
- **Abnahme 30.09.2026:** Echte Chrome-Aufträge über angemeldeten Windows-Host-Worker erfolgreich: LOKAL sieben Szenen/45 Sekunden, CLOUD sieben Szenen/42 Sekunden, Speicherung und Neuladen geprüft. Beide Ergebnisse im Browser bearbeitet und als neue Version gespeichert. Kontrollierte Auth-/Quota-/Antwortfehler zeigten sicheren Fehler und bewusst ausgelösten neuen Job; keine ungültige Skriptversion. Kostensperre berücksichtigt die offiziell dokumentierte Standardwert-Speicherung, bleibt bei aktiven Credits/API-Provider gesperrt. `structured_output` wird streng validiert. 25 Backendtests mit PostgreSQL/Redis/RQ, acht Projekttests und Web-Build bestanden. [Prüfbericht](step10-acceptance.md), [Installationsanleitung](install-on-computer.md). Windows-Hintergrundstart über die Vorlage für die aktuelle Sitzung geprüft; Neustart-/Login-Verhalten und weitere Betriebssysteme bleiben in Aufgabe 35 offen.

### 11. Skript- und Szeneneditor (M; abhängig von: 08, 10)
- [x] Benutzer sieht und bearbeitet Sprechertext, Szenen, Bildbeschreibungen sowie Prompts/Suchbegriffe.
- [x] Speichern erzeugt eine neue Version; Validierung und Konflikte sind sichtbar.
- **Prüfung:** Browserprobe: bearbeiten, neu laden, Version prüfen.
- **Abnahme 30.09.2026:** Für beide echten Pro-Ergebnisse Titel, Szenentext, Bildbeschreibung und Suchbegriffe/Wan-Prompt im Browser geändert; Version 2 gespeichert und neu geladen. Dauer und vollständige Szenenmetadaten bleiben erhalten, Version 1 unverändert. Parallel gespeicherte Version 3 erzeugt sichtbaren Konflikt und erhält den Entwurf. Doppelte Suchbegriffe werden sichtbar abgewiesen. API-Integration prüft zusätzlich inkonsistente Dauer, fehlende Metadaten und abweichenden Gesamttext. Der Editor wurde zur vollständigen bestehenden Abnahme von Schritt 10 ergänzt; keine Kriterien abgeschwächt.

### 12. Skriptfreigabe (S; abhängig von: 07, 11)
- [x] Freigabe referenziert eine unveränderliche Skriptversion und stößt genau einen Produktionslauf an.
- [x] Wiederholter Klick und spätere Bearbeitung umgehen die Freigabe nicht.
- **Prüfung 30.09.2026:** Vier neue PostgreSQL-/Redis-/Windows-Worker-Integrationstests einschließlich gleichzeitiger Klicks, Redis-Ausfall vor und nach Übergabe sowie Versionswechsel. Echte Chrome-Probe für LOKAL/CLOUD mit Doppelklick, Neuladen, Bearbeitung und neuer Freigabe; Datenbank und RQ bestätigen genau einen Lauf/Queue-Eintrag pro freigegebener Version. Ladefehler sperren Freigaben, veraltete Browseransicht zeigt 409-Konflikt. 29 Backendtests, acht Projekttests und Web-Build bestanden. [Prüfbericht](step12-acceptance.md). Der Worker blockiert die noch fehlenden Medienstufen sichtbar als `FAILED`, ohne Artefakte; Videoproduktion bleibt Aufgabe 13–18.

**Checkpoint M1:** [x] Idee → automatisch erzeugtes Gemini-Pro-Skript → Bearbeitung → Skriptfreigabe ist im Browser ohne Codex demonstrierbar. Live-Erstellung/Bearbeitung aus Schritt 10/11 und anschließende Browserfreigabe der bestehenden Pro-Version 2 mit normalem angemeldetem Host-Worker geprüft. Kein Video erzeugt. [Belege](step12-acceptance.md).

## M2 – Lokaler Produktionspfad

### UI-Nacharbeit nach M1 (Betreiberwunsch)

- [x] Alle bestehenden Wartezustände zeigen einen Ladebalken ohne erfundene Prozentwerte; Fehler beenden die zugehörige Anfrageanzeige und erlauben Wiederholung.
- [x] Klickbare, deaktivierte und rein informative Elemente sind durch Gestaltung unterscheidbar; Editoraktionen, Fokus und kleine Bildschirme sind geprüft.
- **Abnahme 30.09.2026:** Echte Chrome-Proben LOKAL/CLOUD mit allen Ladephasen, Ergebnis-Ladefehler und Retry, Anfragetimeout und Wiederholung, erstem Ladefehler, überholter Skriptantwort bei Projektwechsel, Tastaturfokus, sichtbarer Speicherleiste und Browser-Entwurfsschutz bestanden. 320/768/1024/1440 Pixel ohne Überlauf, Buttons mindestens 44 Pixel hoch, reduzierte Bewegung und keine JavaScript-Ausnahmen geprüft. Acht Projekttests und Web-Build bestanden. [Prüfbericht](ui-interaction-acceptance.md). Die Produktionssteuerung wurde inzwischen in Schritt 13 ergänzt.

### 13. Produktionskette mit RQ (M; abhängig von: 07, 12)
- [x] Szenenbeschaffung, Sprachsynthese, Grafik, Encoding und Ablage sind getrennte, wiederaufnehmbare Schritte.
- [x] Status, begrenzte Wiederholungen, Timeouts und Fehlerursachen werden in PostgreSQL geführt.
- **Prüfung:** Worker während eines Testlaufs stoppen und ohne doppelte Artefakte fortsetzen.
- **Abnahme 30.09.:** Migration, 37 Backendtests (einschließlich echtem Prozess-Kill/Neustart mit fünf eindeutigen Testdateien/-artefakten), acht Projekttests und Web-Build bestanden. Echte Browserproben LOKAL/CLOUD mit Wiederaufnahme/Abbruch, Ladebalken, Doppelklickschutz und Neuladen bestanden. 320/768/1200 Pixel einschließlich reservierter Scrollleisten ohne horizontalen Überlauf; normale Hostworker-Probe mit bestehender Pro-Freigabe zeigt korrekt den noch fehlenden Szenenadapter. Keine echte Videoerzeugung, Medienadapter folgen in 14–18/21. [Belege](step13-acceptance.md).

### 14. Pexels-Szenenbeschaffung (M; abhängig von: 04, 13)
- **Abgeschlossen 01.10.2026:** 50 Backendtests, acht Projekttests, Web-Build, echte sechs-Szenen-/Kein-Treffer-Abnahme und Browser-Quellenanzeige bestanden. [Prüfbericht](step14-acceptance.md).
- [x] Jede LOKAL-Szene erhält ausschließlich einen geeigneten Pexels-Clip samt Asset-ID und Herkunft.
- [x] Kein Treffer führt zu einem sichtbaren Fehler/Änderungsbedarf, nicht zu einem Wan-Aufruf.
- **Prüfung:** Erfolgs- und Kein-Treffer-Test; Manifest enthält nur `STOCK_VIDEO`.

### 15. Piper-Sprachsegmente (S; abhängig von: 13)
- **Abgeschlossen (01.10.2026):** 58 Backendtests, zehn Projekttests, Web-Build, echte Migration/Piper-/RQ-Produktion und Browserprüfung bestanden. Nach Tempoanpassung bestätigt der Betreiber die zweite Hörprobe einschließlich des Anfangs als verständlich. [Prüfbericht](step15-acceptance.md).
- [x] Sprechertext wird satz- oder szenenweise in Audio umgewandelt; Dauer je Segment wird erfasst.
- [x] Leere oder fehlgeschlagene Sprachausgabe blockiert den Renderjob nachvollziehbar.
- **Prüfung:** Testtext anhören und Dauer per ffprobe mit Segmentdaten vergleichen.

### 16. Remotion-Grafikvorlagen (M; abhängig von: 01, 15)
- **Abgeschlossen (04.10.2026):** 65 Backendtests ohne Überspringen, zehn Projekttests und Web-Build bestanden. Echte Migration-/RQ-/Piper-/Remotion-Integration beider Modi mit kontrollierten Szenenquellen sowie normaler LOKAL-Auftrag mit sechs echten Pexels-Clips, sechs Sprachsegmenten und sieben Grafiken geprüft. Browser-Neuladen, 320 Pixel, Ladebalken und Sichtprüfung bestanden. [Prüfbericht](step16-acceptance.md).
- [x] Titel, satz-/szenengenaue Untertitel und grafische Elemente werden aus gespeicherten Daten gerendert.
- [x] Vorlagen funktionieren für gewähltes Format, sichere Ränder und Sonderzeichen.
- **Prüfung:** Render-Beispiele für kurze/lange Zeilen und deutsche Umlaute visuell prüfen.

### 17. FFmpeg-Pipeline (M; abhängig von: 14–16)
- **Nachprüfung der Benutzerkorrektur:** 73 Backendtests, zehn Projekttests und Web-Build bestanden; normaler neuer Versionslauf mit Grafikvorlage `v2`, 20 geprüften Artefakten und 36-Sekunden-MP4. Pixel-/PNG-Prüfungen belegen fehlende Titel-/Zählereinblendung; alte Vorlagen sind bei neuen Encodes gesperrt. Projektidee und tatsächlicher Schnitt-Eingabetext im [Prüfbericht](step17-acceptance.md#nachprüfung-nach-benutzerkorrektur--04102026).
- **Benutzerkorrektur 04.10.2026:** Betreiber bestätigt echte Aufnahmen, Sichtbarkeit und Verständlichkeit. Neue Endvideos müssen ohne Themenkasten, Szenenzähler und Szenenfortschrittsstreifen erzeugt werden. Die bisherige Dreierfolge ist ausdrücklich ein technisches Testskript, keine Inhaltsvorgabe; Nachprüfung im [Prüfbericht](step17-acceptance.md).
- **Abgeschlossen (04.10.2026):** 72 Backendtests ohne Überspringen, zehn Projekttests und Web-Build bestanden. Echte Dienstintegration beider Modi mit kontrollierter Szene sowie normaler Pexels-/Piper-/Remotion-/FFmpeg-Auftrag erzeugen geprüfte MP4s. Vollständige 36-Sekunden-Wiedergabe, Sichtprüfung aller Szenen und Browser-Profilanzeige mit Neuladen/320 Pixeln bestanden. [Prüfbericht](step17-acceptance.md).
- [x] Clips werden auf Zielprofil normalisiert, zeitlich an Sprechertext angepasst, mit Grafik/Audio zusammengesetzt und encodiert.
- [x] ffprobe validiert jeden Eingang und die finale MP4; defekte oder zu kurze Quellen stoppen den Schritt.
- **Prüfung:** Ein komplettes LOKAL-Testvideo ansehen und technische Sollwerte maschinell vergleichen.

### 18. Portabler persistenter Medienspeicher (S; abhängig von: 07, 17)
- [x] Masterdatei, Zwischenartefakte und Manifest liegen unter stabilen Projekt-/Versionspfaden auf persistentem Speicher des Installationsrechners. Der Pfad ist konfigurierbar und für Windows, macOS und Linux geeignet.
- [x] Browserabruf ist berechtigt und unterstützt Videowiedergabe; Pfadmanipulation wird abgewehrt.
- [x] Speicherpfad direkt in der Weboberfläche ändern, tatsächlichen Kopierfortschritt anzeigen und ursprüngliche Dateien erhalten (Betreiberentscheidung 04.10.2026).
- **Prüfung bestanden 04.10.2026:** Lokaler Browser-Zugriffsweg ist eingerichtet; Containerneustart, Dateiprüfsumme und Browser-Playback auf dem Installationsrechner geprüft. Aufgabe 35 behandelt danach weitere Betriebssysteme, Backup, Härtung und Betriebsübergabe.

- **Belege:** [Abnahmebericht](step18-acceptance.md); 83 verschiedene Backendtests in Gesamt- und gezielten Nachläufen, zehn Projekttests, Web-Build, echter normaler FINAL-Auftrag und Chrome-Wiedergabe.

### 19. Produktionsstatus und Videoprüfung (S; abhängig von: 13, 18)
- [x] Mit einer vom Betreiber gewählten Idee Erzählung und Bildpassung prüfen; unbeabsichtigte Clipwiederholungen erkennen und beheben. Doppelungsprüfung für Pexels-Video-IDs und Datei-SHA-256 ist implementiert; Suchworttreffer ersetzen keine Bildverständnisprüfung. Die Entwicklung hat die neue Folge visuell geprüft; Betreiber bestätigt die korrigierte Folge: „Ja, das passt auf jeden Fall.“ Die wiederholte Dreierfolge des Techniktests zählt nicht als Nachweis abwechslungsreicher Inhalte.
- [x] React zeigt laufende Schritte, Fehler und das fertige Video zur Prüfung an.
- [x] Bis zur Videofreigabe wird kein Publikationsjob erzeugt.
- **Prüfung:** End-to-End-Browserlauf im LOKAL-Modus bestanden: fünf echte Produktionsstufen, vollständige 36-Sekunden-Wiedergabe, Szenensprünge, Freigabe, Retry, Neuladen, 320 px. 86 verschiedene Backendtests, zehn Projekttests und Web-Build bestanden. Doppelungsprüfung implementiert; Suchfehler bei Tomatenernte in neuer Version behoben und visuell nachgeprüft. **Inhaltsabnahme des Betreibers bestätigt. Schritt 19 abgeschlossen.** [Prüfbericht](step19-acceptance.md).

**Checkpoint M2:** [x] Ein fertiges Video im Modus `LOKAL` mit ausschließlich Pexels-Szenen liegt auf dem Installationsrechner und ist über dessen Weboberfläche abspielbar.

## M3 – Cloud-Produktionspfad

### 20. Modal-Workflow ohne Generierung vorbereiten (M; abhängig von: 05, 13)
- [x] Versionierter ComfyUI-Wan-Workflow mit expliziter `A100-80GB`-GPU und reproduzierbaren Modellgewichten ist vorbereitet.
- [x] Keine lokale Wan-Installation ist Teil des Compose-Stacks auf einem Installationsrechner.
- **Prüfung:** Workflow-Datei, Abhängigkeiten und Deploy-Konfiguration statisch prüfen; keine Inferenz auslösen.
- **Abgeschlossen 04.10.2026:** 14 native Nodes, feste ComfyUI-/Modellrevisionen und SHA-256, 99 Linux-Paketversionen mit Hashes, getrennte Volumes, explizite GPU und deaktivierter Live-Einstieg. Sieben Cloudtests, fünf gezielte Backendtests, zehn Projekttests, Web-Build und lokale Konstruktion mit Modal SDK 1.6.1 bestanden. Keine GPU, kein Image-Build/Deployment, keine Gewichte heruntergeladen. Remote-Funktion/Qualität/Kosten bleiben 24; Kriterien unverändert. [Prüfbericht](step20-acceptance.md).

### 21. Cloud-Szenen und Rücktransfer mit Testdaten anbinden (M; abhängig von: 18, 20)
- [x] Die CLOUD-Schnittstelle akzeptiert ausschließlich Wan-Ergebnisse; Beispielclips und Metadaten gelangen geprüft in den konfigurierten Medienspeicher des Installationsrechners.
- [x] Ein abgebrochener Transfer erzeugt weder gültiges Artefakt noch duplizierten Auftrag.
- **Prüfung:** Erfolgs-, Timeout- und beschädigte-Datei-Proben mit kontrollierten Antworten und Testdateien; Manifest enthält nur `AI_GENERATED_VIDEO`. Keine echte Wan-Generierung.
- **Abgeschlossen 05.10.2026:** Auftrag-/Herkunftsprüfung, Mehrclip-Planung, atomare Transfers/Checkpoints, vollständige MP4-/SHA-/Frameprüfung und Wan-Metadaten im Produktionsstatus. Fünf neue Wan-Tests, sieben gezielte bestehende Backendtests, sieben Cloudtests, zehn Projekttests und Web-Build bestanden. Zwei echte PostgreSQL-/Redis-/RQ-/Prozessfälle plus vier API-Vertragstests in 14,968 s; Timeout mit null Artefakten und Wiederaufnahme derselben Kennungen. Nur `CONTROLLED_TEST`, normale CLOUD-Generierung gesperrt. Kein Modal-/GPU-/Modelldownload-Aufruf; Kriterien unverändert. [Prüfbericht](step21-acceptance.md).

### 22. Cloud-Grenzen (S; abhängig von: 21)
- [x] Maximale Clipzahl, Laufzeit, Parallelität und Kostenlimit sind konfigurierbar und werden vor teuren Aufträgen geprüft.
- [ ] Vor einem echten GPU-Auftrag werden verfügbare Modal-Credits, Workspace-Budget und die Grenze für Nettokosten geprüft. Ohne nachgewiesene Null-Nettokosten-Grenze kein Live-Auftrag.
- [x] Modell-/GPU-Fehler bleiben sichtbar und lösen keinen Pexels-Fallback aus.
- **Prüfung:** Grenzwert- und Fehlerfalltests.
- **09.10.2026 implementiert/funktional geprüft:** 28 gezielte Funktionen/Verträge, zehn Projekttests und Web-Build bestanden; keine Browserabnahme durch Codex. Betreiber übernimmt Haupttest und Videoabnahme; erstes Ziel ist lokale Nutzung. Clipzahl, Zeitgrenzen einschließlich Produktionssubprozess, OS-Parallelitätssperren und reine Kosten-Vorprüfung implementiert. Echte Dienstintegration offen: PostgreSQL lokal auch außerhalb der Socketbeschränkung nicht erreichbar, null Integrationstests ausgeführt. Tatsächliche Modal-Kontonachweise und Live-Verknüpfung vor 24 weiterhin offen; kein Modal-Aufruf, keine Aktivierung. [Prüfbericht 22](step22-acceptance.md).
- **Nachweis in 23 ergänzt:** echte PostgreSQL-/Redis-/RQ-/API-Prüfungen in getrennter Testumgebung bestanden, einschließlich Clipgrenze vor Provider und abgelaufener Cloud-Frist bei Resume. Dienstintegration damit nachgewiesen; echte Modal-Kontonachweise unverändert offen.

### 23. CLOUD-Ablauf mit Testdaten prüfen (M; abhängig von: 15–19, 21–22)
- [x] Skriptfreigabe durchläuft den CLOUD-Pfad mit kontrollierten Wan-Antworten und Beispielclips bis zum Video auf dem Installationsrechner.
- [x] Renderer weist absichtlich gemischtes Manifest zurück.
- **Prüfung:** Browserlauf und maschineller Manifest-/ffprobe-Test mit Testdaten; kein echter Cloud-Generierungsaufruf.
- [ ] Betreiber übernimmt Browser-/Bedienungsabnahme; Codex führt auf ausdrückliche Nutzervorgabe nur Funktionsprüfungen und Build aus.
- **09.10.2026 funktional nachgewiesen:** alle fünf echten CPU-Stufen, 36-s-Test-MP4, zwölf kontrollierte Clipaufträge, vollständige Wan-Herkunft, geschützt abrufbare Datei und Bytebereiche, keine Dubletten durch Freigabe/Zustellung. 30 Funktions-/Vertragsprüfungen und acht verschiedene echte Integrationsfälle erfolgreich; Web-Build bestanden. Testvideo/Manifest unter `.data/step23-preview`, keine echte Wan-Qualitätsabnahme. Oberfläche kennzeichnet Testclips; Anzeige noch durch Betreiber prüfen. [Prüfbericht 23](step23-acceptance.md).

### 24. Erstes echtes CLOUD-Video und Videoabnahme (M; abhängig von: 19, 23)
- [ ] Ein reales LOKAL-Video ist bereits gespeichert und im Browser abspielbar; der CLOUD-Pfad wurde mit kontrollierten Testdaten geprüft.
- [ ] Kontoinhaber bestätigt verfügbares Modal-Gratis-Guthaben, Zahlungsmethode für GPU und wirksames Limit von 0 USD Nettokosten; der geschätzte Ressourcenverbrauch liegt innerhalb des Guthabens. Fehlt ein Nachweis, bleibt der Live-Lauf gesperrt.
- [ ] Modal erzeugt mit `A100-80GB`, ComfyUI und Wan 2.2 T2V-A14B die Szenen für Beispiel B. Das fertige Video liegt auf dem Installationsrechner und ist über dessen Weboberfläche prüfbar; Aufgabe 35 schließt den produktiven Betrieb ab.
- [ ] Laufzeit, Ressourcenverbrauch, Qualität, Manifest, Prüfsumme und ffprobe-Profil werden protokolliert; ein Fehlschlag wird innerhalb dieser Aufgabe bearbeitet.
- **Prüfung:** Benutzer sieht und beurteilt ein echtes CLOUD-Video. Kein Social-Media-Upload ist für die Videoabnahme nötig.

**Checkpoint M3 – Video-MVP:** [ ] LOKAL und CLOUD sind real als abspielbare Videos geprüft; visuelle Medientypen bleiben getrennt. Social Media folgt erst danach.

## M4 – Veröffentlichung nach Videoabnahme

### 25. Plattformverbindungen (M; abhängig von: 24, 07–08)
- [ ] OAuth-/Tokenfluss, sichere Speicherung, Erneuerung und Widerruf für berechtigte Zielkonten implementiert.
- [ ] Fehlende Rechte oder Kontotypen erscheinen vor der Videofreigabe als konkrete Hinweise.
- [ ] Vor echter Verbindung sind API-Kosten, vorhandene Konten, Rechte, Billing/Credits und Reviewstatus je Zielplattform anhand des Kontos geprüft. Kostenpflichtige Plattformen bleiben ohne neue Entscheidung deaktiviert.
- **Prüfung:** Verbindung und Widerruf nur mit freigegebenen Testkonten.

### 26. Veröffentlichungsfreigabe (M; abhängig von: 24–25)
- [ ] Benutzer wählt Zielplattformen und prüft Titel, Beschreibung, Sichtbarkeit und Videovorschau.
- [ ] Plattformabhängige Angaben zu Quellen und synthetischen Medien sind vor Freigabe geprüft und gespeichert.
- [ ] Freigabe referenziert Prüfsumme der finalen Datei; pro Plattform entsteht genau ein Auftrag.
- **Prüfung:** Browser-Doppelklick, nachträgliche Datei-/Metadatenänderung und fehlende Verbindung testen.

### 27. YouTube-Adapter (S; abhängig von: 26)
- [ ] Video wird per `videos.insert` mit autorisiertem Kanal und Metadaten hochgeladen; externe ID/Status gespeichert.
- [ ] Private Beschränkung ungeprüfter Projekte wird als solche angezeigt.
- [ ] Erforderlichen Audit für öffentliche Uploads beantragen und bis zur Freigabe verfolgen, falls das Projekt ungeprüft ist.
- **Prüfung:** Echter Testupload, Statusabfrage, Wiederaufnahme nach simuliertem Timeout.

### 28. TikTok-Adapter (S; abhängig von: 26)
- [ ] Direct Post nutzt berechtigten `video.publish`-Scope und zulässige Sichtbarkeitsoptionen.
- [ ] Audit-/Privatbeschränkung und asynchroner Veröffentlichungsstatus werden korrekt dargestellt.
- [ ] Nach privatem Integrationstest den nötigen Audit für öffentliche Direct Posts einreichen und Status verfolgen.
- **Prüfung:** Echter Testpost und Statusabfrage mit autorisiertem Konto.

### 29. Instagram-Adapter (S; abhängig von: 26)
- [ ] Geeignetes professionelles Konto wird erkannt; Reel-Upload und Publish über Meta werden abgeschlossen.
- [ ] Der erforderliche Upload-Weg ab lokal gespeicherter Masterdatei ist geprüft und abgesichert.
- [ ] Container-/Verarbeitungsstatus und Fehler werden gespeichert.
- [ ] Falls der tatsächliche Nutzungskreis es verlangt, nötigen Meta-Review/Advanced Access beantragen und Status verfolgen.
- **Prüfung:** Echter Reel-Test auf geeignetem Testkonto; veröffentlichte ID/URL prüfen.

### 30. Facebook-Adapter (S; abhängig von: 26)
- [ ] Video/Reel wird über die offizielle Meta-Schnittstelle auf die autorisierte Seite veröffentlicht.
- [ ] Seitenrechte, Verarbeitungsstatus und Fehler werden getrennt von Instagram geführt.
- [ ] Falls der tatsächliche Nutzungskreis es verlangt, nötigen Meta-Review/Advanced Access beantragen und Status verfolgen.
- **Prüfung:** Echter Testpost auf Testseite; veröffentlichte ID/URL prüfen.

### 31. X-Adapter und Ergebnisübersicht (M; abhängig von: 26–30; nur nach separater Kostenentscheidung)
- [ ] Video wird per offiziellem Medienupload verarbeitet und einem Post zugeordnet; Post-ID/Status gespeichert.
- [ ] React zeigt fünf unabhängige Plattformresultate mit Links und sicherer Einzelwiederholung.
- [ ] Ein echter X-API-Aufruf ist gesperrt, solange die dokumentierten Pay-per-use-Kosten nicht ausdrücklich freigegeben sind.
- **Prüfung:** Echter X-Testpost nur nach Kostenfreigabe; andernfalls Adapter mit Testdaten prüfen und X als nicht aktiviert ausweisen. Fehler einer Plattform verändert erfolgreiche andere Posts nicht.

**Checkpoint M4:** [ ] Zweite Freigabe löst pro gewählter, freigeschalteter Plattform genau eine Veröffentlichung aus. Plattformen mit ungeklärten Kosten oder Freigaben bleiben ausdrücklich deaktiviert.

## M5 – Produktionsreife und Übergabe

### 32. Sicherheit (M; abhängig von: 06–31)
- [ ] Authentifizierung/Autorisierung, CSRF/CORS, Dateizugriff, Dateipfade, Uploads, Secret-Handling und externe URL-Aufrufe geprüft.
- [ ] Tokens und persönliche Daten erscheinen weder in Logs noch im Browser-Bundle.
- **Prüfung:** Sicherheitsreview und gezielte Negativtests.

### 33. Betrieb und Wiederherstellung (M; abhängig von: 13, 18, 31)
- [ ] Logs/Metriken für Jobs, Kosten, Dauer und Plattformfehler; Alarme für festgelegte Schwellen.
- [ ] Datenbank- und Medienbackup samt Wiederherstellung, Speichergrenzen und Bereinigung dokumentiert.
- **Prüfung:** Restore und Worker-/Host-Neustart als Übung.

### 34. Automatisierte Qualitätsprüfungen (M; abhängig von: 24, 31)
- [ ] Verträge, Zustandsregeln, Medientyptrennung, Renderpfad und Adapter-Fehlerfälle werden automatisiert geprüft.
- [ ] Browser-End-to-End-Pfade laufen für LOKAL mit realen Artefakten auf einem Installationsrechner und für CLOUD mit kontrollierten Antworten; der bereits absolvierte echte CLOUD-Lauf ist dokumentiert.
- **Prüfung:** CI/Build und Tests auf frischem Stand erfolgreich.

### 35. Plattformübergreifende Installation und Handbuch (M; abhängig von: 32–34)
- [ ] Docker-/Compose-Installation, angemeldeter Host-Worker, Medienwerkzeuge, persistente Volumes, lokale Zugriffe, Secrets, Migrationen und Healthchecks für Windows, macOS und Linux dokumentiert. TLS ist nötig, sobald die UI über den lokalen Rechner hinaus erreichbar sein soll.
- [ ] Auf dem gewählten Produktionsrechner vorhandenes Qwen-Modell und Hardware ermitteln; nur falls kein geeignetes Modell vorhanden ist und die Hardware es erlaubt, dort ein sinnvoll lauffähiges Modell installieren. Qwen wird nicht als Videogenerator eingesetzt.
- [ ] Update, Rollback, Backup, Restore und Störungsbehebung sind ausführbar beschrieben.
- **Prüfung:** Installation, Hintergrundstart, Browser-End-to-End-Lauf und Rollback auf je einem repräsentativen Windows-, macOS- und Linux-Rechner geprüft. Nicht verfügbare Zielsysteme ausdrücklich als ungetestet ausweisen; für erneute Wan-Inferenz gelten weiterhin die Kostenregeln aus Aufgabe 24.

**Checkpoint Video-MVP:** [ ] Nach Aufgabe 24 sind beide Modi real geprüft und Videos im Browser abspielbar. **Checkpoint Veröffentlichung:** [ ] Nur ausdrücklich aktivierte, kostenfrei nutzbare oder gesondert freigegebene Plattformen sind real geprüft; übrige Plattformen bleiben als offen ausgewiesen.
