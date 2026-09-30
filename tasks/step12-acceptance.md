# Schritt 12 – Skriptfreigabe: Abnahme

Stand: 30. September 2026. Implementiert und auf dem aktuellen Windows-Rechner geprüft. Verbindliche Kriterien aus [todo.md](todo.md) bleiben unverändert.

## Ergebnis

- Browserfreigabe nennt und bestätigt exakt die angezeigte unveränderliche Skriptversion. Während Bearbeitung, Freigabe und unvollständigem Laden ist die Freigabe gesperrt.
- PostgreSQL speichert genau eine Freigabe und einen Lauf pro Version. RQ erhält den Auftrag erst nach Commit; Projekt-Sperren serialisieren Übergabe und Wiederholungen. Job-ID entspricht der Lauf-ID. Ein vorhandener Job wird erneut gelesen, nicht nochmals eingereiht. RQ-Ergebnisse bleiben mit `result_ttl=-1` erhalten; Bereinigung gehört zum späteren Betriebskonzept.
- Redis-Fehler liefert `503 QUEUE_UNAVAILABLE`: gespeicherte Freigabe bleibt bestehen. Wiederholung derselben Version übergibt denselben Lauf. Auch verlorene Antwort nach bereits erfolgreicher Übergabe erzeugt keinen zweiten Queue-Eintrag.
- Neue Skriptversion ist unfreigegeben. Alte Version kann nicht erneut freigegeben werden (`409`). Der Worker prüft die aktuelle Version unter derselben Projekt-Sperre und stoppt einen überholten Auftrag.
- Der aktuelle Worker-Einstieg setzt einen gültigen Auftrag ausdrücklich auf `FAILED`: „Die Videoerzeugung ist noch nicht verfügbar. Deine Skriptfreigabe bleibt gespeichert.“ Keine Medienaufrufe, kein fertiges Video, keine Artefakte und kein simulierter Produktionserfolg.

## Nachweise

1. Vier neue [Integrationstests](../backend/app/test_approval.py) mit echter PostgreSQL-/Redis-/RQ-Verarbeitung und Windows-Host-Worker: gleichzeitige Klicks, Brokerfehler vor/nach Übergabe, beide Modi und Versionswechsel. Vor Implementierung schlugen sie an den fehlenden Queue-/Statusfunktionen fehl; anschließend bestanden sie.
2. Gesamte Backendsuite: **29 Tests bestanden**, acht Projekttests bestanden; `npm run build --prefix web` erfolgreich. Keine Datenbankmigration nötig; bestehende unveränderliche Freigaben und Zustandsregeln bleiben wirksam.
3. Echter isolierter Chrome-Browser über DevTools-Protokoll, Compose-Teststack `step12-check`, Web-Port `14178`: LOKAL und CLOUD mit vollständigen kontrollierten Skripten. Doppelklick sendet jeweils einen Freigabe-Request. Neuladen erhält die Freigabe. Bearbeitung erstellt Version 2 ohne Freigabe; Version 1 bleibt unverändert, ihre Freigabe ergibt `409`. Version 2 erhält eine eigene Lauf-ID. PostgreSQL und Redis bestätigen jeweils genau einen Lauf und einen Queue-Eintrag pro freigegebener Version.
4. Echter Worker verarbeitet diese Browseraufträge: überholte Version 1 wird gestoppt, aktuelle Version 2 zeigt die fehlende Produktionsfunktion. Null Artefakte; UI zeigt gespeicherte Freigabe und Fehler nach Neuladen. Keine JavaScript-Ausnahmen, bei 390 Pixeln Breite kein horizontaler Überlauf; Darstellung visuell geprüft.
5. Zusätzliche Browserfehlerprobe mit kontrolliertem `503` beim Skriptladen: Freigabe gesperrt, erfolgreicher Reload gibt sie wieder frei. Eine parallel gespeicherte neue Version führt beim Freigeben der alten Ansicht zu sichtbarem Versionskonflikt ohne Freigabe der neuen Version.
6. Normale Anwendung unter `http://127.0.0.1:4177/`: bestehendes, in Schritt 10 live über Pro erzeugtes und in Schritt 11 bearbeitetes Skript `ace8b4fe-0ca5-4ec6-875d-d562f11c4929`, Version 2, im Browser freigegeben. Doppelklick sendet einen Request; angemeldeter normaler Host-Worker verarbeitet Lauf `e3dbcada-684a-4072-af87-4a78c427df37` und zeigt die Produktionsgrenze. CLI/Kostensperre/DB/Redis vor dem Hintergrundstart ohne Modellaufruf geprüft. Health meldet alle Dienste bereit. Zusammen mit der [Live-Skript-/Editorabnahme](step10-acceptance.md) ist M1 demonstriert; Codex ist kein Laufzeitbestandteil.

Backend-Befehl mit privaten bzw. isolierten Testanschlüssen in `DATABASE_URL` und `REDIS_URL`:

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe -m unittest discover -s backend/app -t backend -p 'test_*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s tasks -p 'test_*.py' -v
npm run build --prefix web
```

## Offen und nächster Schritt

**13 – Produktionskette mit RQ:** wiederaufnehmbare Medienstufen, begrenzte Wiederholungen, Timeouts und Wiederaufnahme ohne doppelte Artefakte. Danach Pexels/Piper/Remotion/FFmpeg und Medienspeicher in 14–18. Ein gestoppter Lauf wird durch wiederholte Skriptfreigabe nicht automatisch neu gestartet; Wiederaufnahme ist Teil von 13. Prozessabbruch zwischen Commit und Übergabe kann durch bewusste erneute Übergabe derselben Version behoben werden; automatische Zustellung/Wiederaufnahme bleibt offen. Login-/Neustartbetrieb und macOS/Linux bleiben Aufgabe 35. Modal bleibt ohne Credits-/Nullkosten-Nachweis gesperrt. Diese Abnahme enthält keine neue Modell- oder GPU-Ausführung.
