# Wan / Modal – Vorbereitung aus Schritt 20

Stand: 04.10.2026. Dieses Verzeichnis enthält den versionierten CLOUD-Bauplan, noch keinen aktiven Videogenerator. Der Installationsrechner benötigt dafür weder Wan-Gewichte noch ComfyUI, PyTorch oder eine lokale GPU. Sein bestehender Compose-Stack bleibt unverändert. [Abnahme und offene Live-Nachweise](../tasks/step20-acceptance.md).

**Aktualisierung 09.10.2026, Aufgabe 24 begonnen:** Vorschau verwendet CPU `(4, 4)` mit explizitem weichem CPU-Limit, RAM `(65536, 65536)` mit hartem Speicherlimit und separaten 300-s-Starttimeout zusätzlich zu 1800 s Ausführung. Geprüfte Bundle-Hashes aktualisiert. `backend/app/cloud_costs.py` plant sämtliche Rohclips einschließlich Start/Nachlauf, verlangt aktuelle Preise und explizite Zusatzkosten und schützt das bestehende 10-USD-Bruttolimit. Zwölf Clips im jetzigen Zeitrahmen ergeben 22,73 USD Compute-Planwert vor Zusatzkosten. Kein tatsächlicher Verbrauch gemessen, keine Kontoverifikation/Reservierung und kein Live-Provider. Erst Kontobelege und begrenzter Einzelclip-Messlauf ermöglichen passende Remote-Grenzen. [Prüfbericht 24](../tasks/step24-acceptance.md).

**Schritt 21 inzwischen abgeschlossen:** Der Hostadapter in `backend/app/wan.py` plant mehrere Clips, speichert stabile Intents und prüft Antwort-/Dateihashes sowie das tatsächliche MP4-Profil, bevor Szenen im gewählten Medienordner erscheinen. Kurze lokale Testantworten/-dateien und echte PostgreSQL-/Redis-/Prozessprüfungen bestanden; kein Modal-Aufruf. Provider werden nur im Testcode explizit injiziert, normale CLOUD-Produktion bleibt gesperrt. [Transportvertrag](../tasks/cloud-transfer-contract.md), [Prüfbericht 21](../tasks/step21-acceptance.md). Nächster Schritt 22: Grenzen vor teuren Aufrufen; Browserlauf 23, echter Provider nach Kostenprüfung 24.

## Dateien und feste Versionen

| Datei | Zweck |
| --- | --- |
| `wan-api.json` | Eigener API-Graph mit 14 nativen ComfyUI-Nodes, ohne LoRA oder Custom Nodes |
| `bundle.lock.json` | Workflow-Version, ComfyUI-Commit, Quellen und SHA-256 der zehn technischen Bundle-Dateien |
| `models.lock.json` | Vier Gewichte mit Repository, festem Hugging-Face-Commit, Dateigröße, Zielpfad und SHA-256 |
| `node-contracts.json` | Eingangs-/Ausgangstypen aus vier offiziellen Modulen am festgelegten ComfyUI-Commit; deren Quellprüfsummen |
| `requirements-comfy.in` / `requirements-linux.lock` | Offizielle ComfyUI-Anforderungen und 99 für Linux/Python 3.12 aufgelöste Pakete mit Versionen und Hashes |
| `requirements-sdk.txt` | Modal SDK 1.6.1 für optionale lokale Prüfung der Definition |
| `deployment.json` / `modal_app.py` | Offline konstruierbare Modal-Definition: genau eine `A100-80GB`, getrennte Modell-/Ergebnis-Volumes |
| `extra_model_paths.yaml` | ComfyUI-Modellpfade unter dem späteren Remote-Mount `/models` |
| `validate.py` / `test_workflow.py` | Offlineprüfung und Fehlerfalltests ohne Netzwerk, SDK oder Inferenz |

Workflow-Version: **`wan2.2-t2v-a14b-v1`**. ComfyUI **v0.38.0**, Commit `6b747c0428c343e1417219641db93a4fb7cb69ae`. PyTorch **2.9.1+cu128**, torchvision **0.24.1+cu128**. Linux-Lock mit **uv 0.11.5**, Python 3.12 und `x86_64-unknown-linux-gnu` erstellt. Die CUDA-Pakete werden ausschließlich für das spätere Modal-Image beschrieben, nicht auf dem Entwicklungsrechner installiert.

Grundlage: [offizieller Wan-Leitfaden](https://docs.comfy.org/tutorials/video/wan/wan2_2), [festgelegte native Vorlage](https://github.com/Comfy-Org/workflow_templates/blob/41675962c18de9c6467731dc69b2587f760a2af8/templates/video_wan2_2_14B_t2v.json), [ComfyUI-Quellstand](https://github.com/Comfy-Org/ComfyUI/tree/6b747c0428c343e1417219641db93a4fb7cb69ae), [PyTorch-Versionen](https://pytorch.org/get-started/previous-versions/), [Modal-Images](https://modal.com/docs/guide/images), [GPU-Auswahl](https://modal.com/docs/guide/gpu) und [Skalierung](https://modal.com/docs/guide/scale).

## Clipprofil und Übergabe

Ein Rohclip ist als **720 × 1280, 81 Frames, 16 fps, MP4/H.264** geplant, also etwa **5,0625 Sekunden**. Das ist noch keine vollständige Szene von 6–12 Sekunden. Planung mehrerer Clips und Verarbeitung zu 24 fps werden in den folgenden CLOUD-Schritten umgesetzt und geprüft.

Der High-Noise-Sampler verarbeitet Schritte 0–10 von 20, übergibt sein Latent mit verbleibendem Rauschen an den Low-Noise-Sampler, dieser verarbeitet 10–20 ohne neues Rauschen. Der Decoder bekommt ausschließlich dessen abgeschlossenen Ausgang. Der Graph ist eine bewusst angepasste API-Fassung der nativen Vorlage, keine unveränderte Kopie. `SaveVideo` verwendet die dynamischen MP4-/H.264-Eingänge des festgelegten ComfyUI-Quellstands.

`prepare_workflow(prompt, seed, clip_id)` erzeugt lediglich eine neue JSON-Struktur: Prompt mit 1–2000 Zeichen, ganzzahliger Seed von 0 bis 2⁶⁴−1 und UUID für den Ausgabepfad. Es wird weder ein Auftrag gestartet noch eine Datei geschrieben. `verify_model_files(directory)` prüft bereits vorhandene Dateien auf Größe und SHA-256; fehlende Gewichte werden nicht heruntergeladen.

## Offline prüfen

Aus dem Repository-Stamm, mit Python 3.12; keine Anmeldung oder Cloud-Verbindung erforderlich:

```text
python -m cloud.validate
python -m unittest cloud.test_workflow -v
```

Optional kann in einer separaten Werkzeugumgebung ausschließlich `requirements-sdk.txt` installiert und `deployment_preview()` lokal aufgerufen werden. Die Funktion konstruiert lazy SDK-Objekte, ohne Image-Build, Volume-Erstellung, Deployment oder Funktionsaufruf. Sie verlangt SDK 1.6.1. Das SDK ist keine neue Voraussetzung des normalen Hostworkers.

Die Abhängigkeiten lassen sich mit uv 0.11.5 über die offiziellen PyPI-/PyTorch-Indizes erneut auflösen:

```text
uv pip compile cloud/requirements-comfy.in --python-version 3.12 --python-platform x86_64-unknown-linux-gnu --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match --only-binary :all: --generate-hashes --output-file cloud/requirements-linux.lock
```

Eine erneute Auflösung kann bei offenen Eingangsbereichen neue Versionen auswählen. Der committed Lock ist verbindlich; Änderungen werden geprüft und als neue Bundle-Version dokumentiert. `.gitattributes` erzwingt LF-Zeilenenden für das Cloud-Bundle, damit die Hashes auch bei Windows-Checkouts mit `core.autocrlf=true` stabil bleiben. Nach einer absichtlichen Änderung eines technischen Bundle-Files dessen SHA-256 in `bundle.lock.json` aktualisieren und alle Offlineprüfungen erneut ausführen. Die Hashes sind Integritätsprüfungen, keine kryptografische Signatur.

## Ausführung noch offen

`live_enabled=false`; es gibt keinen globalen deploybaren `app` und keinen Run-/Deploy-Einstieg. `generate_clip()` ist ausdrücklich noch gesperrt. Modell-Volume schreibgeschützt, Ergebnis-Volume getrennt, keine Volume-Erstellung bei der Vorschau; ein Container gleichzeitig, keine warmen Container, keine automatischen Wiederholungen, 1800 Sekunden Funktionslimit. ComfyUI soll später nur intern auf `127.0.0.1:8188` lauschen. Die Definition startet diesen Server noch nicht.

**Die Fehlermeldung im Funktionskörper wäre keine Kostensperre vor GPU-Zuteilung.** Vor späterer Aktivierung muss Schritt 22 die Auftragsgrenzen vor dem Aufruf prüfen; Schritt 24 verlangt nachgewiesene Gratis-Credits und eine wirksame Grenze von 0 USD Nettokosten. Bisher wurden keine GPU, kein Image-Build und kein Modelldownload gestartet. Die vier Gewichte umfassen laut fixierter Metadaten **35.577.569.479 Bytes**; ihre tatsächlichen Dateien müssen später im Modal-Volume geprüft werden.

Offen: Remote-Image-Build/Start, tatsächlich geladenes CUDA-/ComfyUI-System, Modellprüfung im Volume, VRAM, Dauer, Qualität und Kosten. Betriebssystempakete und Debian-Basis sind nicht vollständig auf Image-Digest/apt-Versionen fixiert; der erste geprüfte Remote-Build muss dokumentiert werden. Rücktransfer folgt mit kontrollierten Testdaten in 21, Grenzen in 22, Browserlauf in 23, echte Inferenz erst in 24.
