# Schritt 22 – Cloud-Grenzen

Stand: **09.10.2026. Implementiert und funktional geprüft; Dienstintegration und echte Kontonachweise noch offen.**

**Aktualisierung durch 23 (09.10.2026):** fehlende Dienstintegration inzwischen auf getrennten PostgreSQL-/Redis-Testcontainern nachgewiesen. Zwei Wan-Transferfälle, vier API-Vertragsfälle und neuer Clipgrenzen-/Frist-Resume-Fall erfolgreich geprüft. Der zuvor nicht erreichbare Dienst ist ein historischer Prüfhinderungsgrund. Tatsächliche Modal-Kontonachweise/Live-Verknüpfung bleiben offen. [Prüfbericht 23](step23-acceptance.md).

## Auftrag und Ergebnis

Betreiberentscheidung: erstes Ziel ist eine ausschließlich lokal benutzte Webseite. Codex prüft Funktionen und Build; der Betreiber übernimmt Bedienung, Videoqualität und Hauptabnahme. Keine öffentliche Bereitstellung und keine Browserabnahme durch Codex für diesen Schritt.

- Private `WAN_LIMITS` in der vorhandenen Worker-Konfiguration oder ausdrücklich gesetzte `WAN_*`-Umgebungsvariablen. Ungültige, leere, unbekannte oder nicht endliche Werte werden gesperrt; keine stillen Ersatzwerte.
- Clipzahlprüfung vor Medienarbeit und Provideroperation. Nicht blockierende Betriebssystem-Dateisperren begrenzen parallele CLOUD-Aufträge mehrerer Prozesse mit demselben Medienspeicher. Sperren werden bei Prozessende freigegeben; Sperrdateien bleiben bestehen. Grenzen nur bei ruhenden Workern ändern; mehrere Installationen/Modal-Workspaces brauchen zusätzlich Remote-Grenzen in 24.
- Konfigurierbare Cloud-Frist im Produktionsprozess, einschließlich bestehendem Prozess-Watchdog. Die normale Produktionskette rechnet die Zeit ab dem ursprünglichen Laufbeginn an; Wiederaufnahme verlängert die Cloud-Frist nicht. Der direkte Testadapter prüft zusätzlich eine monotone Frist, Provider-/Transfergrenzen und begrenzte ffprobe-/FFmpeg-Aufrufe. Blockierende Provider müssen ihre übergebene Restfrist einhalten.
- Separate reine Funktion für Kostenprüfung: frischer, zum Workspace passender Nachweis (höchstens fünf Minuten alt), verbleibende Credits und Workspace-Budget, tatsächlich durchgesetztes Nettokostenlimit von exakt 0 USD, begrenzte Deployment-Parallelität/-Laufzeit und positive Gesamtkostenschätzung innerhalb sämtlicher Grenzen. Die Schätzung muss Compute, Start, Build, Speicher und Transfer einschließen. Ein Nutzungsbudget ersetzt kein Nettokostenlimit.
- Modell-/GPU-Fehler bleiben als `StageFailure` sichtbar; kein Wechsel zu Pexels. Normale CLOUD-Generierung und alle Live-Provider bleiben unabhängig vom Ergebnis der reinen Kostenprüfung gesperrt.

## Konfiguration

In der bestehenden privaten `~/.config/video-pipeline/worker.json` zusätzlich einfügen; vorhandene Einstellungen erhalten:

```json
"WAN_LIMITS": {
  "max_clips": 20,
  "max_run_seconds": 3600,
  "max_clip_seconds": 1800,
  "max_parallel": 1,
  "max_cost_usd": "0"
}
```

Entsprechende explizite Umgebungsvariablen: `WAN_MAX_CLIPS`, `WAN_MAX_RUN_SECONDS`, `WAN_MAX_CLIP_SECONDS`, `WAN_MAX_PARALLEL`, `WAN_MAX_COST_USD`. Sie haben Vorrang vor privaten Datei-Einstellungen. `WORKER_CONFIG_PATH` wird vom normalen Worker gesetzt. Keine Änderung der tatsächlichen Betreiber-Konfiguration in dieser Aufgabe.

| Grenze | Vorgabe | Zulässiger Bereich |
| --- | --- | --- |
| Rohclips pro Auftrag | 20 | 1–100 |
| Cloud-Frist in Sekunden | 3600 | 1–3600 |
| Provider-/Clipfrist in Sekunden | 1800 | 1–1800; Testtransfer weiterhin höchstens 30 |
| Gleichzeitige Host-Aufträge | 1 | 1–8; Modal-Definition weiterhin höchstens ein Container |
| Gesamtkostenlimit in USD | 0 | 0–100; ausschließlich innerhalb geprüfter Gratis-Credits |

Ein höheres `max_cost_usd` aktiviert weder Modal noch einen Live-Provider und erlaubt keine Nettokosten. Der gespeicherte Nachweis ist ein Vertrag für den späteren vertrauenswürdigen Konto-Adapter, kein Kontoauszug und keine technische Garantie allein durch eine JSON-Angabe.

## Tatsächliche Prüfungen

- **28/28 gezielte Funktionen und bestehende Verträge**, keine übersprungen, finaler Lauf **7,580 s**: sieben neue Grenz-/Kostenfunktionen, sieben Wan-Funktionen, vier Encodingplan-, zwei Medienpfad-, ein Stufenvertrags- und sieben Cloud-Bundle-Tests. Lokale Farbflächen-MP4s auf der CPU, keine echten Wan-Clips. Prozessübergreifende Sperre unter Windows mit echtem zweiten Python-Prozess geprüft.
- Geprüft: Ablehnung vor Anbieter/Medienarbeit, ungültige Konfiguration, Clipanzahl, belegte/freigegebene Slots, Cloud-Zeitlimit im Subprozesspayload, unveränderte LOKAL-Frist, verspätete Providerantwort vor Transfer, Modell-/GPU-Fehler ohne Artefakte, Cache/Wiederaufnahme, manipulierte Antworten/Dateien, positive und negative Kostenverträge einschließlich Grenzwertgleichheit.
- **10/10 Projekttests** bestanden; `npm run build --prefix web` bestanden. Keine Webcodeänderung.
- **Echte PostgreSQL-/Redis-/RQ-Integration offen:** erster Versuch scheitert schon im Setup am lokal gesperrten Socketzugriff auf PostgreSQL (`127.0.0.1:5433`). Auch außerhalb dieser Beschränkung ist der Dienst nicht erreichbar. Den wartenden Testprozess anhand Skript/PID gezielt beendet, anschließend mit `PGCONNECT_TIMEOUT=3` erneut geprüft: zwei Setupfehler, null Tests in 6,142 s ausgeführt. Kein Produktionsauftrag und kein Erfolgsnachweis.
- Rote Ausgangsprüfung: neue Grenztests scheitern am noch fehlenden Modul. Ein nachfolgender Prüflauf scheitert an der nicht beschreibbaren Sandbox-Tempablage; temporäre Dateien danach ausschließlich im ignorierten Projektordner `.data/step22-temp`. Ein Testpayload benötigte außerdem die vorhandene Laufkennung; korrigierter finaler Funktionslauf besteht.
- Belege ignoriert: `.data/step22-functions.log`, `.data/step22-integration.log`. Keine Secrets, Gewichte oder Testmedien versioniert.

**Modal-Verbrauch 0:** kein Client, Deployment, Remote-Build, Volumezugriff, Gewichtsdownload oder GPU-Aufruf. Keine Dienste neu gestartet, keine Konten-/Kostenkonfiguration geändert.

## Sicherheitsentscheidung und Grenzen

Schutzbedarf: Credits/Billing, private Worker-Konfiguration, freigegebene Szenen und Medien. Vertrauensgrenzen: Betreiber-Konfiguration → Hostprozess; fremde Prompts/Providerantworten → validierter Auftrag und Dateien; spätere Konto-/Deploymentdaten → Kostentor. Missbrauchsfälle: unbegrenzte Clips, Parallelstarts, verlängerte Retries, veraltete/falsche Kostenbelege und manipulierte Antworten. Grenzen server-/hostseitig; keine Zugangsdaten in Fehlermeldungen oder Tests.

Offizielle Quellen am 09.10.2026 erneut geprüft: [Modal Budgets/Spend limits](https://modal.com/docs/guide/budgets), [Modal Skalierungsgrenzen](https://modal.com/docs/guide/scale), [OWASP Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html). Keine Kryptografieänderung oder Behauptung einer Zertifizierung.

Noch offen: Betreiber-Hauptabnahme; tatsächliche Abfrage/Verifikation von Modal-Credits, Budget und 0-USD-Spend-Limit vor jedem echten Auftrag, atomare Reservierung über parallele Installationen/Retry sowie Remote-Abbruch/Idempotenz in 24. Ohne diese Nachweise bleiben Live-Aufrufe gesperrt. Dienstintegration und vollständiger Funktionsablauf mit Testdaten sind inzwischen in 23 nachgewiesen; Bedienungsabnahme durch Betreiber.
