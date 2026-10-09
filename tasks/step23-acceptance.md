# Schritt 23 – vollständiger CLOUD-Ablauf mit Testdaten

Stand: **09.10.2026. Funktionen vollständig geprüft; Bedienungs-/Browserabnahme durch Betreiber offen.**

## Auftrag und Ergebnis

Der Betreiber hat Punkt 2 beauftragt und übernimmt den Haupttest. Codex prüft Funktionen, Medientyptrennung und Build. Keine Browserbedienung oder Inhaltsabnahme durch Codex, keine öffentliche Bereitstellung und keine echte Wan-/Modal-Ausführung.

- Expliziter Testsubprozess `app.test_cloud_fixture`: ausschließlich SCENES verwendet den kontrollierten Wan-Provider aus 21; SPEECH, GRAPHICS, ENCODING und STORAGE verwenden die echten lokalen Adapter. Kein Testdaten-Schalter im normalen Worker und kein produktiver Provider-Fallback.
- Echte API-Skriptfreigabe → PostgreSQL → Redis/RQ → fünf isolierte Produktionsstufen → gespeicherte finale MP4 → geschützter HTTP-Abruf nachgewiesen. Lokale CPU-Piper-Stimme, echtes Remotion-Rendering und FFmpeg/ffprobe; kein Ersatz dieser Stufen durch Ergebnis-Stubs.
- Encoding weist zusätzlich widersprüchliche Herkunftsmetadaten zurück: CLOUD mit Pexels-Quellen beziehungsweise LOKAL mit Wan-Quellen. Vorhandene Wan-Manifeste werden gegen die freigegebenen Szenen erneut validiert. Gemischte Artefakt-Medientypen stoppen vor FFmpeg; Endablage verwendet dieselbe Eingangsprüfung.
- Weboberfläche zeigt Cloud-Szenen, Clipzahl und Dauer. `CONTROLLED_TEST` wird ausdrücklich als Testclip ohne echte Wan-Generierung bezeichnet. Bedienung/Anzeige noch durch Betreiber prüfen; lediglich TypeScript/Web-Build automatisch nachgewiesen.

## Tatsächliche Nachweise

1. **Vollständiger neuer Integrationsfall erfolgreich:** sechs Szenen à sechs Sekunden, zwölf kontrollierte Rohclipaufträge. Alle fünf Stufen `COMPLETED`, jeweils ein Versuch; ausschließlich `AI_GENERATED_VIDEO` als visuelle Eingänge, keine Pexels-Quellen. Vollständige Wan-Herkunft bis ins FINAL-Manifest und Projektstatus erhalten.
2. Finale Datei: **36 s, 864 Frames, 720 × 1280, 24 fps, H.264/AAC, 360.406 Bytes**. Vollständiges ffprobe-/Decodeprofil und SHA-256 geprüft: `cf56df41eacc1cb9827c23f82ce853b4c3931ee548dd9287c2229bcfd5eb9c58`. Dies ist eine blaue Farbflächen-Testdatei mit deutscher Testsprache und Untertiteln; keine Wan-Bildqualitätsprobe.
3. Videoabruf ohne Sitzung `401`; mit isoliertem Testzugang vollständige MP4 `200` mit passender Prüfsumme, HEAD mit korrekter Dateilänge, Bytebereich `206` mit exakt passenden Bytes. Wiederholte Skriptfreigabe und Zustellung behalten dieselbe Laufkennung, genau ein FINAL und unveränderte MP4-Dateizeiten. Keine Social-Publikation und keine Video-Freigabe gesetzt.
4. Neuer negativer Integrationsfall erfolgreich: Clipgrenze vor Providerarbeit → `WAN_CLIP_LIMIT`, keine Anbieteraufträge/Artefakte. Wiederaufnahme nach abgelaufener ursprünglicher Cloud-Frist → `WAN_RUNTIME_LIMIT`, weiterhin keine Anbieteraufträge/Artefakte. Der erste Prüflauf erwartete versehentlich HTTP `202`; der bestehende Resume-Vertrag liefert korrekt `200`. Testannahme korrigiert und gezielt erfolgreich nachgeprüft.
5. **Acht verschiedene echte Integrationsfälle erfolgreich geprüft:** ein kompletter neuer Videoablauf; danach sieben fokussierte Fälle in **18,119 s** (neuer negativer Grenz-/Resume-Fall, zwei bestehende Wan-Transferfälle, vier API-Vertragsfälle). Der erste Lauf mit beiden neuen Fällen dauerte **64,842 s** und enthielt den oben genannten Testannahmefehler; kein vollständig grüner gemeinsamer Acht-Test-Lauf behauptet. Keine Tests übersprungen. Damit ist auch die zuvor fehlende kurze Dienstintegration zu 22 nachgewiesen.
6. **30/30 gezielte Funktionen/Verträge in 10,589 s**, keine übersprungen: Clip-/Kosten-/Parallelitätsgrenzen, Wan-Transfers, Encodingplan, gemischte Artefakte vor FFmpeg, Pfade, Stufen- und Cloud-Bundle-Verträge. Neue rote Herkunftsprüfung reproduzierte zunächst die fehlende Abweisung und besteht nach der Korrektur.
7. `npm run build --prefix web` bestanden. Keine Browser-/Sichtprüfung durch Codex und kein neuer Gesamtbackend-Lauf behauptet.

Belege bleiben ignoriert: `.data/step23-integration.log`, `.data/step23-focused.log`, `.data/step23-functions.log`. Für den Haupttester erhalten: `.data/step23-preview/CONTROLLED_TEST-cloud.mp4` und `manifest.json`. Die Projekt-/Laufkennungen darin stammen aus dem entfernten Testschema; sie sind keine Projekte der normalen Betreiber-Datenbank.

## Testumgebung und Sicherheit

Docker Desktop war beendet und wurde für die Funktionsprüfung gestartet. Zwei eigene wegwerfbare Container aus bereits vorhandenen `postgres:17-alpine`/`redis:7-alpine`-Images, ausschließlich Loopback-Ports 15433/16380; keine Betreiber-Container oder Betreiber-Datenbank gestartet/geändert. Die anfängliche Testdatenbank ohne Passwort wurde vor dem Testlauf durch eine Instanz mit zufälligem Zugang ersetzt. Zugang über den vorhandenen privaten Schreibmechanismus, nur in ignorierter temporärer Konfiguration, keine Ausgabe der Zugangsdaten. Redis enthielt ausschließlich isolierte Testqueues. Testschemas, Testcontainer und temporäre Dienst-Zugangskonfiguration nach Abschluss entfernt; Testvideo/Prüflogs erhalten. Docker Desktop bleibt gestartet.

Schutzbedarf/Vertrauensgrenzen: freigegebene Szenen und Herkunftsdaten, private Medienablage, API-Sitzung und untrusted Providerantworten. Geprüfte Missbrauchsfälle: Mischquellen in Artefakten/Metadaten, doppelte Zustellung, Grenzüberschreitung, Fristverlängerung bei Resume, unberechtigter Videoabruf. Keine Abschwächung der normalen Kosten-/Login-/Dateikontrollen. Keine neuen Abhängigkeiten oder Migrationen.

**Modal-Verbrauch 0:** kein Modal-Client, GPU, Deployment, Remote-Build, Gewichtsdownload oder Remote-Volumezugriff. Piper verwendet das bereits vorhandene lokale Stimmenmodell. Normale CLOUD-Produktion bleibt gesperrt.

## Wiederholung und offene Abnahme

Für eine erneute sachlich notwendige Funktionsprüfung `DATABASE_URL` und `REDIS_URL` sicher für eine erreichbare isolierte Testumgebung bereitstellen; vorhandene lokale Piper-/Remotion-/FFmpeg-Voraussetzungen erforderlich. Keine Zugangsdaten aus diesem Bericht übernehmen. `PGCONNECT_TIMEOUT=3` begrenzt fehlende Dienstverbindungen.

```text
PYTHONPATH=<absoluter Backendpfad>
python -m unittest app.test_cloud_production.CloudProductionTest -v
npm run build --prefix web
```

Optionaler Test-Preview-Export: `CLOUD_TEST_PREVIEW_DIR` als absoluter Pfad innerhalb des ignorierten Projektordners `.data`; ausschließlich vom Testcode ausgewertet. Ohne Export bleiben Medien temporär. Der normale Worker wertet diese Variable nicht aus.

Offen: Betreiber-Bedienungs-/Browserabnahme einschließlich Wiedergabe und verständlicher Testkennzeichnung. Erst danach beziehungsweise getrennt in 24 echte Wan-Ausführung mit tatsächlichen Credits-/Budget-/0-USD-Nettokosten-Nachweisen, Remote-Idempotenz und Qualitätsabnahme. Kein echter GPU-Auftrag durch diesen Schritt autorisiert.
