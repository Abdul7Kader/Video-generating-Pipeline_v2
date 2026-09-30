# UI-Nacharbeit – Ladeanzeigen und Bedienung

Abgenommen am 30. September 2026 auf dem Windows-Entwicklungsrechner. Betreiberwunsch nach Schritt 12: sichtbare Wartezeiten, bessere Bedienung und erkennbare Klickbarkeit durch Design ohne zusätzliche Bedienhinweise.

## Ergebnis

- Einheitliche Ladebalken für Verbindungstest, Projektanlage, Projekt-/Skriptladen, Skriptauftrag, Warte-/Generierungsphase, Ergebnisdownload, Versionsspeicherung, Freigabe/Übergabe und Produktionswartezeit. Lange Skriptaufträge zeigen die Zeit seit Auftragsanlage. Keine geschätzten Prozentwerte oder Restzeiten.
- Hauptaktionen sind gefüllt, Nebenaktionen gerahmt. Aktive Buttons haben Hover-, Druck- und Fokuszustände; deaktivierte Aktionen sind flach, gedämpft und gestrichelt. Statusanzeigen und Ablaufmarkierungen haben keine Buttonoptik. Dropdown und Eingabefelder reagieren auf Hover/Fokus. Keine Erklärtexte zur Klickbarkeit hinzugefügt.
- Editoraktionen bleiben am unteren Rand erreichbar. Fokus geht zum Titel und nach Speichern/Verwerfen zurück zur Vorschau. Unveränderte Versionen können nicht erneut gespeichert werden; laufendes Speichern sperrt die Eingaben. Beim Neuladen warnt die native Browserabfrage vor ungespeicherten Änderungen.
- Anfragen sind auf 20 Sekunden aktive Browserzeit begrenzt. Transport-/Ladefehler beenden die jeweilige Anfrageanzeige und lassen erneutes Laden zu. Auch ein Fehler beim ersten Wiederherstellen bietet „Neu laden“. Ein fertig erzeugtes, aber nicht geladenes Skript kann gezielt erneut geladen werden. Erfolgreiches Laden entfernt die erledigte Fehlermeldung.
- Überlappende Skriptstatusabfragen werden vermieden. Antworten zu einem früheren Projekt überschreiben kein inzwischen neu angelegtes Projekt. Projektanlage ist während Editor, Freigabe und unmittelbaren Speicher-/Ladeaktionen gesperrt.

Umsetzung: [Ladeanzeige](../web/src/LoadingBar.tsx), [Anfragen](../web/src/request.ts), [Studio](../web/src/Studio.tsx), [Editor](../web/src/ScriptEditor.tsx), [Gestaltung](../web/src/studio.css).

## Prüfungen

- `npm run build --prefix web`: TypeScript und Vite-Produktionsbuild bestanden. Acht vorhandene Python-Projekttests bestanden. Backend-/Datenbankvertrag unverändert; die 29 Backendtests aus Schritt 12 wurden für diese ausschließlich im Frontend liegende Änderung nicht erneut ausgeführt.
- Echter separater Chrome-Browser mit DevTools-Protokoll gegen die normale Compose-Anwendung unter `http://127.0.0.1:4177/`. Maus- und Tastaturaktionen; reale Projektanlage, Skriptspeicherung und Freigabe. Skriptgenerierung wurde gezielt abgefangen; QUEUED/RUNNING/COMPLETED und längere Produktionswartezeiten waren kontrollierte Browserantworten. Kein Antigravity-/Gemini-/Modal-Aufruf. Der echte Host-Worker stoppte die freigegebenen Testläufe weiterhin mit der fehlenden Videoerzeugung; kein Video/Artefakt erzeugt.
- Beide Modi durchlaufen: Projekt speichern → Skriptauftrag übergeben → warten → generieren → fertiges Skript laden → neu laden → bearbeiten/speichern → freigeben → Produktionswartezeit → echte sichtbare Produktionsgrenze. Jede Wartephase besitzt eine benannte `progressbar` ohne `aria-valuenow`.
- Kontrolliertes `503` beim Ergebnisladen: Ladebalken verschwindet, „Skript erneut laden“ funktioniert, erledigte Fehlermeldung verschwindet. Blockierte Projekt-Leseanfrage endet nach dem tatsächlichen 20-Sekunden-Limit; erneutes Laden erfolgreich. Kontrollierter Fehler beim ersten Wiederherstellen bleibt erneut ladbar.
- Verzögerte alte Skriptantwort nach Neuanlage eines weiteren Projekts: neue Projektansicht und eigener Skriptstatus bleiben erhalten.
- Editor: Titel erhält Fokus; Tab wechselt zum ersten Dauerfeld. Unverändertes Speichern deaktiviert/gestrichelt; nach Änderung aktiviert. Speicherleiste im sichtbaren Viewport; Speichern erhält vollständige Szenenmetadaten. Native `beforeunload`-Abfrage abgebrochen: Entwurf bleibt erhalten. Verwerfen bringt Fokus zur Vorschau zurück.
- 320, 768, 1024 und 1440 Pixel Breite ohne horizontalen Überlauf; Buttons mindestens 44 Pixel hoch. Reduzierte Bewegung schaltet die Ladeanimation ab. Aktive Buttons besitzen solide Rahmen/Pointer, passive Statusanzeigen keine Rahmen. Keine JavaScript-Ausnahmen; Screenshots visuell geprüft und außerhalb von Git aufbewahrt.
- Normale Webanwendung aktualisiert; API, Datenbank, Redis und Host-Worker bereit. Temporärer Chrome-Test und Prüfscripte bereinigt. Die klar benannten UI-Testprojekte enthalten ausschließlich kontrollierte Skriptmetadaten und bleiben als Datenbank-Prüfstand erhalten; die Projektauswahl des Betreibers im In-App-Browser wurde nicht verändert.

Technische Referenzen: [MDN: unbestimmter Fortschritt ohne Prozentwert](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/progressbar_role), [MDN: AbortSignal.timeout](https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/timeout_static).

## Grenze

Die Warteanzeigen für laufende Videoproduktion sind mit kontrollierten Zustandsantworten geprüft. Eine echte Produktionskette, echte Videos und Wiedergabe bleiben Schritte 13–19. Diese UI-Nacharbeit ändert deren Abnahmekriterien nicht.
