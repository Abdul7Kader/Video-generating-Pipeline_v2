# Projektanweisungen für Codex

Vor Änderungen [STATE.md](STATE.md), [tasks/todo.md](tasks/todo.md) und [tasks/plan.md](tasks/plan.md) lesen. Die nächste Aufgabe aus dem aktuellen Status ermitteln. Nach jedem erledigten Schritt Status und Prüfnachweise in diesen Dateien aktualisieren.

- Entwickle über das GitHub-Repository. Die Anwendung soll auf unterstützten Windows-, macOS- und Linux-Rechnern mit lokal installierten Voraussetzungen laufen; Ubuntu ist ein möglicher Zielrechner, keine feste Laufzeitvorgabe. Verlange für Codearbeit keinen Zugriff auf einen früheren Rechner, dessen `localhost`, `.env` oder Browseranmeldung. `LOKAL` ist ein Videomodus, kein Entwicklungsort.
- Führe `npm run build --prefix web` und die passenden Python-Tests aus. Für Datenbank- oder Dienständerungen zusätzlich eine echte Integrationsprüfung; ohne verfügbare Testumgebung die Prüfung als offen benennen.
- Kein Gemini-API-Key und keine bezahlte API als Ersatz für das Gemini-Pro-Abo. Antigravity-Live-Tests erst auf einem dafür angemeldeten Host-Worker des Installationsrechners. Ein Test- oder Entwicklungsrechner darf selbst Installationsrechner sein, wenn seine Anmeldung und Kostensperre nachgewiesen sind. Kein Modal-GPU-Job ohne nachgewiesene Gratis-Credits und wirksame Grenze von 0 USD Nettokosten.
- Keine Secrets, `.env`, Tokens, heruntergeladenen Clips oder Modellgewichte committen. `LOKAL` enthält nur `STOCK_VIDEO`, `CLOUD` nur `AI_GENERATED_VIDEO`; keine stillen Fallbacks.
- Ändere Abnahmekriterien nur bei einer begründeten Produktentscheidung. Zeige dem Betreiber sichtbare Zwischenstände und halte ungetestete Funktionen ausdrücklich als offen fest.
