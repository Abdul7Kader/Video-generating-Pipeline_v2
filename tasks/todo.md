# Aufgaben und Abnahmekriterien – Version 1

Bezug: [Umsetzungsplan](plan.md). Reihenfolge ist verbindlich, soweit Abhängigkeiten angegeben sind. Größen: S = ein fokussierter kleiner Schritt, M = ein fokussierter Funktionsabschnitt. Ein Haken wird erst nach der genannten Prüfung gesetzt. Externe Plattformfreigaben bleiben offen, bis ein echter öffentlicher Upload belegt ist.

**Fortsetzung ab 28. September 2026:** Aufgaben 01–09 sind abgeschlossen; Entwicklung ab Aufgabe 10 in Codex Cloud am GitHub-Repository. [STATE.md](../STATE.md) enthält die Übergabe. `LOKAL` ist der Pexels-Videomodus und keine Vorgabe für einen lokalen Entwicklungsrechner. Eine Cloud-Entwicklungsumgebung ersetzt nicht den später benötigten Remote-Testbetrieb für echte Skript- und Videoproben.

## M0 – Machbarkeit und Vertrag

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
- **Prüfung:** [API-Vertrag](api-contract.md) mit Beispielpayloads; OpenAPI- und HTTP-Vertragstests gegen isoliertes PostgreSQL-Schema bestanden (3 Tests), darunter idempotente Skript-/Videofreigaben; dazu 4 Datenbanktests, 8 bestehende Python-Tests, Web-Build und gesunder Compose-Stack. Produktionslauf wird als `QUEUED` gespeichert; RQ-Ausführung folgt in Aufgabe 12/13. Medieninhalt liefert bis Aufgabe 18 ausdrücklich `501`; Veröffentlichungsaufträge folgen in Aufgabe 26.

### 09. Idee- und Modusformular (S; abhängig von: 08)
- [x] React erfasst Idee und Dropdown `CLOUD`/`LOKAL` und zeigt den gewählten Medientyp an.
- [x] Fehlerhafte oder leere Eingaben werden verständlich abgewiesen.
- **Prüfung:** Echter Chrome-Browserlauf gegen den gesunden Fünf-Container-Compose-Stack: Leere Idee abgewiesen; `CLOUD` → `AI_GENERATED_VIDEO` und `LOKAL` → `STOCK_VIDEO`; beide Projekte über das Formular angelegt, aus PostgreSQL geladen und nach Neuladen erneut angezeigt. Web-Build und Python-Tests bestanden. Die UI erzeugt noch kein Skript und kein Video.

### 10. Automatische Gemini-Pro-Skriptintegration (M; abhängig von: 03, 07–08)
- [ ] Die Oberfläche startet aus Idee und Modus einen Hintergrundauftrag. Ein Worker ruft Antigravity CLI mit der Google-AI-Pro-Anmeldung auf, validiert und speichert Skript und geordnete Szenen; kein beliebiger Freitext wird als valides Skript akzeptiert. Codex und manuelles Kopieren sind zur Laufzeit nicht erforderlich.
- [ ] Ungültige oder unvollständige Antworten, fehlende Anmeldung und erschöpftes Kontingent führen zu verständlichen Fehlern mit bewusster Wiederholung. Automatische AI-Credit-Überziehung ist nachweislich deaktiviert; es gibt keinen stillen Wechsel zu einer kostenpflichtigen API.
- **Prüfung:** Cloud-Entwicklung mit kontrollierten Antworten; Live-Abnahme erst auf einem erreichbaren Worker mit eigener, bestätigter Google-AI-Pro-/Antigravity-Anmeldung: Idee im Browser absenden, ohne weitere Eingabe echtes Skript erhalten und bearbeiten; kontrollierte Fehlerfälle. Kein Gemini-API-Aufruf. Die lokale Anmeldung des früheren Entwicklungsrechners ist kein Cloud-Zugang.
- **Zwischenstand 29.09.2026:** Automatischer UI-Auftragsstart, PostgreSQL-Speicherung, Redis/RQ-Transport, Modusvalidierung, Fehleranzeige und bewusster Retry implementiert. Sieben gezielte Tests bestanden, darunter echter Redis→RQ→PostgreSQL-Durchlauf mit kontrollierter Antwort. Web-Build und Compose-Start bestanden; echter HTTP→Worker-Auftrag endete ohne bestätigte Kostensperre erwartungsgemäß mit `CREDIT_GUARD_UNVERIFIED`. Die Live-Abnahme samt CLI-Installation, Pro-Anmeldung und Kostensperre auf einem Remote-Worker bleibt offen; beide Haken bleiben deshalb offen.

### 11. Skript- und Szeneneditor (M; abhängig von: 08, 10)
- [ ] Benutzer sieht und bearbeitet Sprechertext, Szenen, Bildbeschreibungen sowie Prompts/Suchbegriffe.
- [ ] Speichern erzeugt eine neue Version; Validierung und Konflikte sind sichtbar.
- **Prüfung:** Browserprobe: bearbeiten, neu laden, Version prüfen.

### 12. Skriptfreigabe (S; abhängig von: 07, 11)
- [ ] Freigabe referenziert eine unveränderliche Skriptversion und stößt genau einen Produktionslauf an.
- [ ] Wiederholter Klick und spätere Bearbeitung umgehen die Freigabe nicht.
- **Prüfung:** API- und Browserprobe mit Doppelklick und Versionswechsel.

**Checkpoint M1:** [ ] Idee → automatisch erzeugtes Gemini-Pro-Skript → Bearbeitung → Skriptfreigabe ist im Browser ohne Codex demonstrierbar.

## M2 – Lokaler Produktionspfad

### 13. Produktionskette mit RQ (M; abhängig von: 07, 12)
- [ ] Szenenbeschaffung, Sprachsynthese, Grafik, Encoding und Ablage sind getrennte, wiederaufnehmbare Schritte.
- [ ] Status, begrenzte Wiederholungen, Timeouts und Fehlerursachen werden in PostgreSQL geführt.
- **Prüfung:** Worker während eines Testlaufs stoppen und ohne doppelte Artefakte fortsetzen.

### 14. Pexels-Szenenbeschaffung (M; abhängig von: 04, 13)
- [ ] Jede LOKAL-Szene erhält ausschließlich einen geeigneten Pexels-Clip samt Asset-ID und Herkunft.
- [ ] Kein Treffer führt zu einem sichtbaren Fehler/Änderungsbedarf, nicht zu einem Wan-Aufruf.
- **Prüfung:** Erfolgs- und Kein-Treffer-Test; Manifest enthält nur `STOCK_VIDEO`.

### 15. Piper-Sprachsegmente (S; abhängig von: 13)
- [ ] Sprechertext wird satz- oder szenenweise in Audio umgewandelt; Dauer je Segment wird erfasst.
- [ ] Leere oder fehlgeschlagene Sprachausgabe blockiert den Renderjob nachvollziehbar.
- **Prüfung:** Testtext anhören und Dauer per ffprobe mit Segmentdaten vergleichen.

### 16. Remotion-Grafikvorlagen (M; abhängig von: 01, 15)
- [ ] Titel, satz-/szenengenaue Untertitel und grafische Elemente werden aus gespeicherten Daten gerendert.
- [ ] Vorlagen funktionieren für gewähltes Format, sichere Ränder und Sonderzeichen.
- **Prüfung:** Render-Beispiele für kurze/lange Zeilen und deutsche Umlaute visuell prüfen.

### 17. FFmpeg-Pipeline (M; abhängig von: 14–16)
- [ ] Clips werden auf Zielprofil normalisiert, zeitlich an Sprechertext angepasst, mit Grafik/Audio zusammengesetzt und encodiert.
- [ ] ffprobe validiert jeden Eingang und die finale MP4; defekte oder zu kurze Quellen stoppen den Schritt.
- **Prüfung:** Ein komplettes LOKAL-Testvideo ansehen und technische Sollwerte maschinell vergleichen.

### 18. Persistenter Medienspeicher im Remote-Testbetrieb (S; abhängig von: 07, 17)
- [ ] Masterdatei, Zwischenartefakte und Manifest liegen unter stabilen Projekt-/Versionspfaden auf persistentem Speicher eines erreichbaren Remote-Testbetriebs, vorzugsweise des geplanten Ubuntu-Servers. Der bisherige Entwicklungsrechner ist nicht erforderlich.
- [ ] Browserabruf ist berechtigt und unterstützt Videowiedergabe; Pfadmanipulation wird abgewehrt.
- **Prüfung:** Remote-Adresse und Zugriffsweg sind eingerichtet; Containerneustart, Dateiprüfsumme und Browser-Playback über diese Adresse geprüft. Aufgabe 35 behandelt danach Backup, Härtung und endgültige Betriebsübergabe.

### 19. Produktionsstatus und Videoprüfung (S; abhängig von: 13, 18)
- [ ] React zeigt laufende Schritte, Fehler und das fertige Video zur Prüfung an.
- [ ] Bis zur Videofreigabe wird kein Publikationsjob erzeugt.
- **Prüfung:** End-to-End-Browserlauf im LOKAL-Modus.

**Checkpoint M2:** [ ] Ein fertiges Video im Modus `LOKAL` mit ausschließlich Pexels-Szenen liegt im Remote-Testbetrieb und ist über dessen Weboberfläche abspielbar.

## M3 – Cloud-Produktionspfad

### 20. Modal-Workflow ohne Generierung vorbereiten (M; abhängig von: 05, 13)
- [ ] Versionierter ComfyUI-Wan-Workflow mit expliziter `A100-80GB`-GPU und reproduzierbaren Modellgewichten ist vorbereitet.
- [ ] Keine lokale Wan-Installation ist Teil des Ubuntu-Compose-Stacks.
- **Prüfung:** Workflow-Datei, Abhängigkeiten und Deploy-Konfiguration statisch prüfen; keine Inferenz auslösen.

### 21. Cloud-Szenen und Rücktransfer mit Testdaten anbinden (M; abhängig von: 18, 20)
- [ ] Die CLOUD-Schnittstelle akzeptiert ausschließlich Wan-Ergebnisse; Beispielclips und Metadaten gelangen geprüft in den konfigurierten Medienspeicher des Remote-Testbetriebs.
- [ ] Ein abgebrochener Transfer erzeugt weder gültiges Artefakt noch duplizierten Auftrag.
- **Prüfung:** Erfolgs-, Timeout- und beschädigte-Datei-Proben mit kontrollierten Antworten und Testdateien; Manifest enthält nur `AI_GENERATED_VIDEO`. Keine echte Wan-Generierung.

### 22. Cloud-Grenzen (S; abhängig von: 21)
- [ ] Maximale Clipzahl, Laufzeit, Parallelität und Kostenlimit sind konfigurierbar und werden vor teuren Aufträgen geprüft.
- [ ] Vor einem echten GPU-Auftrag werden verfügbare Modal-Credits, Workspace-Budget und die Grenze für Nettokosten geprüft. Ohne nachgewiesene Null-Nettokosten-Grenze kein Live-Auftrag.
- [ ] Modell-/GPU-Fehler bleiben sichtbar und lösen keinen Pexels-Fallback aus.
- **Prüfung:** Grenzwert- und Fehlerfalltests.

### 23. CLOUD-Ablauf mit Testdaten prüfen (M; abhängig von: 15–19, 21–22)
- [ ] Skriptfreigabe durchläuft den CLOUD-Pfad mit kontrollierten Wan-Antworten und Beispielclips bis zum Video im Remote-Testbetrieb.
- [ ] Renderer weist absichtlich gemischtes Manifest zurück.
- **Prüfung:** Browserlauf und maschineller Manifest-/ffprobe-Test mit Testdaten; kein echter Cloud-Generierungsaufruf.

### 24. Erstes echtes CLOUD-Video und Videoabnahme (M; abhängig von: 19, 23)
- [ ] Ein reales LOKAL-Video ist bereits gespeichert und im Browser abspielbar; der CLOUD-Pfad wurde mit kontrollierten Testdaten geprüft.
- [ ] Kontoinhaber bestätigt verfügbares Modal-Gratis-Guthaben, Zahlungsmethode für GPU und wirksames Limit von 0 USD Nettokosten; der geschätzte Ressourcenverbrauch liegt innerhalb des Guthabens. Fehlt ein Nachweis, bleibt der Live-Lauf gesperrt.
- [ ] Modal erzeugt mit `A100-80GB`, ComfyUI und Wan 2.2 T2V-A14B die Szenen für Beispiel B. Das fertige Video liegt im Remote-Testbetrieb und ist über dessen Weboberfläche prüfbar; Aufgabe 35 schließt den produktiven Betrieb ab.
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
- [ ] Browser-End-to-End-Pfade laufen für LOKAL mit realen Artefakten im Remote-Testbetrieb und für CLOUD mit kontrollierten Antworten; der bereits absolvierte echte CLOUD-Lauf ist dokumentiert.
- **Prüfung:** CI/Build und Tests auf frischem Stand erfolgreich.

### 35. Ubuntu-Deployment und Handbuch (M; abhängig von: 32–34)
- [ ] Compose-Deployment mit persistenten Volumes, TLS-Zugang, Secrets, Migrationen und Healthchecks dokumentiert.
- [ ] Auf dem Ubuntu-Produktionsrechner vorhandenes Qwen-Modell und Hardware ermitteln; nur falls kein geeignetes Modell vorhanden ist, dort ein sinnvoll lauffähiges Qwen-Modell installieren. Qwen wird nicht als Videogenerator eingesetzt.
- [ ] Update, Rollback, Backup, Restore und Störungsbehebung sind ausführbar beschrieben.
- **Prüfung:** Deployment- und Rollback-Probe auf Ubuntu-Staging; für erneute Wan-Inferenz gelten weiterhin die Kostenregeln aus Aufgabe 24.

**Checkpoint Video-MVP:** [ ] Nach Aufgabe 24 sind beide Modi real geprüft und Videos im Browser abspielbar. **Checkpoint Veröffentlichung:** [ ] Nur ausdrücklich aktivierte, kostenfrei nutzbare oder gesondert freigegebene Plattformen sind real geprüft; übrige Plattformen bleiben als offen ausgewiesen.
