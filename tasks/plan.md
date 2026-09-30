# Umsetzungsplan Version 1 – automatisierte Videoproduktion

Stand: 1. Oktober 2026

Stand am 1. Oktober 2026: Aufgaben 01–14 sind abgeschlossen. Schritt 10 wurde mit zwei echten Browseraufträgen über das bestätigte Google-AI-Pro-Konto des Windows-Host-Workers abgenommen (LOKAL sieben Szenen/45 Sekunden, CLOUD sieben Szenen/42 Sekunden). Der für dessen Bearbeitungs-Prüfung erforderliche Szeneneditor aus Schritt 11 ist ebenfalls implementiert und live geprüft. Gespeicherte neue Versionen, unveränderte alte Versionen, sichtbare Validierung und Entwurfserhalt bei Konflikten sind nachgewiesen. Kontrollierte Fehlerfälle prüfen bewusste Wiederholung. [Prüfbericht](step10-acceptance.md).

Schritt **12 – Skriptfreigabe** und M1 sind ebenfalls abgenommen: Browser bestätigt die angezeigte Version, neue Versionen verlangen neue Freigaben. Datenbank-Commit vor RQ-Übergabe, stabile Lauf-ID und Projekt-Sperren sichern wiederholte/gleichzeitige Aufrufe und Retry nach Brokerfehler. Beide Modi im echten Browser geprüft; 29 Backendtests, acht Projekttests und Web-Build bestehen. Zusätzlich wurde eine bereits live erzeugte und bearbeitete Pro-Version in der normalen Anwendung freigegeben und vom angemeldeten Host-Worker verarbeitet. [Prüfbericht](step12-acceptance.md).

Nächste Aufgabe: **15 – Piper-Sprachsynthese**. Die Produktionskette aus Schritt 13 führt fünf wiederaufnehmbare Stufen. Schritt 14 beschafft echte Pexels-Clips im LOKAL-Modus und speichert Quellenartefakte; die nächsten noch fehlenden Adapter scheitern sichtbar mit `STAGE_UNAVAILABLE`, ohne ein fertiges Video zu behaupten. Die Entwicklung läuft am Windows-Rechner über GitHub; Installationsziel bleiben unterstützte Windows-, macOS- und Linux-Rechner. Ubuntu ist optional. Vollständige Installation, Login-/Neustartverhalten und weitere Betriebssysteme bleiben Aufgabe 35. Verbindlicher Stand: [STATE.md](../STATE.md).
Aufgabenliste: [todo.md](todo.md)

**Schritt 14 abgeschlossen (01.10.2026):** Native Pexels-Beschaffung, ffprobe-Prüfung, Quellenmanifest/-anzeige, atomare Downloads, 24-Stunden-Suchcache und Wiederaufnahme einzelner Szenen. 50 Backendtests, acht Projekttests, Web-Build und echte sechs-Szenen-/Kein-Treffer-/Browserabnahme bestanden. Das unveränderte Pro-Skript meldet korrekt Szene 6 als nicht auffindbar; das positive Testskript wurde nach visueller Prüfung als neue Version präzisiert. Keine automatische Bildanalyse. Die Quellen liegen vorläufig in `.data/media` oder einem absoluten `MEDIA_ROOT`; endgültige Ablage und Browserwiedergabe bleiben Schritt 18. [Abnahme](step14-acceptance.md).

**Abschluss Schritt 13:** Fünf persistente RQ-Produktionsstufen, drei Versuche pro Stufe, unverlängerte Drei-Stunden-Gesamtgrenze, Prozesszeitlimits, automatische Zustellung/Wiederaufnahme und API-/UI-Abbruch implementiert. PostgreSQL-/Redis-/RQ-Abbruchprüfung ohne Artefaktdubletten, 37 Backendtests, acht Projekttests und Web-Build bestanden. Echte Chrome-Bedienabnahme für beide Modi, Neuladen und kleine Bildschirme erfolgreich. Medienadapter werden weiterhin in 14–18/21 umgesetzt; Abnahmekriterien unverändert. [Belege](step13-acceptance.md).

**UI-Nacharbeit auf Betreiberwunsch:** Bestehende Wartezeiten erhalten gemeinsame Ladebalken mit tatsächlicher Phase statt geschätztem Prozentfortschritt. Die Klickbarkeit wird durch einheitliche Buttonformen, Hover/Fokus und klar getrennte gesperrte/passive Zustände sichtbar, ohne zusätzliche Bedienhinweise. Speicherleiste und Fokus verbessern den Szeneneditor. Web-Build, acht Projekttests und echte Browserproben für beide Modi mit verzögerten Antworten/Fehlern, Timeout/Retry, Projektwechsel, Editor-Entwurfsschutz und responsive Gestaltung bestanden. [Prüfbericht](ui-interaction-acceptance.md). Umfang und Kriterien von Schritt 13 bleiben unverändert.

## 1. Ziel und verbindlicher Umfang

Ein Benutzer gibt in der React-Oberfläche eine Videoidee ein und wählt **CLOUD** oder **LOKAL**. Die Anwendung erzeugt das Skript automatisch über die mit dem vorhandenen Google-AI-Pro-Konto angemeldete Antigravity CLI im Hintergrund. Sie validiert das Ergebnis und zeigt das Skript zur Prüfung und Bearbeitung an. Es sind weder Codex zur Laufzeit noch ein manuelles Kopieren aus Gemini nötig. Die Skriptfreigabe startet automatisch die Videoproduktion. Das fertige Video liegt dauerhaft auf dem gewählten Installationsrechner und ist in dessen Oberfläche abspielbar. **Erst nach der Videoabnahme** wird die zweite Freigabe für ausgewählte Veröffentlichungsplattformen umgesetzt.

| Modus | Einziger visueller Medientyp | Bildquellen und Ausführung |
| --- | --- | --- |
| CLOUD | `AI_GENERATED_VIDEO` | Jede Videoszene mit ComfyUI und Wan 2.2 T2V-A14B auf Modal, GPU `A100-80GB`; Ergebnisse zurück auf den Installationsrechner |
| LOKAL | `STOCK_VIDEO` | Jede Videoszene aus der Pexels API; Produktion auf dem Installationsrechner; kein Wan |

Beide Modi verwenden Piper für Sprechertext, FFmpeg/ffprobe für Verarbeitung und Encoding sowie Remotion für Texte, Untertitel und Grafiken. Visuelle Szenenquellen werden innerhalb eines Videos **nie** gemischt. Wenn eine Quelle ausfällt, erhält das Video einen Fehler- oder Wartezustand; es gibt keinen stillen Wechsel des Medientyps.

**Kosten- und Prioritätsregel:** Zuerst soll der Benutzer fertige LOKAL- und CLOUD-Videos in der Oberfläche ansehen und beurteilen können. Erst danach folgen Social-Media-Verbindungen und Veröffentlichungen. Ohne neue Produktentscheidung werden keine kostenpflichtigen APIs aktiviert. Für Modal ist nur ein kontrollierter Test innerhalb tatsächlich verfügbarer kostenloser Credits vorgesehen; eine hinterlegte Zahlungsmethode allein ist keine Kostenfreigabe. **Skriptweg für V1:** Die offizielle Antigravity CLI nutzt die bestehende Google-AI-Pro-Anmeldung und erzeugt im Hintergrund strukturierte Skripte. Die Gemini API und ein Gemini-API-Key werden nicht verwendet. Bei fehlender Anmeldung, erschöpftem Abo-Kontingent oder ungültiger Antwort zeigt die Anwendung einen Fehler; sie wechselt weder zu einer Bezahl-API noch zu einer manuellen Übergabe.

**Entwicklung und Installationsziel ab 29. September 2026:** Der Betreiber entwickelt die Anwendung zunächst auf dem aktuellen Windows-Rechner am GitHub-Repository. Die Anwendung soll anschließend auf einem unterstützten Windows-, macOS- oder Linux-Rechner mit Docker Compose, Python 3.12, Antigravity CLI und späteren Medienwerkzeugen installierbar sein. Ubuntu ist eine mögliche Distribution, kein festes Ziel. `LOKAL` bezeichnet ausschließlich den Pexels-Videomodus. Anmeldungen, `.env` und Medien werden nicht durch Git übertragen. Die vollständige Portabilität ist noch zu prüfen.

**Qwen-Regel für Entwicklung und Produktion:** Das auf einem früheren Windows-Rechner installierte Qwen war eine optionale Testmöglichkeit und ist **keine Voraussetzung** für die aktuelle Entwicklung. Es wird dafür nicht neu installiert oder verändert. Ein Test mit Qwen ersetzt keinen später gewünschten Gemini-Integrationstest. Erst auf dem gewählten Installationsrechner wird geprüft, ob dort ein geeignetes Qwen-Modell vorhanden ist. Nur falls keines vorhanden ist und die Hardware es erlaubt, wird dort ein sinnvoll lauffähiges Modell installiert. Qwen ist kein Videogenerator und ersetzt Wan nicht.

## 2. Produkt- und Architekturentscheidungen

### 2.1 Benutzerfluss und Freigaben

1. Idee, Modus und zunächst gewünschte Plattformen erfassen; Projekt anlegen.
2. Die API erstellt aus Idee und Modus einen Gemini-Pro-Auftrag mit festem Ausgabeformat und startet die Antigravity CLI als begrenzten Hintergrundauftrag. Die Anwendung akzeptiert nur ein valides strukturiertes Skript mit Sprechertext, geordneten Szenen, visueller Beschreibung und je nach Modus Wan-Prompts beziehungsweise Pexels-Suchbegriffen. Fehler und ungültige Antworten werden angezeigt; der Benutzer kann den Auftrag erneut starten oder nach erfolgreicher Generierung das Skript bearbeiten.
3. Benutzer bearbeitet Skript und Szenen. Speichern erzeugt eine neue Skriptversion.
4. Skriptfreigabe fixiert genau diese Version und startet einen Produktionsauftrag. Spätere Textänderungen verlangen eine neue Version und neue Freigabe.
5. System produziert die Szenen, Sprachdateien, Untertitel, Grafiken und das finale Video. Fortschritt, Fehler und Wiederaufnahme sind sichtbar.
6. Benutzer prüft das fertige Video sowie Plattformauswahl und Veröffentlichungsdaten. Videofreigabe fixiert genau die geprüfte Videodatei und startet je Plattform einen eigenen Veröffentlichungsauftrag.
7. Ergebnis je Plattform anzeigen: in Bearbeitung, veröffentlicht mit Link, oder fehlgeschlagen mit gezielter Wiederholungsmöglichkeit. Kein erneuter Upload eines bereits veröffentlichten Ergebnisses.

### 2.2 Technischer Aufbau

```text
React UI ── FastAPI ── PostgreSQL (Projekte, Versionen, Freigaben, Jobs, Veröffentlichungen)
                │
                ├── Redis + RQ ── Host-Worker ── Antigravity CLI (Gemini-Pro-Skript)
                │                        ├── Pexels / Piper / FFmpeg / Remotion
                │                        │
                │                        └── Modal-Auftrag ── ComfyUI + Wan 2.2 T2V-A14B
                │
                ├── lokaler, persistenter Medienspeicher auf dem Installationsrechner
                └── offizielle YouTube-, TikTok-, Meta- und X-Schnittstellen
```

- Docker Compose verwaltet Weboberfläche, API, PostgreSQL und Redis. Für Installation und Live-Betrieb ersetzt `compose.host-worker.yaml` den nicht angemeldeten Container-Worker durch einen unter dem angemeldeten Benutzer des Installationsrechners laufenden RQ-Host-Worker; PostgreSQL und Redis bleiben an `127.0.0.1` gebunden. Linux/macOS verwenden `SpawnWorker`, Windows wegen eines bestätigten Fehlers in RQ 2.3.2 `SimpleWorker` mit Timer und ohne separaten RQ-Kindprozess. Dieser Weg ist vorbereitet, aber noch nicht auf allen Zielsystemen live geprüft. Produktionsdateien und Datenbank brauchen persistenten Speicher unabhängig vom Betriebssystem. Modal bleibt ein separat deployter Cloud-Dienst; Compose startet keine lokale Wan-Instanz.
- Der Skript-Worker startet die offizielle Antigravity CLI mit Pro-Modell und JSON-Ausgabe in einem isolierten temporären Arbeitsordner. Der Prototyp in `tasks/agy_script_probe.py` hat beide Modi mit einer vorhandenen Antigravity-Anmeldung erfolgreich geprüft. Die Zuordnung zum gewünschten Google-AI-Pro-Konto wurde für die Windows-Live-Abnahme vom Betreiber bestätigt; weitere Installationsrechner benötigen ihre eigene Bestätigung. Der Worker braucht dort eine einmalige Anmeldung unter demselben Benutzer und Zugriff auf dessen Betriebssystem-Schlüsselspeicher; das wird vor dem Produktivbetrieb getestet. Ein leeres oder ungültiges Ergebnis wird abgewiesen.
- Die Videoabnahme läuft auf einem unterstützten Installationsrechner mit persistentem Medienspeicher und lokalem Browser. Der aktuelle Entwicklungsrechner kann dafür verwendet werden, sobald er alle Voraussetzungen erfüllt; ein separater Server ist nicht erforderlich. Aufgabe 18 richtet Speicher und Browserabruf ein; Aufgabe 35 prüft Installation, Härtung, Backup und Wiederherstellung auf den unterstützten Betriebssystemen. Gerätespezifische Pfade und Zugangsdaten gehören nicht ins Repository.
- PostgreSQL ist die fachliche Quelle für Zustände. Redis/RQ transportiert Hintergrundjobs. Jeder Schritt ist anhand von Projekt-ID, Skriptversion und Job-ID wiederaufnehmbar und gegen doppelte Ausführung geschützt.
- Der Produktionsmodus und der daraus abgeleitete Medientyp werden beim Anlegen gespeichert und bei jeder Szenenbeschaffung und vor dem finalen Rendern geprüft.
- Der CLOUD-Worker übergibt nur die nötigen Prompts an Modal. Er lädt fertige Clips zurück, prüft sie mit ffprobe und legt sie auf dem persistenten Speicher des Installationsrechners ab. Dort geschieht das finale Rendering.
- Ein Medienmanifest pro Version enthält Quelle, Pexels-Asset-ID oder Wan-Workflow/Seed, Dateipfad, Prüfsumme, Dauer, Format und Rechte-/Herkunftsinformationen. Es erlaubt Nachvollziehbarkeit und Wiederaufnahme.
- Für Plattformen, die Videodateien selbst von einer URL abrufen, wird ein zeitlich begrenzter HTTPS-Abruf vom jeweils erreichbaren Installationsrechner oder einem dafür vorgesehenen Veröffentlichungsdienst geprüft. Die Masterdatei bleibt lokal gespeichert; Upload-Transport und Zugriffsprotokoll werden pro Plattform geprüft.
- Externe Tokens werden serverseitig gespeichert und verschlüsselt beziehungsweise über geeignete Secret-Verwaltung bereitgestellt. Sie erscheinen weder im Browser noch in Logs.

### 2.3 Festgelegte V1-Produktparameter – Aufgabe 01

Die folgenden Werte gelten als V1-Startvorgaben. Sie wurden mit dem Auftrag vom 26. September 2026, Schritt 01 jetzt abzuschließen, als konkrete Arbeitswerte festgelegt. Der Nutzer hat keine abweichenden Zahlen vorgegeben; spätere Änderungen werden als Produktänderung dokumentiert.

| Parameter | Vorgeschlagener V1-Wert | Grund / Prüfpunkt |
| --- | --- | --- |
| Videotyp | Vertikales Kurzvideo; Ziel 45 Sekunden, zulässiger Bereich 30–60 Sekunden | Gemeinsamer Ausgangspunkt für die fünf Zielplattformen; Kontogrenzen vor Upload prüfen. |
| Szenen | 6–10 geordnete Szenen, jeweils mit Sprechertext und visueller Beschreibung | Deckt 30–60 Sekunden ab; längere Szenen brauchen im CLOUD-Modus mehrere Wan-Clips derselben Quelle. |
| Sprache | Deutsch (`de-DE`) für Skript, Sprechertext und Untertitel | Ein klarer V1-Sprachumfang. |
| Piper-Stimme | `de_DE-thorsten-high` als konfigurierbare Standardstimme | Das Stimmenmodell ist verfügbar; Klang wird in Aufgabe 15 angehört. |
| Mastervideo | Hochformat 9:16, 720 × 1280 Pixel, 24 fps, MP4/H.264 und AAC | Wan unterstützt 720 × 1280; TikTok erlaubt 24 fps und MP4/H.264. Plattformadapter dürfen Encodes aus derselben freigegebenen Masterdatei ableiten. |
| Untertitel | Satz- oder szenengenau anhand separat synthetisierter Piper-Segmente | Nachvollziehbares Timing ohne zusätzliches Sprachmodell; keine Wort-für-Wort-Zusage. |
| CLOUD-Budget | Maximal 10 USD Ressourcenverbrauch pro Testvideo **innerhalb vorhandener kostenloser Credits**; 0 USD zulässige Nettokosten, ein CLOUD-Auftrag gleichzeitig, maximal 3 Stunden Produktionslaufzeit | Vor dem ersten GPU-Auftrag Restguthaben und Kontolimits prüfen. Workspace-Budget und Limit für Kosten außerhalb von Credits müssen wirksam sein. Ist eine Null-Kosten-Grenze nicht verifizierbar, bleibt der Live-Test gesperrt. |
| LOKAL-Budget | Keine GPU-Modellkosten; Pexels-Limits und lokaler Speicher begrenzen den Durchsatz | Kein Wan-Aufruf im LOKAL-Modus. |
| Benutzer und Rollen | Ein authentifizierter Betreiber mit Freigaberecht; keine Selbstregistrierung in V1 | Entspricht dem beschriebenen einzelnen Benutzer; weitere Rollen erst mit eigenem Bedarf. |
| Plattformkonten | Ein verbundenes Zielkonto je Plattform; Auswahl pro Video | V1 unterstützt YouTube, TikTok, Instagram, Facebook und X, sofern die jeweiligen Konten/API-Freigaben bereitstehen. |
| Veröffentlichung | Nach erfolgreicher Videoabnahme als spätere Ausbaustufe; pro Plattform nur nach geklärten API-Kosten und Freigaben | Veröffentlichungen werden getrennt verfolgt. Kostenpflichtige Plattform-APIs, insbesondere X, bleiben ohne neue Kostenfreigabe deaktiviert. |
| Aufbewahrung | Finale Masterdateien bis zur ausdrücklichen Löschung durch den Betreiber; Zwischenartefakte 30 Tage nach erfolgreichem Rendern; Betriebslogs 30 Tage | Finale Videos gehen nicht durch eine stille Frist verloren; automatische Bereinigung betrifft nur ersetzbare Daten. Backup-Frist wird in Aufgabe 32 festgelegt. |

### 2.4 Repräsentative Abnahmeideen für Aufgabe 01

**Beispiel A – „Ein bienenfreundlicher Stadtbalkon in fünf Schritten“:** Ein 30–60 Sekunden langes, deutsch gesprochenes Informationsvideo. Erwartete Bildfolge: (1) karger Balkon, (2) passende Blühpflanzen, (3) Einpflanzen, (4) Gießen, (5) Biene an einer Blüte, (6) fertiger Balkon mit Schlussbotschaft. Jede Szene braucht Sprechertext, Bildbeschreibung und Pexels-Suchbegriffe. Erste Abnahme: `LOKAL` mit ausschließlich Pexels-Clips, gespeichert und im Browser abspielbar. Veröffentlichung auf YouTube, Instagram und Facebook ist eine spätere, separate Prüfung.

**Beispiel B – „Ein Regentag in der Stadt“:** Ein 30–60 Sekunden langes, deutsch gesprochenes atmosphärisches Kurzvideo. Erwartete Bildfolge: (1) Regen über der Stadt, (2) Menschen mit Schirmen, (3) Straßenbahn im Regen, (4) Regentropfen am Caféfenster, (5) spiegelnde Straßenlichter, (6) Abendansicht mit Schlussbotschaft. Jede Szene erhält Sprechertext und Bildbeschreibung; im Modus `LOKAL` zusätzlich Pexels-Suchbegriffe, im Modus `CLOUD` stattdessen einen Wan-Prompt. Zuerst wird B im Modus `LOKAL` produziert. Nach kontrollierten CLOUD-Tests folgt in Aufgabe 24 ein echtes Wan-Video innerhalb geprüfter Gratis-Credits, das im Browser angesehen wird. TikTok und X werden erst danach gesondert betrachtet; X benötigt vor einem API-Test eine Kostenentscheidung.

**Messbare Videoabnahme:** Der Benutzer kann die Idee eingeben, den Modus wählen, ein automatisch erzeugtes strukturiertes Skript prüfen und bearbeiten, es freigeben und das fertige Video im Browser ansehen. LOKAL-Manifeste enthalten nur `STOCK_VIDEO`, das echte CLOUD-Manifest nur `AI_GENERATED_VIDEO`; ffprobe bestätigt das Masterprofil. Die spätere Veröffentlichungsabnahme ist davon getrennt und verlangt je Plattform eine externe ID und einen erreichbaren Ergebnislink.

## 3. Reihenfolge und Meilensteine

Die Implementierung erfolgt in **vertikalen, testbaren Abschnitten**. Nach jedem Meilenstein muss der bereits gebaute Benutzerfluss weiter funktionieren.

| Meilenstein | Aufgaben | Ergebnis und Entscheidungstor |
| --- | --- | --- |
| M0: Machbarkeit und Vertrag | 01–05 | Produktparameter, kostenfreie Skript-/Pexels-Optionen und dokumentenbasierte Wan-/Modal-Prüfung sind belegt. Social-Kontozugänge werden später geprüft. |
| M1: Skriptfreigabe | 06–12 | Idee → automatischer Gemini-Pro-Skriptauftrag → validiertes, editierbares Skript → unveränderliche Freigabe funktioniert im Browser, ohne Codex und ohne manuelle Übergabe. |
| M2: Pexels-Produktionspfad | 13–19 | Freigegebenes Skript → ausschließlich Pexels → Piper/Remotion/FFmpeg → auf dem Installationsrechner gespeichertes, im Browser prüfbares Video. |
| M3: Cloud-Produktionspfad und Videoabnahme | 20–24 | CLOUD-Integration erst mit Testdaten prüfen, dann innerhalb nachgewiesener Gratis-Credits ein echtes Wan-Video erzeugen und im Browser ansehen. |
| M4: Veröffentlichung nach Videoabnahme | 25–31 | Plattformzugänge, Freigabe und Adapter erst jetzt bearbeiten; kostenpflichtige APIs bleiben ohne gesonderte Entscheidung deaktiviert. |
| M5: Produktionsreife und Übergabe | 32–35 | Sicherheit, Ausfallsicherheit, Tests und Installation auf den unterstützten Betriebssystemen für tatsächlich aktivierte Funktionen nachweisen. |

**Kritischer Pfad für Live-Abnahmen:** Produktparameter und kostenfreier Skriptweg → Daten-/Zustandsvertrag → kontrolliert geprüfte Skriptfreigabe und Videofunktionen → Installation auf einem unterstützten Rechner mit eigener Antigravity-Anmeldung und persistentem Speicher → echter LOKAL-Videotest → geprüfte Modal-Credits/Kostensperre → echter CLOUD-Videotest und Benutzerprüfung. Der CLOUD-Pfad mit Testdaten kann schon während der Entwicklung geprüft werden. Erst nach der echten Videoabnahme folgen Plattformverbindungen, Veröffentlichungsfreigabe und Adapter. Die Anforderungen und späteren Kontoprüfungen stehen in der [Zugangs- und Freigabematrix](access-matrix.md).

**Verbindliche Testreihenfolge:** Vor Aufgabe 24 wird kein Video mit Wan auf Modal generiert. CLOUD-Jobs, Fehlerfälle, Rücktransfer und Benutzeroberfläche werden zunächst mit festen Beispielartefakten geprüft. Erst wenn ein reales LOKAL-Video vorliegt, die CLOUD-Testdaten funktionieren und Modal-Guthaben samt Kostenbegrenzung nachgewiesen sind, darf Aufgabe 24 einen echten Wan-Lauf auslösen. Ohne sichere Null-Nettokosten-Grenze bleibt dieser Lauf gesperrt. Vor der Videoabnahme erfolgt kein Social-Media-Upload.

**Projektsteuerung:** Nach M0 wird aus dokumentierten Wan-Anforderungen und den Videoparametern ein vorläufiger Termin- und Kostenplan erstellt. Die tatsächlichen Wan-Werte werden in Aufgabe 24 gemessen. Jede Aufgabe erhält einen Verantwortlichen, einen nachprüfbaren Abschluss und einen kurzen Demo-/Testnachweis. Social-API-Reviews werden erst nach der Videoabnahme verfolgt. Technische Änderungen an den verbindlichen V1-Vorgaben brauchen eine dokumentierte Produktentscheidung.

## 4. Nummerierte Todos

Die Prüfpunkte, Abhängigkeiten und konkreten Abnahmekriterien stehen in [todo.md](todo.md). Diese Liste ist der Management-Index.

### M0 – Machbarkeit und Vertrag

01. [x] V1-Produktparameter und Abnahmebeispiele festlegen.
02. [x] Anbieteranforderungen prüfen und Gemini Pro ohne Gemini API als Skriptweg festlegen; Social-Kontostatus später erfassen ([Matrix](access-matrix.md)).
03. [x] Gemini-Pro-Auftrag, strukturierte Antworten und automatischen Aufruf über Antigravity CLI prototypisch prüfen ([Prüfbericht](script-probe.md)).
04. [x] Pexels-Videosuche und Quellen-/Lizenzdaten prototypisch prüfen ([Prüfbericht](pexels-probe.md)).
05. [x] ComfyUI/Wan auf Modal A100-80GB dokumentenbasiert prüfen; keinen Testclip erzeugen ([Prüfbericht](wan-modal-design.md)).

### M1 – Skriptfreigabe

06. [x] Projektgerüst, Docker Compose und Konfigurationsverwaltung anlegen.
07. [x] Datenmodell, Migrationen und verbindliche Zustandsmaschine erstellen. Migration 0001 auf leerer PostgreSQL-17-Datenbank und vier Integrationstests bestanden.
08. [x] API-Verträge für Projekt, Skriptversion, Freigaben, Status und Medien definieren. HTTP-/OpenAPI-Vertragstests gegen PostgreSQL bestanden; [Vertrag](api-contract.md).
09. [x] Idee- und Modusformular in React umsetzen; Browserprobe für beide Modi, Validierung und gespeicherte Projektansicht bestanden.
10. [x] Automatischen Antigravity-Pro-Skriptauftrag samt Schema-Validierung und Fehlerbehandlung anbinden.
11. [x] Skript- und Szeneneditor mit Versionierung umsetzen.
12. [x] Skriptfreigabe und automatische, eindeutige Produktionsauslösung umsetzen. Browser-/Datenbank-/RQ-Abnahme bestanden; Produktionsstufen sind in 13 implementiert; konkrete Medienadapter folgen ab 14. [Belege](step12-acceptance.md).

### M2 – Lokaler Produktionspfad

13. [x] Robuste RQ-Produktionskette mit Status, Wiederholung und Abbruchgrenzen bauen. PostgreSQL-/Redis-/RQ-Neustartprobe und Browserbedienung bestanden; [Belege](step13-acceptance.md).
14. [x] Pexels-Suche, Auswahl und Download pro Szene implementieren ([Prüfbericht](step14-acceptance.md)).
15. [ ] Piper-Sprechersegmente und Zeitdaten erzeugen.
16. [ ] Remotion-Vorlagen für Text, Untertitel und Grafiken rendern.
17. [ ] FFmpeg/ffprobe-Normalisierung, Szenenschnitt, Audio und Encoding bauen.
18. [ ] Portablen persistenten Medienspeicher, Manifest und sicheren Videoabruf einrichten.
19. [ ] Produktionsstatus und Videoprüfung in React bereitstellen.

### M3 – Cloud-Produktionspfad

20. [ ] Reproduzierbaren ComfyUI/Wan-Workflow für Modal vorbereiten, ohne Generierung auszulösen.
21. [ ] Szenenaufträge, Ergebnistransfer und Validierung mit Testdaten anbinden.
22. [ ] Cloud-spezifische Laufzeit-, Kosten- und Fehlergrenzen integrieren.
23. [ ] Durchgängigen CLOUD-Ablauf mit kontrollierten Testdaten und Trennung der Medientypen prüfen.
24. [ ] Erstes echtes CLOUD-Video innerhalb nachgewiesener Gratis-Credits erzeugen und im Browser abnehmen.

### M4 – Veröffentlichung nach Videoabnahme

25. [ ] Plattformverbindungen, OAuth, Tokenpflege und Zielkonten umsetzen.
26. [ ] Veröffentlichungsdaten, Plattformprofile und Video-Freigabe umsetzen.
27. [ ] YouTube-Uploadadapter implementieren.
28. [ ] TikTok-Direct-Post-Adapter implementieren.
29. [ ] Instagram-Reels-Adapter über Meta implementieren.
30. [ ] Facebook-Video-/Reels-Adapter über Meta implementieren.
31. [ ] X-Medienupload und Post-Adapter nur nach separater Kostenfreigabe umsetzen.

### M5 – Produktionsreife und Übergabe

32. [ ] Zugriffe, Secrets, Eingaben, Dateipfade und externe Requests absichern.
33. [ ] Metriken, Logs, Alarmierung, Backups und Wiederherstellung einrichten.
34. [ ] Automatisierte Vertrags-, Integrations- und End-to-End-Tests ergänzen.
35. [ ] Installation und Betrieb auf unterstützten Systemen, Qwen-Bestandsprüfung, Handbuch und Rollback-Probe abschließen.

## 5. Qualitäts- und Abnahmeregeln

- **Freigabeschranken:** Ohne gültige Skriptfreigabe kein Produktionsjob; ohne Freigabe der konkreten finalen Datei keine Veröffentlichung. Bearbeitungen entwerten die betroffene Freigabe.
- **Medientyp:** Für `CLOUD` tragen sämtliche visuellen Szenen `AI_GENERATED_VIDEO`; für `LOKAL` sämtliche `STOCK_VIDEO`. Ein gemischtes Manifest wird vor Rendering abgewiesen.
- **Videoqualität:** ffprobe bestätigt Codec, Auflösung, Bildrate, Dauer, Audiostream und abspielbare Datei. Automatisierte Stichproben prüfen schwarze/leere Szenen, Stille und erkennbare Untertitel; fachliche Sichtprüfung bleibt Teil der Video-Freigabe.
- **Betrieb:** Ein fehlgeschlagener Job kann ab dem letzten gültigen Artefakt fortgesetzt werden. Doppelte Klicks oder Worker-Neustarts erzeugen kein zweites Video und keine unkontrollierte doppelte Veröffentlichung.
- **Transparenz:** Oberfläche zeigt verständliche Fehler sowie den Status jeder Plattform separat. API-Einschränkungen werden angezeigt und nicht als erfolgreicher öffentlicher Post dargestellt.
- **Schutz:** Dateien und Tokens sind nur berechtigten Benutzern zugänglich. Keine Schlüssel in Repository, Browser-Bundle oder Log. Datensicherung und Restore sind nachweislich getestet.

## 6. Hauptrisiken und Gegenmaßnahmen

| Risiko | Folge | Maßnahme / Entscheidungstor |
| --- | --- | --- |
| Plattform-App noch nicht freigegeben | Öffentliche automatische Veröffentlichung nicht möglich | Zugangs-/Auditbedarf in Aufgabe 02 dokumentieren; Konten und Anträge erst nach Videoabnahme in Aufgaben 25–31 bearbeiten. YouTube und TikTok können ungeprüfte Uploads auf privat beschränken. |
| Antigravity-Sitzung auf dem Installationsrechner nicht verfügbar oder Abo-Kontingent erschöpft | Skriptauftrag kann nicht automatisch beendet werden | Worker unter dem angemeldeten Benutzer mit Zugriff auf dessen Schlüsselspeicher starten und Headless-Lauf vor Inbetriebnahme prüfen; Fehler sichtbar machen und keine kostenpflichtige API als Fallback aktivieren. |
| Kostenpflichtige Plattform-API erforderlich | Widerspruch zur Null-Kosten-Vorgabe | Integration und echte Aufrufe bis zu einer ausdrücklichen Kostenentscheidung sperren; X ist derzeit kostenpflichtig. |
| Wan-Workflow passt praktisch nicht in Gratis-Guthaben oder Laufzeit | CLOUD-Modus vorerst nicht live prüfbar | In Aufgabe 05 Anforderungen dokumentieren und in Aufgabe 22 Kosten- und Laufzeitgrenzen einbauen. Aufgabe 24 nur bei bestätigten Credits und wirksamem Null-Nettokosten-Limit ausführen. Kein Modellwechsel ohne neue Produktentscheidung. |
| Lange Sprecherpassage bei kurzen Wan-Clips | Bild-/Tonlücken | Skriptplaner begrenzt Sprechlänge je Szene; weitere Wan-Clips derselben Szene erzeugen, bis Dauer gedeckt ist; vor Rendern Dauer prüfen. |
| Pexels findet keine passende/zulässige Quelle | Unvollständige Szene | Suchbegriffe verfeinern, Alternativen innerhalb Pexels prüfen, fehlende Szene zur Bearbeitung melden; keine AI-Quelle als Ersatz. Quellen und geforderte Pexels-Nennung dokumentieren. |
| Veröffentlichung nach Timeout mit unbekanntem Ergebnis | Doppelter Post | Externe Upload-/Post-ID dauerhaft speichern, Ergebnis abfragen und erst nach Abgleich wiederholen. |
| Plattformen verlangen abweichende Formate, Metadaten oder Upload-Wege | Upload scheitert | Profile je Plattform aus derselben freigegebenen Masterdatei erzeugen; lokalen Datei-Upload oder zeitlich begrenzten HTTPS-Abruf je Plattform prüfen. |
| Stockrechte oder Kennzeichnung von KI-Inhalten werden übersehen | Post muss korrigiert oder entfernt werden | Herkunft und erlaubte Verwendung dokumentieren; nötige Quellenangaben und Plattformfelder für synthetische Medien vor Freigabe prüfen. |
| Lokaler Speicher oder Redis/Worker fällt aus | Unterbrochene Produktion oder Datenverlust | Persistente Volumes, PostgreSQL-Zustand, Checkpoints, Backup/Restore, Wiederanlaufprobe. |

## 7. Produktentscheidung und Änderungskontrolle

Aufgabe 01 ist mit den konkreten V1-Startwerten und zwei Abnahmeideen in Abschnitt 2.3–2.4 abgeschlossen. Am 26. September 2026 wurde die Priorität geändert: zuerst Videos ohne laufende API-Kosten nachweisen, dann Social Media prüfen. Die frühere Vorgabe „echtes CLOUD-Video als letzter Schritt“ ist damit durch den früheren, kostenkontrollierten Test in Aufgabe 24 ersetzt. Die ursprüngliche manuelle Gemini-Pro-Übergabe aus Aufgabe 02 wurde auf ausdrücklichen Wunsch des Betreibers durch einen automatischen Antigravity-CLI-Aufruf ersetzt. Aufgabe 03 belegt mit vier echten Skripten, dass beide Modi gültige strukturierte Antworten liefern; der CLI-Prototyp lief mit einem angemeldeten Google-Konto und Pro-Modell ohne Gemini API. Die Abo-Zuordnung dieser CLI-Sitzung wird vor der Webintegration bestätigt. Technische Plattformgrenzen und tatsächliche Modal-Nutzung können weitere dokumentierte Anpassungen nötig machen.

Am 27. September 2026 war Codex Cloud als Entwicklungsort vorgesehen. Am 29. September 2026 wurde die Entwicklung auf dem aktuellen Windows-Rechner am GitHub-Repository festgelegt. Der Betreiber hat anschließend das Installationsziel erweitert: Die Anwendung soll auf **jedem unterstützten Windows-, macOS- oder Linux-Rechner** mit nötigen Werkzeugen und Anmeldung nutzbar sein; Ubuntu ist nur eine mögliche Wahl. Diese Produktentscheidung ändert feste Betriebssystemannahmen, nicht die fachlichen Abnahmekriterien. Unabhängig prüfbare Implementierungen dürfen mit kontrollierten Daten entwickelt werden; die Live-Abnahme von Schritt 10 und dem ergänzten Schritt 11 wurde am 30. September 2026 auf Windows nachgewiesen. Vor Social-Media-Arbeit müssen echte Videos auf einem vollständig eingerichteten Installationsrechner abgenommen sein. Keine Anmeldung oder `.env` wird durch Git übertragen. Die plattformübergreifende Installation und spätere Medienwerkzeuge sind in Aufgabe 35 zu prüfen.

## 8. Verifizierte Quellen und erneute Prüfung

Stand der Recherche: 26. September 2026. Vor Implementierung der jeweiligen Integration und vor Produktionsstart erneut prüfen, da APIs, Zugänge, Preise und Formate veränderlich sind.

- [Gemini 3.8 Flash, Modell-ID `gemini-3.8-flash`](https://ai.google.dev/gemini-api/docs/latest-model)
- [Gemini API: kostenloser Tarif und Abrechnung](https://ai.google.dev/gemini-api/docs/billing)
- [Google AI Pro und Antigravity: Abovorteile](https://support.google.com/googleone/answer/14534406?hl=en)
- [Antigravity CLI: Headless-Ausführung, JSON-Ausgabe und gespeicherte Anmeldung](https://antigravity.google/docs/cli/headless/)
- [ComfyUI: offizieller Wan-2.2-14B-T2V-Workflow](https://docs.comfy.org/tutorials/video/wan/wan2_2)
- [Wan 2.2: offizielles Repository und Modellanforderungen](https://github.com/Wan-Video/Wan2.2)
- [Modal: GPU-Konfiguration `A100-80GB`](https://modal.com/docs/guide/gpu)
- [Pexels API: Videosuche und Richtlinien](https://www.pexels.com/api/documentation/)
- [YouTube `videos.insert` und Beschränkung ungeprüfter Projekte](https://developers.google.com/youtube/v3/docs/videos/insert)
- [TikTok Direct Post: Voraussetzungen, `video.publish` und Audit](https://developers.tiktok.com/docs/en/content-posting-api-get-started)
- [Meta: offizielle Instagram-API-Sammlung](https://www.postman.com/meta/workspace/instagram/documentation/23987686-9386f468-7714-490f-9bfc-9442db5c8f00)
- [Meta: Facebook-Reels-Beispielsammlung](https://github.com/fbsamples/Facebook-Reels-Publishing-API-Postman-Collection)
- [X: offizielles Beispiel für Video-Medienupload](https://github.com/xdevplatform/samples/blob/main/python/media/media_upload_v2.py)
- [Piper: verfügbare deutsche Stimme `de_DE-thorsten-high`](https://huggingface.co/rhasspy/piper-voices/tree/main/de/de_DE/thorsten/high)
- [TikTok: unterstützte Videoformate und Bildraten](https://developers.tiktok.com/docs/en/content-posting-api-media-transfer-guide)
- [Modal: A100-80GB-Preisübersicht; vor Kostenfreigabe erneut prüfen](https://modal.com/pricing)
- [Modal: Budgets und Grenze für Nettokosten](https://modal.com/docs/guide/budgets)
