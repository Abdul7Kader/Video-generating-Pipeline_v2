# Schritt 03 – Gemini-Pro-Skriptprobe ohne API

## Automatischer Skriptweg

1. Die Anwendung erzeugt aus Idee und Modus einen Auftrag nach `make_prompt` in `script_probe.py`.
2. Ihr Worker startet die offizielle Antigravity CLI mit dem Google-AI-Pro-Konto des Betreibers. Der Prototyp `agy_script_probe.py` zeigt den Aufruf in einem isolierten temporären Arbeitsordner; die Identität der dort bereits gespeicherten CLI-Anmeldung wird vor der Webintegration mit dem Abo-Konto abgeglichen.
3. Die JSON-Antwort wird vor Speicherung und Bearbeitung validiert. Bei leerer oder ungültiger Antwort schlägt der Auftrag sichtbar fehl.
4. Die beiden repräsentativen Probeaufträge liegen in `prompt-balkon-lokal.txt` und `prompt-regen-cloud.txt`.

Es wird kein Gemini-API-Key benötigt und kein Aufruf der Gemini Developer API ausgelöst. Die Webanwendung ist noch nicht implementiert; die automatische CLI-Ausführung und Schema-Prüfung sind als Prototyp belegt. Die einmalige Anmeldung für den späteren Ubuntu-Worker ist in Aufgabe 10 und beim Deployment zu prüfen.
Der Prototyp entfernt mögliche API-Key-Umgebungsvariablen und startet ohne pauschale Werkzeugfreigabe. Laut [Antigravity-Dokumentation](https://antigravity.google/docs/cli/credits/) kann `useG1Credits` zusätzliche Credits nach Ausschöpfen der Basisquote verbrauchen. Diese Einstellung ist hier nicht aktiv (die CLI-Konfigurationsdatei fehlt, dokumentierter Standard ist `false`); bei einer vorhandenen Konfiguration verlangt der Prototyp explizit `false` und bricht sonst ab.

## V1-Datenvertrag

Das Top-Level-JSON enthält ausschließlich `title`, `language`, `mode`, `target_duration_seconds` und `scenes`. `language` ist `de-DE`; `mode` ist `LOKAL` oder `CLOUD`. Der Titel ist 1–120 Zeichen lang. Die Zielzeit ist eine ganze Zahl zwischen 30 und 60 Sekunden.

Es gibt 6–10 Szenen. Jede hat einen fortlaufenden `index` ab 1, eine ganzzahlige `duration_seconds` von 3–12, einen deutschen `narration`-Text (1–400 Zeichen), eine konkrete `visual_description` (1–600 Zeichen) und einen `media_type`. Die Szenendauern ergeben exakt die Zielzeit. Tatsächliche TTS-Dauern werden später in Aufgabe 15 gemessen und können eine Korrektur des Skripts nötig machen.

| Modus | `media_type` je Szene | Weitere Pflichtdaten je Szene | Andere Quelle |
| --- | --- | --- | --- |
| `LOKAL` | `STOCK_VIDEO` | `pexels_queries`: 2–4 unterschiedliche Suchbegriffe, je 1–100 Zeichen | `wan_prompt` verboten |
| `CLOUD` | `AI_GENERATED_VIDEO` | `wan_prompt`: englischer T2V-Prompt, 1–1000 Zeichen | `pexels_queries` verboten |

Zusätzliche oder fehlende Schlüssel sowie eine Mischung der Medientypen werden abgewiesen. Der Prototyp verwendet ausschließlich die Python-Standardbibliothek.

## Prüfbefehle

```powershell
python -m unittest discover -s tasks -p test_script_probe.py -v
python tasks/script_probe.py validate --mode LOKAL --file <antwort-balkon.json>
python tasks/script_probe.py validate --mode CLOUD --file <antwort-regen.json>
python tasks/agy_script_probe.py --idea "Ein bienenfreundlicher Stadtbalkon in fünf Schritten" --mode LOKAL --out tasks/response-balkon-agy.json
python tasks/agy_script_probe.py --idea "Ein Regentag in der Stadt" --mode CLOUD --out tasks/response-regen-agy.json
```

## Ergebnisstand

- [x] Prompt- und JSON-Vertrag erstellt.
- [x] Positive Beispiele für beide Modi und Negativfälle (ungültiges JSON, fehlende Felder, falscher Medientyp, falsche Szenenzahl/Reihenfolge/Dauer) lokal geprüft.
- [x] Echte Gemini-Pro-Antwort für Beispiel A in `response-balkon-lokal.json` gespeichert und gegen den Vertrag geprüft: 7 Szenen, 42 Sekunden, `LOKAL`.
- [x] Echte Gemini-Pro-Antwort für Beispiel B in `response-regen-cloud.json` gespeichert und gegen den Vertrag geprüft: 6 Szenen, 36 Sekunden, `CLOUD`.
- [x] Automatische Antigravity-Pro-Antwort für Beispiel A in `response-balkon-agy.json`: 6 Szenen, 40 Sekunden, `LOKAL`.
- [x] Automatische Antigravity-Pro-Antwort für Beispiel B in `response-regen-agy.json`: 6 Szenen, 36 Sekunden, `CLOUD`.

**Abnahme:** Alle vier echten Antworten waren ohne Formatkorrektur parsebar. Die fünf lokalen Tests, einschließlich ungültigem JSON und Teilausgaben, bestehen. Zwei Proben erfolgten in der angemeldeten Gemini-Webanwendung mit ausgewähltem Pro-Modell, zwei über Antigravity CLI mit `gemini-3.1-pro-low`; es wurde keine Gemini API verwendet.

**Produktentscheidung nach der Probe:** Der Betreiber will die Skripterstellung durch eine Nachricht in der eigenen Weboberfläche automatisch starten, ohne Codex zur Laufzeit und ohne manuelles Kopieren. Die offizielle Antigravity CLI bietet einen Headless-Modus mit JSON-Ausgabe und Pro-Modellen. Der direkte Aufruf im Projektordner scheiterte, weil der Agent dort einen Shell-Befehl anforderte, den der Headless-Modus ohne Freigabe ablehnte. Im isolierten temporären Arbeitsordner funktionierten beide Skriptaufträge ohne pauschale Werkzeugfreigabe. Die vorhandene Gemini CLI 0.60.0 wurde vom Google-Dienst für Einzelkonten mit `UNSUPPORTED_CLIENT` abgewiesen. Kein kostenpflichtiger API-Fallback und keine stille manuelle Übergabe.
