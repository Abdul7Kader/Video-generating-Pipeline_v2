# Schritt 16 – Remotion-Grafikvorlagen

Stand: 01.10.2026, auf ausdrücklichen Betreiberwunsch **pausiert**. Implementierung gespeichert; Dienst- und Browserabnahme noch offen. Schritt 16 ist nicht abgeschlossen.

Letzter Prüfstand der gesamten Backend-Suite: 65 Tests entdeckt, **32 bestanden und 33 Diensttests übersprungen**. Kein vollständiger Integrationsnachweis. Zehn Projekttests und Web-Build bestanden. Code-Zwischenstand ist als `271c323` auf GitHub gesichert (01.10.2026); Pull war bereits aktuell. Pausen-/Fortsetzungsdokumentation wird zusätzlich versioniert. Die Entwicklung bleibt pausiert. [Fortsetzungsanleitung](../STATE.md#pause-und-genauer-wiedereinstieg).

## Ergebnis

- Remotion 4.0.532 rendert lokal einen Titel und einen Untertitel je Szene als transparente PNG-Ebenen, einschließlich Szenenzähler und Fortschrittsgrafik.
- Fester Rahmen: 720 × 1280, 24 fps, lokale Noto-Sans-Schrift, sichere Ränder 64/112/96/240 Pixel. Gemessene Textgrenzen verhindern Abschneiden und gegenseitige Überdeckung. Titel bis vier Sekunden, Untertitel szenengenau aus tatsächlicher Piper-Dauer; geplante Haltezeiten bleiben erhalten.
- Typisiertes Manifest, Hash-/WAV-/PNG-Prüfungen, atomare Speicherung und Cache-Wiederaufnahme. `GRAPHICS_OVERLAY` ist ein neutrales Zwischenartefakt; die visuellen Quellenregeln für LOKAL/CLOUD bleiben verbindlich.
- Migration 0005 ergänzt den Medientyp mit Modus-/Artefaktprüfung und verweigert verlustbehaftetes Rollback. API und UI zeigen Grafikprofil, Anzahl und Untertitelzeiten. Kein finales Video; Encoding und Auslieferung bleiben 17/18.

## Bisherige Prüfnachweise

- Drei Timingtests bestanden: beide Modi, Audioframes/Haltezeiten, geänderte/fehlende/doppelte Sprachmetadaten, zu lange Gesamtdauer.
- Echter lokaler Renderer mit beiden Modi: sieben PNGs je Lauf, Cache ohne Node-Aufruf, beschädigte PNG erkannt und neu gerendert, beschädigtes Audio blockiert. Vier Grafiktests bestanden; die verwendeten Audiodaten in dieser isolierten Prüfung sind ausdrücklich kontrollierte WAVs.
- Tatsächliche PNG-Proben mit langem Titel, kurzer Zeile, 400 Zeichen deutschem Fließtext und `ÄÖÜ äöü ß <Text> & "Anführungszeichen"` gerendert. ffprobe bestätigt 720 × 1280/RGBA; Sichtprüfung zeigt vollständige Zeichen, Zeilenumbruch und sichere Ränder. Titel: 32 px, Rechteck (64,96)–(608,374.94); lange Untertitel: 28 px, (64,449.61)–(608,1040). Unlesbarer Extremfall aus 400 ungetrennten `W` wird ausdrücklich abgewiesen.
- Zehn Projekttests und `npm run build --prefix web` bestanden. `npm install --prefix graphics` meldet null Sicherheitsbefunde. Abhängigkeiten über Lockfile fixiert; heruntergeladener Browser, Medien und Modelle sind ignoriert.

## Noch offen

- Migration up/down/up, PostgreSQL-/Redis-/RQ-/echte Piper-/Remotion-Integration, normaler Produktionslauf und echte Browserabnahme einschließlich Neuladen und 320 Pixeln.
- Grund: Docker Desktop startet am 01.10.2026 nicht; `docker-secrets-engine/engine.sock` kann nicht umbenannt werden. PostgreSQL-Verbindungsprüfung läuft in Timeout. Betreiber wurde um vollständiges Beenden und Administratorstart gebeten und hat stattdessen Dokumentation und Pause angeordnet. Keine Containerdaten gelöscht und kein Abnahmekriterium herabgesetzt.
- Die vorbereiteten Integrationsprüfungen liegen in `backend/app/test_graphics_production.py`. Ohne erfolgreiche Abnahme bleiben Schritt 16 und dessen Haken offen. macOS-/Linux-Installation weiter Aufgabe 35; kein Modal-/Pro-/bezahlter API-Aufruf für die Grafikentwicklung.

## Implementierungsentscheidung

Statische, wiederverwendbare Remotion-Ebenen mit framegenauem Manifest halten Renderzeit und Speicher gering. Schritt 17 legt sie anhand derselben Zeitdaten über die geprüften Szenen. Eine zusätzliche große Zwischenvideodatei oder PNG-Bildfolge pro Frame ist für die festgelegten statischen Texte nicht nötig. [Installation und Vertrag](../graphics/README.md).
