# Schritt 13 – Produktionskette mit RQ

Stand: 30. September 2026. Implementiert, integriert geprüft und im echten Browser abgenommen. Schritt 13 orchestriert die Medienarbeit, die konkreten Pexels-/Piper-/Remotion-/FFmpeg-/Speicheradapter folgen in 14–18, der Wan-Adapter ab 21. Die normale Anwendung erzeugt weiterhin kein Video. Nächster Schritt: 14.

## Implementierung

- Migration 0003 speichert fünf geordnete `production_steps`: `SCENES`, `SPEECH`, `GRAPHICS`, `ENCODING`, `STORAGE`. Jeder Schritt hat Status, Versuchszähler, Zeitlimit, Fehlercode/-meldung und einen bestätigten Ergebnis-Checkpoint. `production_attempts` erhält den Verlauf jedes Versuchs mit Anfang, Ende und Fehlerursache.
- Freigabe und Wiederaufnahme werden vor Redis-Übergabe bestätigt. `QUEUED`-Läufe dienen als dauerhafte Zustellliste in PostgreSQL. Der angemeldete Hostworker prüft sie beim Start und im Leerlauf ungefähr alle fünf Sekunden. Eine verlorene Redis-Antwort und ein Abbruch vor Zustellung erzeugen keinen zweiten fachlichen Lauf. RQ-IDs enthalten Lauf-ID und bei Wiederzustellung eine fortlaufende Nummer; PostgreSQL bleibt die Quelle des fachlichen Status.
- Eine PostgreSQL-Sitzungssperre erlaubt nur eine aktive Ausführung pro Lauf über mehrere Checkpoint-Transaktionen hinweg. Jeder Medienprozess besitzt zusätzlich eine Schrittsperre. Ein nach Elternprozess-Abbruch noch lebender Medienprozess blockiert eine parallele Wiederaufnahme bis zu seinem eigenen Zeitlimit. Sperren werden beim Prozessende freigegeben. Danach zählt ein unterbrochener Schritt als fehlgeschlagener Versuch; bereits bestätigte Schritte bleiben erhalten.
- Pro Schritt höchstens **drei Versuche insgesamt**, einschließlich bewusster Wiederaufnahme. Nur ausdrücklich vorübergehende Fehler lösen automatische Wiederholung aus, mit fünf beziehungsweise 30 Sekunden Abstand. Fehlende Adapter werden nicht automatisch wiederholt. Wiederaufnahme setzt weder Versuchszähler noch die Gesamtlaufzeit zurück.
- Zeitlimits pro Versuch: Szenen 3.600, Sprache 300, Grafik 900, Encoding 1.800, Ablage 120 Sekunden. Gesamtlaufzeit ab erstem Start höchstens 10.800 Sekunden. Der Elternprozess überwacht Zeitlimit, Abbruch und aktuelle Skriptversion; der Kindprozess besitzt zusätzlich einen eigenen Watchdog. Prozessbäume werden bei Abbruch/Timeout beendet. Neue Skriptversionen stoppen den alten Lauf und benötigen eigene Freigabe.
- Artefakte erhalten deterministische IDs aus Schritt-ID und Ergebnisschlüssel sowie einen eindeutigen Datenbankindex. Artefakte und Schrittabschluss werden in einer Transaktion bestätigt. Bereits vorhandene Ergebnisse müssen bei Wiederaufnahme übereinstimmen. Relative portable Pfade werden geprüft; gemischte Quellen abgewiesen. Nur `STORAGE` darf ein finales Artefakt bestätigen; ohne finales Artefakt kein `COMPLETED`.
- API und Oberfläche bieten Schrittstatus, bewusste Wiederaufnahme innerhalb des verbliebenen Budgets und Abbruch. Ein abgebrochener, überholter, zeitlich abgelaufener oder vollständig ausgeschöpfter Lauf kann nicht wiederaufgenommen werden. Laufende Medienprozesse werden bei Abbruch gestoppt, erfolgreiche frühere Schritte bleiben gespeichert. Neue Bedienaktionen zeigen Ladebalken und sperren parallele Klicks.

Die konkreten Medienadapter müssen Dateien unter stabilen Schritt-/Ergebnispfaden atomar schreiben und bestehende Ergebnisse prüfen. Externe Aufträge brauchen zusätzlich eine persistente Anbieter-ID und ihre späteren Kostengrenzen; die Orchestrierung allein belegt keine idempotente Wan-/Modal-Ausführung. Persistenter Medienspeicher und berechtigtes Playback bleiben Schritt 18.

## Prüfnachweise

1. Migrationen 0001–0003 auf isoliertem PostgreSQL-Schema: Aufbau, vollständige Rückmigration und erneuter Aufbau bestanden. Migration 0003 auch im normalen Stack angewendet.
2. **37 Backendtests bestanden**, darunter sieben neue Produktions-Integrationstests mit PostgreSQL/Redis/RQ und ein Vertragstest. Beide Modi durchlaufen alle fünf Stufen mit kontrollierten Dateiergebnissen. Parallele Zustellung führt zu einer Ausführung; abgeschlossene Schritte werden nicht erneut ausgeführt.
3. Echter Testworker während `SPEECH` per Prozess-Kill beendet und anschließend neu gestartet. Der verwaiste Testprozess bleibt bis zu seinem begrenzten Ende gegen parallele Ausführung gesperrt. Danach automatische Fortsetzung: Versuchszähler **1/2/1/1/1**, genau fünf Dateien und fünf Artefakteinträge, kein `.partial`-Rest. Versuch 1 der Sprache bleibt als `WORKER_INTERRUPTED` dokumentiert, Versuch 2 ist abgeschlossen. Der Ersatzworker benötigt ein Beobachtungsfenster über Prozesslimit und Retry-Wartezeit hinaus; ein zunächst zu kurzer Test-Leerlauf wurde korrigiert, Produktionsgrenzen unverändert.
4. Vier-Sekunden-Testtimeout, Erfolg nach vorübergehendem Fehler, fünf-/30-Sekunden-Wartezeiten, Ende nach drei Versuchen, parallele Wiederaufnahme, Redis-Ausfall vor Zustellung, Abbruch vor Start und während eines echten Testprozesses, alte Skriptversion, Gesamtlaufzeitgrenze, falscher Medientyp, unbekannte/fremde Lauf-ID und ungültige Ergebnisfelder/Pfade geprüft. Kein doppeltes Artefakt bei Fortsetzung; keine Wiederaufnahme nach Abbruch oder verbrauchtem Budget.
5. **Acht Projekttests** und `npm run build --prefix web` bestanden. API/Web neu gebaut und lokal installiert, Hostworker nach Prüfung seines Leerlaufs aktualisiert; Health meldet Datenbank, Redis und Worker bereit.
6. **Browserabnahme bestanden:** Echte Chrome-Mausbedienung in isolierter API-/PostgreSQL-/RQ-Umgebung mit kontrollierten Stufen. LOKAL-Lauf `80ff845d-7976-471e-8904-7aa19c2132a1` und CLOUD-Lauf `17c09558-83f9-41f9-ba0e-df8885f76b57` nach bewusster Wiederaufnahme abgeschlossen, Versuchszähler jeweils 1/2/1/1/1. Genau eine Resume-Anfrage pro Doppelklick, eine Cancel-Anfrage bei Doppelklick, fünf sichtbare Schritte, Ladebalken und gesperrte Aktionen während verzögerter Antworten. Laufende Sprache abgebrochen, Fehler und Schritte nach Neuladen erhalten, keine JavaScript-Ausnahmen. 320/768/1200 Pixel gegen tatsächliche `clientWidth` inklusive Windows-Scrollleisten geprüft; eine feste Body-Mindestbreite, die bei 320 Pixeln einen Scrollrand verursachte, entfernt und erneut geprüft. Screenshots visuell geprüft und außerhalb von Git gesichert.

7. Normaler angemeldeter Hostworker: bestehender Pro-Lauf `e3dbcada-684a-4072-af87-4a78c427df37`, Version 2, über den neuen Resume-Endpunkt verarbeitet. Freigabe und Lauf-ID bleiben erhalten, fünf Schritte gespeichert, `SCENES` korrekt als `STAGE_UNAVAILABLE`/Versuch 1 beendet, null finale Artefakte. Keine neue CLI-/Medienausführung und kein automatischer Retry fehlender Adapter. Normale Browserauswahl unverändert.

Die isolierte Browser-API, Testworker, Chrome-Profil, Datenbankstruktur, RQ-Testmetadaten, temporären Skripte und Testdateien sind entfernt. Die normale Anwendung und Anmeldung bleiben erhalten.

Die Testdateien enthalten ausschließlich ausdrücklich gekennzeichnete Text-Fixtures, keine Videoerzeugung. Testadapter sind nur in Testprozessen ausgewählt; der normale Worker hat keinen Test-/Fallback-Schalter. Keine neuen Antigravity-, Pexels-, Modal-, GPU- oder Social-Aufrufe für diese Abnahme. Linux/macOS-Prozess- und Installationsabnahme bleibt Aufgabe 35; die aktuelle Prozessabnahme erfolgte auf Windows.

## Quellen und Wiederholung

- [RQ-Warteschlangen, Job-Timeout und Job-ID](https://python-rq.org/docs/), fest installierter Quellcode `rq==2.3.2`: neuere `unique=True`-Funktionen werden nicht vorausgesetzt.
- [PostgreSQL 17: Sitzungssperren](https://www.postgresql.org/docs/17/explicit-locking.html#ADVISORY-LOCKS).
- [Python 3.12: Subprozesse und Zeitlimits](https://docs.python.org/3.12/library/subprocess.html).

Mit privat gesetzten `DATABASE_URL`/`REDIS_URL` und `PYTHONPATH=backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/app -t backend -p 'test_*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s tasks -p 'test_*.py' -v
npm run build --prefix web
```

Die neuen Backendtests verwenden ein isoliertes Schema, eigene RQ-Queues und einen temporären Dateipfad; sie benötigen PostgreSQL und Redis. Der Produktions-Neustarttest startet und beendet ausschließlich eigene Testprozesse.
