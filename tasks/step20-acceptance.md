# Schritt 20 – Modal-Workflow ohne Generierung vorbereiten

Stand: **04.10.2026. Statische Abnahme abgeschlossen.** Beide Kriterien aus [todo.md](todo.md) sind erfüllt. Eine laufende CLOUD-Produktion oder Bildqualität wird damit nicht behauptet.

## Ergebnis der Entwicklung

Das neue [Cloud-Bundle](../cloud/README.md) beschreibt den späteren Wan-Generator getrennt vom installierten Hostworker und Compose-Stack. Versionierter API-Graph, Quellverträge, vier Modellrevisionen/Prüfsummen, Linux-Abhängigkeiten mit Hashes und eine lokal konstruierbare Modal-Definition sind vorhanden. Die Weboberfläche wurde in diesem Schritt nicht geändert; ein neues KI-Video wurde nicht erzeugt.

| Bestandteil | Festgelegter Stand |
| --- | --- |
| Workflow | `wan2.2-t2v-a14b-v1`, 14 native Nodes, keine LoRA/Custom Nodes |
| ComfyUI | v0.38.0 / `6b747c0428c343e1417219641db93a4fb7cb69ae` |
| Vorlage | Nativer Zweig aus `workflow_templates` / `41675962c18de9c6467731dc69b2587f760a2af8` |
| Modal SDK | 1.6.1, separat vom Hostworker |
| Remote-Python / CUDA-Pakete | Python 3.12 / PyTorch 2.9.1+cu128 / torchvision 0.24.1+cu128 |
| Abhängigkeiten | 99 Pakete, feste Versionen und SHA-256; uv 0.11.5, Linux x86_64, ausschließlich Wheels |
| GPU / Parallelität | Explizit `A100-80GB`, maximal ein Container, keine warmen Container oder automatischen Retries |
| Zeit / CPU / RAM | 1800 s pro Funktion, 4 CPU-Kerne, 65536 MiB RAM; Gesamtkosten-/Clipgrenzen folgen in 22 |
| Speicherung | Getrennte Remote-Volumes für Modelle und Ergebnisse, Modelle schreibgeschützt |
| Rohclip | 720 × 1280 / 81 Frames / 16 fps / MP4-H.264, ca. 5,0625 s |
| Live-Status | `live_enabled=false`, kein globaler Deploy-/Run-Einstieg, Funktionskörper gesperrt |

### Modelle und Herkunft

Die Metadaten wurden aus offiziellen Hugging-Face-Repositories am jeweiligen Commit gelesen; LFS-Objektkennungen sind als SHA-256 festgeschrieben. Es wurden **keine Gewichte heruntergeladen**.

| Gewicht | Bytes | Repository / Revision |
| --- | ---: | --- |
| `wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors` | 14.293.923.632 | Wan_2.2_ComfyUI_Repackaged / `ee6f4a40737a995bf5818954cfce6d59443b0f04` |
| `wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors` | 14.293.923.632 | gleiche Revision |
| `wan_2.1_vae.safetensors` | 253.815.318 | gleiche Revision |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | 6.735.906.897 | Wan_2.1_ComfyUI_repackaged / `123acf1cc74bccbb9bfff8ac1ee72edc08c2341d` |

Summe **35.577.569.479 Bytes**. Vollständige SHA-256 und sichere Volume-Zielpfade stehen in [models.lock.json](../cloud/models.lock.json). Offizielle Quellen: [Wan-2.2-Revision](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/tree/ee6f4a40737a995bf5818954cfce6d59443b0f04/split_files), [Textencoder-Revision](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/tree/123acf1cc74bccbb9bfff8ac1ee72edc08c2341d/split_files/text_encoders), [Wan-Leitfaden](https://docs.comfy.org/tutorials/video/wan/wan2_2).

### Bewusste Workflow-Anpassung

Aus der offiziellen nativen Vorlage wurde ein eigener API-Graph erstellt. High-Noise 0–10 und Low-Noise 10–20 bilden eine zusammenhängende Folge. Low-Noise erhält das High-Noise-Latent, fügt kein neues Rauschen hinzu und liefert den endgültigen Decoder-Eingang. Damit wird nicht versehentlich der High-Noise-Zwischenstand gespeichert. Die dynamischen flachen `SaveVideo`-Felder (`format`, `format.codec`, `format.codec.encoding`) wurden gegen die reine Eingangs-Umwandlung im festgelegten `_io.py` geprüft. Das ist eine Quell-/Vertragsprüfung, noch keine ausgeführte ComfyUI-Inferenz.

[Vorlage am festen Commit](https://github.com/Comfy-Org/workflow_templates/blob/41675962c18de9c6467731dc69b2587f760a2af8/templates/video_wan2_2_14B_t2v.json), [Node-Quellen](https://github.com/Comfy-Org/ComfyUI/tree/6b747c0428c343e1417219641db93a4fb7cb69ae/comfy_extras), [dynamische API-Eingänge](https://github.com/Comfy-Org/ComfyUI/blob/6b747c0428c343e1417219641db93a4fb7cb69ae/comfy_api/latest/_io.py).

## Ausgeführte Prüfungen

- `python -m cloud.validate`: 14 Nodes, vier Modelle, feste Bundle-Hashes, GPU `A100-80GB`, Live deaktiviert bestätigt.
- `python -m unittest cloud.test_workflow -v`: **7/7 bestanden**. Manipulierte Datei, falsche GPU, vertauschte Modelle, falsche Port-/Typverbindung, Zyklus, falscher Sampling-Übergang, Decoder am Zwischenstand und unerlaubter Codec werden abgelehnt. Prompt-/Seed-/UUID-Grenzen und unveränderte Vorlage geprüft. Modell-Dateiprüfung mit kleinen kontrollierten Dateien: Erfolg, beschädigt, fehlend und Pfad außerhalb des Volumes; kein Download.
- Modal SDK **1.6.1** in ignorierter Werkzeugumgebung: `deployment_preview()` konstruiert Definition erfolgreich. `modal.Client.from_env` war dabei durch eine Assertion gesperrt; kein Client wurde initialisiert. Kein Remote-Image-Build, Deployment, Volume-Anlegen oder GPU-Aufruf.
- Linux-Abhängigkeitsauflösung mit **uv 0.11.5** über offizielle PyPI-/PyTorch-Indizes erfolgreich. Wheel-only-Auflösung ergibt dieselben 99 Paketversionen; Hash-Lock erstellt. Das belegt Auflösbarkeit, nicht den tatsächlichen Remote-Build.
- `app.test_production.StageContractTest`: **1/1 bestanden**; `app.test_encoding.EncodingPlanTest`: **4/4 bestanden**, einschließlich Ablehnung gemischter Quellen. Für Backendtests ist `PYTHONPATH=backend` erforderlich; ein erster Aufruf ohne diesen Modulpfad wurde korrigiert, kein Produktfehler.
- `python -m unittest discover -s tasks -p test_*.py -v`: **10/10 bestanden**.
- `npm run build --prefix web`: **bestanden**. Webcode unverändert; keine neue Browserfunktion in 20.
- AST-/Dateiprüfung bestätigt keinen Live-Einstieg und keine ComfyUI-/Torch-/NVIDIA-Installation in beiden Compose-Dateien oder Hostanforderungen. Vorhandene LOKAL-Produktion unverändert; CLOUD-Adapter noch nicht aktiviert.
- `.gitattributes` fixiert LF für das Cloud-Bundle; damit verändert Windows-`core.autocrlf` die gehashten Dateien beim Checkout nicht. Bundle-Prüfung auch im separaten `git checkout-index`-Export bei aktivem `core.autocrlf=true` bestanden. Die fünf offiziellen Modulquellen wurden nochmals byteweise am festen Commit abgerufen, mit den verwendeten Quellen verglichen und ihre originalen Byte-SHA-256 erfasst.

Keine Datenbank-, API- oder laufende Dienständerung in 20; daher keine neue Datenbank-/Browserintegration erforderlich. Die 86 Backendtests aus Schritt 19 sind historische Nachweise, nicht als Gesamtlauf dieses Schritts erneut behauptet. Quellen und Hilfsproben liegen ignoriert unter `.data/step20-*`; nur Bundle, Tests und Dokumentation werden versioniert.

## Offen für folgende Schritte

1. **21:** CLOUD-Auftragsvertrag, Mehrclip-Planung und geprüfter Rücktransfer mit kontrollierten Antworten/Testdateien; keine echte Generierung.
2. **22:** Vor dem teuren Aufruf durchgesetzte Clip-, Zeit-, Parallelitäts- und Kostenlimits. Die Ausnahme im GPU-Funktionskörper verhindert keine Kosten vor GPU-Zuteilung und ersetzt keinen Kontonachweis.
3. **23:** Gesamter CLOUD-Browserlauf mit Testdaten, ausschließlich `AI_GENERATED_VIDEO`, Fehlerfälle und Masterprofil.
4. **24:** Erst nach nachgewiesenen Gratis-Credits und wirksamen 0 USD Nettokosten: Remote-Image bauen, Gewichte im Volume prüfen, ComfyUI starten und reale GPU-Inferenz/Qualität/VRAM/Laufzeit/Kosten messen. Debian-Basis und apt-Pakete sind noch nicht auf einen geprüften Image-Digest fixiert. Ein statisch plausibles 81-Frame-Hochformat ist kein Leistungsnachweis.

Keine Kontoanmeldung, Zahlungsfreigabe, lokale Wan-Installation oder Zugriff auf den früheren Ubuntu-Rechner ist für den Abschluss von 20 notwendig. Deployment/Modelldownload/Inference bleiben bis zu den jeweiligen Folgeprüfungen offen. [Modal-Images](https://modal.com/docs/guide/images), [GPU-Auswahl](https://modal.com/docs/guide/gpu), [Skalierung](https://modal.com/docs/guide/scale), [PyTorch-Versionen](https://pytorch.org/get-started/previous-versions/).
