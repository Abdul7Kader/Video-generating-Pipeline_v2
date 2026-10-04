# Schritt 18 – persistenter Speicher und Videoabruf

Stand: **04.10.2026 abgeschlossen**. Entwicklung und echte Prüfungen auf dem aktuellen Windows-Rechner. Weitere Betriebssysteme und vollständiger Betriebsübergang bleiben 35.

## Bedienung

„Speicher & Videos“ lässt den vollständigen Medienpfad direkt in der Weboberfläche ändern. Dateien werden vor Aktivierung kopiert und per SHA-256 geprüft; der tatsächliche geprüfte Anteil erscheint als Fortschrittsbalken. Alte Dateien bleiben erhalten. Fremde Ordner, verschachtelte Pfade, Verknüpfungen und abweichende Zieldateien werden abgewiesen. Der aktive Speicher bleibt bei Fehlern gültig. Wiederaufnahme läuft höchstens dreimal über einen persistenten PostgreSQL-/RQ-Auftrag.

Das erste Öffnen verlangt ein eigenes Betreiberpasswort; der entsperrte Zugang nutzt eine vier Stunden gültige HttpOnly-/SameSite-Sitzung. Fertige Videos erscheinen mit normalen Video-Steuerelementen und MP4-Download. Keine Zugangsdaten im Chat, Repository oder Artefakt-URL. In der normalen Installation ist das persönliche Passwort vom Betreiber noch erstmals selbst festzulegen; die Browserabnahme verwendet eine eigene Testdatenbank mit kontrolliertem Testpasswort.

## Ablage und Zugriff

Neue Quellen, Audio, Grafiken, Encode und Endablage liegen unter `projects/<id>/versions/<version>/runs/<run-id>/<stage>/`. Ältere gespeicherte relative Pfade bleiben lesbar und werden mitkopiert. Keine Änderung früherer Versionen oder Prüfsummen. STORAGE prüft alle Eingänge, den Encodingplan, Profil/Frames und vollständigen Decode, schreibt atomar FINAL-MP4 und das versionsgebundene Manifest. Erst anschließend wird der FINAL-Checkpoint veröffentlicht.

Ein schmaler Mediengateway des normalen nativen Hostworkers liefert höchstens 1-MB-Blöcke über Redis. Der API-Container benötigt keine wechselnde Host-Laufwerksfreigabe. Nur eine Artefakt-ID aus abgeschlossenem STORAGE wird aufgelöst; Manifest und MP4 werden vor Auslieferung geprüft. Sichere relative Pfade bleiben unter dem aktiven Medienroot. GET/HEAD, einzelne Bytebereiche, ETag und If-Range sind implementiert; Pfadmanipulation, unfertige und beschädigte Dateien werden abgewehrt. Der Worker muss auch zur Wiedergabe laufen.

Produktionsparent und Medienkind halten gemeinsame PostgreSQL-Sperren; Speicherübernahme benötigt die exklusive Sperre. Damit bleibt auch ein verwaister Medienprozess vor einem Speicherwechsel geschützt. Aktivierung aktualisiert die private Worker-Konfiguration atomar, auch bei reiner Umgebungsinstallation. Migration 0006 speichert Zugang und Übernahmehistorie; Rollback mit solchen Daten wird verweigert.

## Maschinenprüfungen

- **83 verschiedene Backendtests erfolgreich geprüft, keine übersprungen.** Der vollständige Lauf mit 81 Tests dauerte 583 s; zunächst drei historische Testannahmen fehlgeschlagen (zweimal Migration 5 statt 6, einmal alter Quellenpfad). Nach Anpassung bestehen neun gezielte Nachtests einschließlich echter Workerunterbrechung. Zwei zusätzliche Randfalltests und elf abschließende gezielte Prüfungen bestehen. Kein unveränderter Fehltest als bestanden gezählt.
- **Zehn Projekttests und `npm run build --prefix web` bestanden.** Docker-Web-Build ebenfalls bestanden. Kein neues Paket für den Medienspeicher nötig.
- Echte PostgreSQL-/Redis-/RQ-/Piper-/Remotion-/FFmpeg-Prüfung beider Modi mit ausdrücklich kontrollierten visuellen Testeingängen: vollständiger FINAL-Checkpoint, stabile Pfade, kein Medientypfallback, wirkliche MP4 und identischer Browserabrufhash. Dies ist keine echte Wan-/Modal-Abnahme.
- Zugriffstests: eigener Passwortzugang, HttpOnly/SameSite, falsches Passwort, fremder Origin, Logout, gefälschte Sitzung, unauthentifizierter Abruf, komplette Datei/HEAD, Präfix-/Suffix-/offener Bytebereich, ungültige/mehrfache Bereiche, If-Range, beschädigte und manipulierte Datei.
- Speicherübernahme: Leerzeichen/Umlaute, Hash/Bytezähler, Original erhalten, Cache/Teilübernahme, Redis-Ausfall vor Zustellung, fremder Zielordner und Konflikt. Kontrollierte Prozessunterbrechung direkt nach Konfigurationsaktivierung vor Datenbankabschluss: Wiederaufnahme beendet denselben Auftrag mit Versuch 2, keine zweite Kopie und identische Daten.
- Migration up/down/up und verlustfreier Rollbackschutz geprüft. Reine Umgebungsinstallation erzeugt private Konfiguration; spätere Rootänderung wird frisch gelesen.

## Normaler LOKAL-Auftrag

Projekt `501f8d0a-1bf6-4c6e-9516-9b2812178003`, freigegebene Version **4**, Lauf `dda12e48-d0ed-40cd-8e0b-647be2e0e59b`: bestehende SCENES/SPEECH/GRAPHICS/ENCODING unverändert, STORAGE in Versuch 2 erfolgreich, Gesamtstatus **COMPLETED**. Keine erneute Skriptsynthese, keine Fristverlängerung.

FINAL `ad381164-207a-5d53-948b-104d9748d9db`, **36 Sekunden / 864 Frames / 720 × 1280 / 24 fps / H.264/AAC / 13.212.947 Bytes**. SHA-256: `908ef72954ae0e1132b9c82f6d30fcbaa24dda7a262f4aee9eae9e8f66cdeab4`. 20 Eingangsartefakte und Manifest geprüft. Endablage unter dem Projekt-/Versions-/Laufpfad. Die drei Motive jeweils zweimal bleiben ausdrücklich Technik-Testmaterial; Inhalts-/Doppelungsprüfung folgt 19.

## Browser und Neustart

Echter isolierter Chrome, eigene PostgreSQL-Testdatenbank, gleiche entwickelte API/Webanwendung und reale Pexels-MP4 des normalen Auftrags: Zugang per Webformular, Abspielen bis **36/36 s**, Neuladen mit erhaltener Sitzung, Speicherwechsel per Webformular, geprüfte Aktivierung und Neuladen am neuen Pfad. Ungültiger Pfad lässt Eingabe und aktuellen Speicher erhalten. Verzögerte Antworten zeigen Ladebalken. **320 px: scrollWidth=clientWidth=320**, keine Konsolenfehler. Private Benutzerprofile und persönliche Passwörter wurden nicht benutzt.

Anschließend echter Neustart von **Web/API/PostgreSQL/Redis** und normalem Hostworker auf dem Installationsrechner. FINAL-ID, aktiver Pfad, Dateigröße, SHA-256 und sämtliche 20 Eingangshashes danach identisch. Keine Container-/Medienlöschung. Normale Dienste unter `http://127.0.0.1:4177/` bereit. Es wurde kein AI-Pro-, Gemini-API- oder Modal-Aufruf für diese Aufgabe ausgelöst.

Lokale ignorierte Nachweise: `.data/step18-tests.log`, `.data/step18-recheck.log`, `.data/step18-live-current.json`, `.data/step18-restart-result.json`, `.data/step18-browser-result.json`. Screenshots:

- [Speicher am Desktop](</C:/Users/aks/.codex/visualizations/2026/10/04/01a106ed-85e3-74d1-83fe-727091e5bfb0/step18-storage-desktop.png>)
- [Wirkliche Videowiedergabe](</C:/Users/aks/.codex/visualizations/2026/10/04/01a106ed-85e3-74d1-83fe-727091e5bfb0/step18-video-playing.png>)
- [Speicher bei 320 Pixeln](</C:/Users/aks/.codex/visualizations/2026/10/04/01a106ed-85e3-74d1-83fe-727091e5bfb0/step18-storage-mobile.png>)
- [Fehler und Entwurfserhalt](</C:/Users/aks/.codex/visualizations/2026/10/04/01a106ed-85e3-74d1-83fe-727091e5bfb0/step18-invalid-path-mobile.png>)

## Weiterarbeit

Nächster Schritt **19 – Produktionsstatus und Videoprüfung**, einschließlich Bildpassung und unbeabsichtigter Clipdoppelungen. CLOUD-Beschaffung/echter kostenbegrenzter Wan-Test bleiben 21–24. Allgemeine Authentifizierung/Härtung, Backup und vollständige macOS-/Linux-Installation bleiben 32/35. Noch keine Veröffentlichung an Social Media.
