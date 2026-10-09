# Schritt 24 – echter CLOUD-Lauf vorbereitet, Live-Nachweis offen

Stand: **09.10.2026. Beauftragt durch „jetzt mach 3“. Nicht abgeschlossen.**

## Auftrag und Grenzen

Punkt 3 der fünf offenen Punkte ist Aufgabe 24: Beispiel B „Ein Regentag in der Stadt“ mit echten Wan-Szenen auf Modal produzieren, lokal speichern und dem Betreiber zur Videoabnahme bereitstellen. Erstes Ziel bleibt lokale Nutzung. Codex prüft Funktionen und Build; der Betreiber übernimmt Bedienung und Bild-/Tonqualität. Kein Social-Media-Upload.

LOKAL ist bereits real abgenommen. Der CLOUD-Gesamtablauf wurde in [23](step23-acceptance.md) funktional mit ausdrücklich gekennzeichneten Testclips nachgewiesen. Dieser Nachweis ersetzt keine echte Wan-Inferenz und keine Betreiber-Bedienungsabnahme.

## Implementierte unabhängige Vorbereitung

- `backend/app/cloud_costs.py`: reine, netzwerkfreie Kostenplanung für die tatsächlich geplante Rohclipzahl. Rechnet pro Clip mit separatem Kaltstart, vollständigem Remote-Funktionslimit, Container-Nachlauf und 30 s Planungsreserve; die lokale Cloud-Frist wird nicht als Abbruch entfernten Verbrauchs angerechnet. Decimal-Rechnung, Aufrundung, aktuelle Preisparameter und expliziter Zusatzbetrag für Image-Build, Modellbereitstellung, Speicher und Transfer. Unbekannte Zusatzkosten und veraltete Preise blockieren. Ein expliziter Betrag 0 erfordert weiterhin einen externen Nachweis.
- `check_planned_budget` schützt das bestehende **10-USD-Bruttolimit pro Testvideo** auch bei höher gesetztem Worker-Kostenlimit und verlangt zusätzlich den vorhandenen frischen Workspace-/Credits-/0-USD-Nettokosten-Nachweis. Reine Vorprüfung; weder Kontobeweis noch atomare Reservierung oder Provideraktivierung.
- Modal-Vorschau: CPU `(4, 4)` mit ausdrücklichem **weichem** CPU-Limit; RAM `(65536, 65536)` mit hartem 64-GiB-Limit; eigener Starttimeout 300 s zusätzlich zu 1800 s Ausführung. Ein Container, keine warmen Container/automatischen Funktions-Retries, 2 s Nachlauf. CPU-Throttling ist keine mathematisch harte Kostengrenze. Validator verwirft fehlende/erhöhte Grenzen auch bei neu berechneten Bundle-Hashes. Drei technische Bundle-Hashes bewusst aktualisiert; Workflow-/Modellprofil unverändert.

Preisstand 09.10.2026: A100-80GB 0,000694 USD/s, CPU 0,0000131 USD/Core/s, RAM 0,00000222 USD/GiB/s. Für 4 physische Cores und 64 GiB: 0,00088848 USD/s. **Sechs Szenen à 6 s benötigen zwölf Rohclips** und ergeben bei `12 × (300 + 1800 + 2 + 30)` s einen Planwert von **22,73087232 USD Compute**, vor Zusatzkosten. Das ist keine gemessene Inferenzdauer oder Rechnung, sondern ein konservativer Planwert unter ausdrücklich genannten Annahmen. Der unveränderte Remote-Zeitrahmen passt damit nicht in das 10-USD-Testvideobudget. Ein einzelner Clip hat unter denselben Annahmen einen Compute-Planwert von 1,89423936 USD.

Provider-Neustarts/Preemption, Abweichungen beim CPU-Throttling und tatsächliche Aufbau-/Transferkosten sind mit dieser Rechnung nicht sicher gedeckelt. Die Vorprüfung aktiviert daher auch bei rechnerischem Erfolg nichts. Insbesondere schützt ein Host-Timeout nicht vor einer weiterlaufenden entfernten GPU.

## Tatsächlich geprüft

- **27/27 gezielte Funktionen/Verträge in 8,864 s**, ohne Überspringen: vier neue Kostenfälle, sieben Grenz-/Budgetfälle, sieben Wan-Plan-/CPU-Transferfälle und neun Cloud-Bundle-/SDK-Vertragsfälle. Kostenbestandteile, veraltete/future Preise, 10-USD-Produktlimit, fehlender Kontobeleg, Ressourcenänderungen, Testclipherkunft und unverändert gesperrte Live-Provider geprüft. Erster neuer Lauf: ein falsch vorgerechneter Test-Erwartungswert korrigiert; finaler vollständiger gezielter Lauf grün.
- **10/10 Projekttests in 0,042 s** bestanden.
- `npm run build --prefix web` bestanden. Kein Webcode geändert und kein Browser-/Bedienungsnachweis behauptet.
- Gepinntes **Modal SDK 1.6.1** konstruiert die tatsächliche Vorschau offline; lokale SDK-Spezifikation enthält CPU `(4, 4)` und RAM `(65536, 65536)`. Keine Clientinitialisierung/Remote-Operation. SDK-Inspektion zunächst mit falschem privaten Attribut `_spec` versucht, mit tatsächlich vorhandenem `_spec_` korrigiert. Deprecation-Hinweis zur lokalen Inspektionsproperty notiert; kein SDK-Upgrade.
- Bundle-Hashes und `git diff --check` geprüft. Funktionslog ignoriert unter `.data/step24-functions.log`; temporäre Testdateien unter `.data/step24-temp`.
- Keine Datenbank-/Dienständerung; die unveränderten Integrationsnachweise aus 23 wurden nicht wiederholt. Keine Dienste/Container neu gestartet.

## Sicherheitsentscheidung und echte Blocker

Schutzbedarf: Konto-Credits und Billing, Modal-Zugang, private freigegebene Prompts und Medien. Vertrauensgrenze: verifizierte Betreiber-/Konto-/Preisdaten → Host-Kostentor → späterer Modal-Auftrag. Missbrauchsfälle: falsche Nullkostenannahme, fehlende Zusatzkosten, Burst-Ressourcen, nach Host-Timeout weiterlaufende Jobs und doppelte Starts. Nur vertrauenswürdige Konfiguration darf Nachweise liefern; Skript-/UI-Eingaben dürfen keine Kostenfreigabe erteilen. Keine Tokens gelesen/ausgegeben oder in Testdaten gespeichert.

1. **Kontonachweis fehlt:** keine `~/.modal.toml` vorhanden; keine `MODAL_*`-/`WAN_*`-Variablen in der aktuellen Shell gefunden. Das schließt eine Browseranmeldung nicht aus, beweist aber keine nutzbare SDK-Anbindung. Modal-Workspace, aktuelles Gratis-Restguthaben, Tarif, GPU-Zahlungsmethode, verbliebenes Bruttonutzungsbudget und wirksam gesetztes **Spend limit 0 USD nach Credits** fehlen. Der Betreiber wurde nach Workspace/Credits/Spend-Limit gefragt; keine Antwort liegt zum dokumentierten Stand vor. Keine Tokens/Passwörter im Chat anfordern.
2. **Vollvideo-Kostenplan passt noch nicht:** vor Vollproduktion begrenzten Einzelclip mit aktuellen vollständigen Aufbaukosten planen; erst nach Kontonachweis ausführen und echte Laufzeit/Verbrauch messen. Daraus Remote-Ausführungsgrenzen und Gesamtreservierung innerhalb verbleibender 10 USD ableiten. Nicht aus Zeitersparnis den Planwert als Messung behandeln oder das Bruttolimit erhöhen.
3. **Remote-Adapter und Betrieb bleiben offen:** echtes begrenztes Build/Modell-Volume, Hashprüfung im Volume, ComfyUI-Prozess, idempotente dauerhafte Auftragserfassung, workspaceweite Reservierung, Abbruch/Remote-Status bei Hostverlust, echter Rücktransfer und Produktionsanbindung fehlen weiterhin. Die bisherige `generate_clip()`-Sperre bleibt erhalten; es gibt weiterhin keinen globalen deploybaren `app` und keinen normalen Live-Factory-Schalter.
4. **Echtes Video/Betreiberabnahme fehlen:** VRAM, Wan-Bildqualität, Laufzeit, tatsächlicher Verbrauch, finales Manifest/ffprobe/Dateihash und Wiedergabe sind erst nach echter Inferenz nachweisbar. M3 bleibt offen.

**Modal-Verbrauch in diesem Auftrag: 0.** Kein Client, Image-Build, Deployment, Remote-Volume, Gewichtsdownload oder GPU-Aufruf. Die öffentliche 30-USD-Tarifangabe wurde nicht als vorhandenes Kontoguthaben behandelt. Keine Kontolimits/Zahlungsmethode geändert.

## Quellen, Übergabe und nächster Schritt

Offizielle Quellen am 09.10.2026 gelesen: [Preise und Abrechnung](https://modal.com/pricing), [Bruttobudget und Nettospend-Limit](https://modal.com/docs/guide/budgets), [CPU-/RAM-Limits](https://modal.com/docs/guide/resources), [Start-/Ausführungszeitlimits](https://modal.com/docs/guide/timeouts). Keine Kryptografieänderung oder Zertifizierungsbehauptung.

Lokaler Windows-Host, exaktes Arbeitsverzeichnis `C:/Users/Public/Projekte/Video pipline/Video-generating-Pipeline v2`, Branch `codex/step10-in-progress`; vorhandene `.venv`, FFmpeg/Piper/Remotion bleiben erhalten. Ausgangs-HEAD `cb9d18ef07a0528ddf531d8468c59c6f784db046`, Arbeitsbaum vor 24 sauber. Diese Vorbereitung betrifft Cloud-Definition/Validierung, zwei neue Backenddateien und Statusdokumente; Commit-ID nach Sicherung über Git prüfen. Keine privaten Konfigurationsinhalte in der Übergabe.

CTX-001 geprüft: Das App-Projektverzeichnis enthält keinen gespeicherten Projekt-Eintrag für exakt diesen v2-Checkout. Der ähnlich benannte Eintrag zeigt auf einen anderen Ordner ohne `v2`. Deshalb kein Folgechat in einer abweichenden Umgebung gestartet; dieser sichere Wiedereinstieg bleibt dokumentiert.

**Genau nächster beauftragter Schritt:** Betreiber-Kontonachweise und lokale sichere Modal-Anmeldung herstellen/prüfen; danach echten Remote-Adapter mit Reservierung und begrenztem Einzelclip-Messlauf fertigstellen. Erst bei sämtlichen Nachweisen den GPU-Lauf starten, innerhalb des 10-USD-Bruttobudgets Beispiel B produzieren und dem Haupttester lokal zeigen. Erfolgreiche unveränderte Prüfungen aus 23/24 nicht pauschal wiederholen. Nicht automatisch mit 25 fortfahren.
