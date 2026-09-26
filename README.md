# Video-generating-Pipeline v2

Stand: Planung und Skriptprototyp. Die Weboberfläche und Videoproduktion sind noch nicht implementiert.

Die geplante Anwendung nimmt eine Videoidee und den Modus `LOKAL` oder `CLOUD` in einer Weboberfläche entgegen. Ein Hintergrundauftrag soll mit dem vorhandenen Google-AI-Pro-Konto über die offizielle Antigravity CLI ein Skript erzeugen, ohne Gemini Developer API und ohne Codex zur Laufzeit. Nach Prüfung und Freigabe wird das Video erstellt. Social-Media-Veröffentlichungen folgen erst nach der Videoabnahme.

Der Prototyp unter [`tasks/`](tasks/) enthält den [Umsetzungsplan](tasks/plan.md), die [Aufgabenliste](tasks/todo.md), das [Skriptformat](tasks/script-probe.md) und vier geprüfte Beispielskripte. Zwei davon wurden automatisch mit Antigravity CLI erzeugt. Die [Pexels-Probe](tasks/pexels-probe.md) hat drei echte Suchtreffer und einen geprüften Download nachgewiesen. Die fertigen Videos sind noch nicht implementiert.

## Lokale Prüfung

```powershell
python -m unittest discover -s tasks -p test_script_probe.py -v
python tasks/script_probe.py validate --mode LOKAL --file tasks/response-balkon-agy.json
python tasks/script_probe.py validate --mode CLOUD --file tasks/response-regen-agy.json
```

Für eine neue automatische Skriptprobe muss die offizielle Antigravity CLI (`agy`) installiert und mit dem gewünschten Google-Konto angemeldet sein. Der Prototyp verweigert eine aktivierte automatische AI-Credit-Überziehung und verwendet keinen Gemini-API-Key.

```powershell
python tasks/agy_script_probe.py --idea "Ein Regentag in der Stadt" --mode CLOUD --out tasks/neues-skript.json
```

Die Einbindung in die Weboberfläche ist als Aufgabe 10 geplant. Sobald eine lauffähige Oberfläche mit sichtbarer Skript- oder Videovorschau vorliegt, kann sie vorgeführt werden.
