# Aufgabe 05 – Wan/Modal-Entwurfsprüfung ohne Generierung

Stand: 26. September 2026. **Dokumentenbasierte Prüfung abgeschlossen.** Es wurde weder ein Modal-Job gestartet noch ein Wan-Clip erzeugt. Die folgenden Zahlen sind Planwerte, keine Messung im Projekt. Der erste echte CLOUD-Lauf bleibt Aufgabe 24.

## Technischer Befund

| Punkt | Befund und Entwurfsentscheidung |
| --- | --- |
| Generator | [ComfyUI zeigt einen nativen Wan2.2-14B-T2V-Workflow](https://docs.comfy.org/tutorials/video/wan/wan2_2) mit getrennten High- und Low-Noise-Modellen, Textencoder, VAE und `EmptyHunyuanLatentVideo` für Breite, Höhe und Framezahl. Für V1 werden die von Comfy-Org für ComfyUI aufbereiteten FP8-Dateien benutzt, nicht die anders organisierten Original-Checkpoints des Wan-Python-Beispiels. Die konkrete Workflow-JSON und Versionen werden erst in Aufgabe 20 fixiert. |
| GPU | [Modal unterstützt `gpu="A100-80GB"` ausdrücklich](https://modal.com/docs/guide/gpu); `A100` allein bezeichnet laut Doku die 40-GB-Variante. [Wan nennt für seine eigene T2V-A14B-Einzel-GPU-Ausführung mindestens 80 GB VRAM](https://github.com/Wan-Video/Wan2.2#run-text-to-video-generation). Das beweist **nicht**, dass die gewählte ComfyUI-Konfiguration auf einer A100-80GB bei jeder Framezahl ohne Speicherfehler läuft. |
| Format und Länge | [Wan führt für T2V-A14B unter anderem 720 × 1280 und 480 × 832 als unterstützte Größen](https://github.com/Wan-Video/Wan2.2/blob/main/wan/configs/__init__.py). Der [Wan-Standard setzt 81 Frames und 16 fps](https://github.com/Wan-Video/Wan2.2/blob/main/wan/configs/shared_config.py), also ungefähr fünf Sekunden Rohclip. Das ist ein Ausgangswert der Wan-Python-Konfiguration, **keine geprüfte ComfyUI-Ausgabe**. Für 30–60 Sekunden werden mehrere Clips benötigt; längere Szenen erhalten mehrere Clips desselben CLOUD-Medientyps. Der Ubuntu-Renderer bringt sie anschließend auf das V1-Masterprofil 720 × 1280, 24 fps, H.264/AAC. Die tatsächliche Bewegung und Länge werden in Aufgabe 24 geprüft. |
| Speicher | Die vier unten genannten Gewichte umfassen zusammen rund **35,6 GB dezimal**. Zusätzlich sind Platz für ComfyUI, temporäre Dateien, Videos und Caches sowie Arbeitsspeicher und VRAM nötig. Dateigröße auf dem Volume ist keine Aussage über Spitzenbedarf im VRAM. [Modal empfiehlt ein persistentes Volume für Modellgewichte](https://modal.com/docs/guide/model-weights), damit sie nicht bei jedem Containerstart erneut geladen werden müssen. |
| Rücktransfer | [Modal-Volumes unterstützen persistente Dateien und `commit()`](https://modal.com/docs/guide/volumes); [die CLI kann größere Dateien mit `modal volume get` abrufen](https://modal.com/docs/cli/latest/volume#modal-volume-get). Der künftige Worker auf dem Entwicklungsrechner bzw. Ubuntu stößt den Modal-Job selbst an, holt den Clip automatisch in eine temporäre Datei, prüft Prüfsumme und Medienprofil mit `ffprobe` und verschiebt ihn erst danach in den persistenten Medienspeicher. Ein Volumepfad allein ist kein fertiges Ergebnis in der Weboberfläche. |

### Benötigte Modellgewichte

Quelle für die Dateiauswahl: [offizieller ComfyUI-Wan2.2-T2V-Leitfaden](https://docs.comfy.org/tutorials/video/wan/wan2_2). Die angegebenen Größen stammen von den jeweiligen Dateien bei Comfy-Org auf Hugging Face und können sich mit Revisionen ändern.

| Datei und Zielordner in ComfyUI | Größe |
| --- | ---: |
| [`wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors`](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/blob/main/split_files/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors) → `models/diffusion_models/` | 14,3 GB |
| [`wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors`](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/blob/main/split_files/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors) → `models/diffusion_models/` | 14,3 GB |
| [`umt5_xxl_fp8_e4m3fn_scaled.safetensors`](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/blob/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors) → `models/text_encoders/` | 6,74 GB |
| [`wan_2.1_vae.safetensors`](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/blob/main/split_files/vae/wan_2.1_vae.safetensors) → `models/vae/` | 254 MB |

In Aufgabe 20 müssen ComfyUI-Version, Workflow-JSON, Modellrevisionen und Prüfsummen festgeschrieben und **ohne Inferenz** auf vorhandene Nodes und korrekte Dateipfade geprüft werden. [ComfyUI weist darauf hin, dass neue Nodes in stabilen Versionen fehlen können](https://docs.comfy.org/tutorials/video/wan/wan2_2). Optionale LoRAs oder Beschleuniger werden nicht als stillschweigende Voraussetzung angenommen.

## Vorgesehener automatischer Ablauf

1. Nach Skriptfreigabe zerlegt der Worker jede CLOUD-Szene in geplante Wan-Clips und legt Prompt, Seed, Auflösung, Framezahl und Workflow-Version fest. Jeder visuelle Clip bleibt `AI_GENERATED_VIDEO`; bei Fehlern gibt es keinen Pexels-Fallback.
2. Der Worker übergibt den Auftrag an eine separat deployte Modal-Funktion mit **genau einer** A100-80GB. Dort startet ComfyUI intern; der Worker reicht eine versionierte Workflow-JSON über die [lokale ComfyUI-Server-API `/prompt` und `/history/{prompt_id}`](https://github.com/Comfy-Org/ComfyUI/blob/master/script_examples/websockets_api_example.py) ein. ComfyUI ist nicht öffentlich erreichbar. Vor dem GPU-Job wird geprüft, dass alle Modellgewichte bereits auf einem persistenten Volume liegen.
3. Der erzeugte Clip wird in ein getrenntes Ergebnis-Volume geschrieben und dort persistiert. Der Modal-Aufruf meldet nur Kennung, Pfad und technische Metadaten zurück. Der Worker lädt die Datei über SDK oder die dokumentierte CLI herunter; die konkrete Schnittstelle und ihre Fehlerfälle werden in Aufgabe 21 mit Testdateien implementiert.
4. Erst nach erfolgreicher Datei-, Prüfsummen- und `ffprobe`-Prüfung wird der Clip in den lokalen Medienspeicher übernommen. Manifest und Jobzustand enthalten Modell-/Workflow-Version, Seed, Prompt-Referenz, Laufzeit, Dateipfad und SHA-256. FFmpeg/Remotion/Piper erstellen auf Ubuntu das fertige Video, das die Weboberfläche abspielt. **Codex und manuelle Browserbedienung sind zur Laufzeit nicht beteiligt.**

Die Gewichte werden erst in einem späteren, kostengeprüften Schritt in das Modal-Volume übertragen. Dieser Entwurf löst jetzt keinen Download von rund 36 GB und keine Modal-Nutzung aus.

## Kosten, Guthaben und Laufzeit – nur Planung

[Modal nennt aktuell 30 USD monatlich enthaltene Compute-Nutzung im Starter-Tarif](https://modal.com/pricing). Das ist kein Nachweis für ein vorhandenes Guthaben **dieses** Kontos. Laut derselben Preisseite kostet eine A100 mit 80 GB **0,000694 USD pro GPU-Sekunde**, also rechnerisch rund **2,50 USD pro GPU-Stunde**. CPU (0,0000131 USD pro Core-Sekunde), RAM (0,00000222 USD pro GiB-Sekunde), eventuell Volume-Speicher und andere Ressourcen kommen hinzu. GPU-Kaltstart, Modellladen und fehlgeschlagene Versuche können ebenfalls Ressourcen verbrauchen. Der Nutzer hat höchstens **10 USD Brutto-Ressourcenverbrauch pro Testvideo innerhalb nachgewiesener Gratis-Credits** und **0 USD Nettokosten** festgelegt.

| Reines Rechenbeispiel, **keine gemessene Wan-Laufzeit** | GPU-Zeit | GPU-Anteil zum aktuellen Listenpreis |
| --- | ---: | ---: |
| 6 Clips × angenommene 10 Minuten | 1 Stunde | ca. 2,50 USD |
| 12 Clips × angenommene 20 Minuten | 4 Stunden | ca. 9,99 USD |

Schon das zweite Beispiel lässt praktisch keinen Platz für CPU, RAM, Initialisierung oder Fehlversuche innerhalb der 10-USD-Grenze. Für 30–60 Sekunden können je nach Clipdauer und Schnitt mehr als sechs Rohclips nötig sein. Die [Modal-Standardlaufzeit pro Funktion beträgt fünf Minuten](https://modal.com/docs/guide/timeouts); in Aufgabe 20 wird ein ausdrücklicher Timeout gesetzt und in Aufgabe 22 eine Gesamtlaufzeit- und Clipzahlgrenze. Die tatsächliche Inferenzdauer und der VRAM-Bedarf sind unbekannt und werden erst in Aufgabe 24 gemessen. Aus den Dokumenten lässt sich **keine** verlässliche Laufzeit- oder Kostenprognose für dieses konkrete Video ableiten.

[Modal verlangt eine hinterlegte Zahlungsmethode](https://modal.com/docs/guide/billing). [Workspace-Budgets begrenzen Bruttonutzung, Spend-Limits begrenzen Nettokosten nach Credits](https://modal.com/docs/guide/budgets). Das voreingestellte Spend-Limit kann **größer als null** sein. Die Dokumentation bestätigt hier nicht, ob das konkrete Konto einen benutzerdefinierten Wert **0 USD** setzen und wirksam durchsetzen kann. Environment-Budgets sind laut Modal nur bei Team/Enterprise verfügbar und dürfen für Starter nicht vorausgesetzt werden. **Sperre für Aufgabe 24:** Vor jeder echten GPU-Ausführung müssen tatsächliche Credits, aktueller Tarif, Workspace-Budget, wirksame Null-Nettokosten-Grenze, verbleibendes 10-USD-Bruttobudget und die geplante Clipzahl im Modal-Dashboard bzw. mit belastbarem Kontonachweis geprüft sein. Wenn eine Null-Grenze nicht nachweisbar ist, wird kein echter GPU-Job gestartet. Ein App-seitiger Timeout oder Kostenschätzer allein schützt nicht vor einer Rechnung.

## Offene Risiken und Entscheidung für den Live-Test

| Risiko | Entscheidung / Nachweis in späterer Aufgabe |
| --- | --- |
| ComfyUI-Nodes oder FP8-Dateien passen nicht zur fixierten Version | Aufgabe 20: Versionen/Hashes pinnen und Workflow statisch prüfen. |
| 720 × 1280 bei gewählter Framezahl überschreitet VRAM oder Zeitbudget | Aufgabe 24: nach Kostenfreigabe zunächst kleinsten geplanten CLOUD-Clip messen; bei Fehler transparent stoppen und Parameter nur als dokumentierte Produktänderung anpassen. Die 80-GB-Angabe des Wan-Python-Beispiels ist kein ComfyUI-Benchmark. |
| Fünf-Sekunden-Clips decken Szenendauer/Bewegung nicht sauber ab | Aufgaben 21–24: Mehrclip-Planung, 16→24-fps-Umsetzung und Wiedergabe im fertigen Video prüfen; keine bloße Dateiverkettung als Qualitätsnachweis. |
| Downloads, Kaltstart, Wiederholungen und Dateitransfer verbrauchen Budget | Aufgaben 20–22: persistente Gewichte, eine GPU gleichzeitig, harte Clip-/Timeoutgrenzen, keine automatischen teuren Wiederholungen und kontrollierte Transfer-/Fehlertests. |
| Modal-Credits oder Spend-Limit reichen nicht für 0 USD Nettokosten | Aufgabe 24 bleibt gesperrt, bis der Kontoinhaber den tatsächlichen Dashboard-Zustand nachgewiesen hat. Keine Kostenfreigabe durch bloßes Hinterlegen einer Zahlungsmethode. |

**Prüfergebnis von Aufgabe 05:** T2V-Workflow, vier Gewichte, Hochformat, A100-80GB-Auswahl, automatisierbarer Rücktransfer und Kostenmodell sind anhand offizieller Anbieterquellen entworfen. Die reale Funktion, Qualität, Dauer, VRAM-Belegung und Rechnung sind damit **noch nicht** bestätigt. Der nächste Umsetzungsschritt ist Aufgabe 06, die lauffähige Webanwendung; der erste echte CLOUD-Clip bleibt Aufgabe 24.
