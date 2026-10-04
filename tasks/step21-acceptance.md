# Schritt 21 – Cloud-Szenen und Rücktransfer mit Testdaten

Stand: **05.10.2026. Abgeschlossen mit kontrollierten Testdaten.** Entwicklung/Prüfungen am 04./05.10.; Kriterien unverändert, kein echter Wan- oder Modal-Aufruf.

## Entwicklungsergebnis

- Strikte Wan-Auftrags-/Antwortmodelle mit festem Modell-/Workflow-Bezug, Prompt, Seed, UUID und eindeutig gekennzeichnetem `CONTROLLED_TEST`-Ursprung. Ausschließlich `AI_GENERATED_VIDEO`; Pexels-/andere Herkunft, Live-Antworten und manipulierte Aufträge werden abgewiesen.
- Mehrclip-Planung aus 81 Frames / 16 fps, stabile Kennungen über Wiederaufnahme, gespeicherte Auftragsabsicht vor Provideroperationen. Host-Prüfung des unveränderten Bundles aus 20.
- Rücktransfer in den konfigurierten Medienspeicher: begrenzte Bytes/Dateigröße, SHA-256, echtes ffprobe-Profil mit gezählten Frames und vollständiger CPU-Decode. Atomare Clipcheckpoints, Reparatur beschädigter lokaler Dateien, CPU-Zusammenführung zur geplanten Szenendauer und vollständiges Szenenmanifest.
- Produktionscheckpoints speichern UUID-Metadaten sicher als JSON. API ergänzt `wan_sources` beziehungsweise `production_wan_sources`; finale Ablage übernimmt diese Metadaten, wenn sie vorhanden sind. Keine Migration oder zusätzliche Abhängigkeit.
- Normale CLOUD-Produktion weiterhin sichtbar gesperrt. Kein produktiver Testdaten-Schalter, kein Modal-Import/Client, keine Kontoanmeldung. [Vertrag und Wiedereinstieg](cloud-transfer-contract.md).

## Kurze Prüfnachweise

1. **5 Wan-Tests** mit einem einmal lokal erzeugten blauen Testclip (81 Frames, 720 × 1280, 16 fps). Erfolg/Manifest, Wiederverwendung, korrupter Cache ohne zusätzlichen Auftrag, Transfer-Timeout mit unmittelbarer Testausnahme statt Wartezeit, falscher Provider/Auftrag, ausbrechender Pfad, Live-Herkunft, falscher SHA, Nicht-MP4-Datei und Abbruch vor/während Übernahme geprüft. Fehlende/vertauchte/gemischte Szenenmetadaten werden ebenfalls abgewiesen. Kein semantischer Bildqualitätsnachweis.
2. **7 gezielte bestehende Backendtests**: vier Encodingplan-, ein Stufenvertrags- und zwei Medienpfadtests bestanden. Zusammen mit den fünf neuen Tests und sieben Cloud-Bundle-Tests: **19/19 in 3,834 s**, keine übersprungen. Zehn Projekttests bestanden.
3. **Echte PostgreSQL-/Redis-/RQ-/Subprozessprüfung:** zwei neue Integrationsfälle und vier bestehende API-Vertragstests, **6/6 in 14,968 s**, keine übersprungen. Separates temporäres Schema und private Testqueue; eigene Medienablage im temporären Ordner. Sechs Szenen à sechs Sekunden, zwölf kontrollierte Clipaufträge. Abbruch nach SCENES, keine Sprach-/Grafik-/Gesamtvideoproduktion für diesen Test.
4. Erfolgsfall: SCENES vollständig gespeichert, sechs `AI_GENERATED_VIDEO`-Artefakte, Wan-Metadaten in Lauf-/Projektstatus, keine Pexels-Quellen. Wiederzustellung erhöht nicht die zwölf unterschiedlichen Clipaufträge und erzeugt keinen zweiten Produktionslauf.
5. Unterbrechungsfall: `WAN_TRANSFER_TIMEOUT`, **null Artefakte**, kein gültiges SCENES-Manifest. Wiederaufnahme mit unveränderter freigegebener Version verwendet dieselbe erste Auftragskennung; danach zwölf eindeutige Clipaufträge und sechs Artefakte. Keine `.part`-Reste. Der kontrollierte Transport wurde wieder verfügbar gemacht, das Skript nicht geändert.
6. `npm run build --prefix web`: bestanden. Keine Änderung am Webcode; vollständiger CLOUD-Browserlauf bleibt 23.
7. Lokale API neu gebaut/gestartet, Readiness und neue OpenAPI-Statusfelder unter `http://127.0.0.1:4177/` bestätigt. Normalen Hostworker ohne laufende Produktionsaufträge mit aktuellem Code neu gestartet; RQ-Zustand und tatsächlichen Prozess geprüft. Veraltete Registrierung des beendeten Workers blockierte zunächst den Start; nach Prozessprüfung/bereinigtem Ablauf wieder bereit. Kein Skript-/Videogenerierungsauftrag dafür ausgelöst.

Bei der Entwicklung gefunden und behoben: Der zunächst unvollständige Testpayload enthielt einen Gesamterzähltext, der nicht seinen Szenen entsprach (422, Produktvalidierung korrekt). Danach deckte die echte Integration die notwendige JSON-Konvertierung der neuen UUIDs auf; `StageResult.model_dump(mode='json')` behebt die Speicherung. Die finale Integrationsprüfung ist erfolgreich.

**Modal-Ressourcenverbrauch: 0.** Kein Modal SDK-Aufruf, Deployment, Image-Build, Remote-Volumezugriff, Modelldownload oder GPU-Test. Alle MP4s sind explizite lokale Farbflächen-Testdateien und verbleiben temporär/ignoriert. Lokale Hilfsdatei `.data/step21-tests.py` lädt nur Datenbank-/Redis-Konfiguration, ohne sie auszugeben. Prüfzeiten beziehen sich auf die erfolgreichen Läufe, nicht auf gesamte Entwicklungszeit.

## Noch offen

- 22: konfigurierbare Auftrags-/Kostenlimits, belastbare Kosten-/Kontonachweise vor GPU-Zuteilung. Keine Behauptung, dass ein Timeout oder gespeicherter Intent allein Modal-Kosten verhindert.
- 23: durchgehender CLOUD-Browserlauf mit Testantworten bis abspielbarer MP4 und gemischte-Manifeste-Prüfung.
- 24: tatsächlicher Remote-Provider samt atomarem Auftragsregister, Modal-Netzwerktransfer, Build, Gewichte, GPU-Inferenz und Qualitäts-/Kostenabnahme. Echte Wan-Ausführung verlangt verifizierte Gratis-Credits und wirksame 0 USD Nettokosten; keine automatische Nutzung des genannten 30-USD-Guthabens.
- 35: vollständige Installation/Betrieb auf weiteren unterstützten Rechnern. Ubuntu-Zugriff ist für 21 nicht erforderlich.
