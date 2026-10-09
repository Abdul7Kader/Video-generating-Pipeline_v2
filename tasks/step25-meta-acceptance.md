# Meta-Verbindungen – zweiter Punkt der Fünferliste

Stand: 09.10.2026. Auftrag: „mach 2“, anschließend Fortsetzung ausdrücklich bestätigt. Instagram-/Facebook-Verbindungen aus Schritt 25 technisch ergänzen; keine Uploadadapter 29/30 oder Folgeaufgaben. Vorheriger Git-Stand `da01e30`, gleicher Windows-v2-Checkout und Branch `codex/step10-in-progress`. Kriterien aus [todo.md](todo.md) bleiben unverändert; Gesamtabschluss 25 und Live-Abnahmen bleiben offen.

## Implementiert

- Facebook Login mit getrennten, festen Rückwegen für `facebook` und `instagram`, Code-Austausch und anschließender Long-Lived-Token-Konvertierung. API-Version **v26.0** fest im Code. Meta besitzt in diesem Pfad keinen verwendeten Refresh-Token-Grant: „Zugang prüfen“ prüft den vorhandenen Zugang, ohne sein Ablaufdatum zu verlängern; abgelaufene Zugänge verlangen neue Zustimmung.
- Eigene App und fest konfigurierte `meta_page_id`. Facebook-Ziel ist diese Seite; Instagram-Ziel ist ausschließlich deren `instagram_business_account`, kein Privatkonto oder erstes beliebiges Ergebnis. App-ID, Benutzertyp/-ID, gültiges Token, Token-/Datenzugriffsablauf, tatsächliche Scopes, erteilte Berechtigungen, Seitenzugriff und Content-Aufgaben werden geprüft. App-/Seiten-/Versionsänderung verändert die gespeicherte Konfigurationsbindung. Ein neuer Zielaccount wird bei späterer Prüfung nicht still übernommen.
- Kurzlebiges Token vor Konvertierung und langes Token vor Kontoabfrage dauerhaft verschlüsselt gespeichert. Fehlversuch lässt widerrufbare Zugangsdaten in `REAUTH_REQUIRED`, fehlende Scopes ergeben `LIMITED`. AES-GCM und externer privater Schlüssel bleiben die vorhandenen Mechanismen; keine neue Kryptobibliothek oder globale Konfiguration.
- Gemeinsame PostgreSQL-Sitzungssperre für beide Meta-Plattformen. App-Widerruf betrifft denselben App-/Benutzergrant: passende lokale Verbindungen und noch offene Zustimmungen werden gemeinsam entfernt beziehungsweise bei Fehler gesperrt. Unterschiedliche bestätigte Benutzer werden erhalten; bei unbekannter Benutzeridentität wird konservativ ein möglicherweise gemeinsamer Grant gesperrt. `success=true` von Meta ist für bestätigten Widerruf erforderlich. Weitere Zustimmungen derselben App bleiben bei ausstehendem Widerruf gesperrt.
- Oberfläche zeigt Ablauf, „Zugang prüfen“, gemeinsamen Widerrufhinweis und tatsächliche Entfernung beider Verbindungen. Schlüsselverlustbereinigung ist weiterhin eine ausdrücklich bestätigte lokale Entfernung der ausgewählten Verbindung, ohne behaupteten Remote-Widerruf; weitere betroffene Zugänge separat entfernen/prüfen.
- Private Einrichtungs-CLI unterstützt `--provider instagram --provider facebook` und fragt die Seiten-ID ab. Defaults bleiben deaktiviert. MVP-/aktuelle Nullkosten-/Konto-/Reviewnachweise bleiben notwendige Aktivierungsschranken. X bleibt unverändert gesperrt.
- Migration **0010** erweitert nur die beiden Social-Provider-Constraints; Rückmigration verwirft weder aktive noch getrennte Meta-Verbindungsdatensätze oder offene Zustimmungen. Publication-Readiness und serverseitige Options-/Freigabeprüfung blockieren Meta ausdrücklich bis zu den noch fehlenden Uploadadaptern. Eine Verbindung startet keinen Upload.

## Sicherheit und Quellen

Schützenswert: App-Secret, OAuth-Codes, Benutzer-/Seitentokens, Kontoidentität und Zustimmungen. Vertrauensgrenzen: Browser → lokale API, API → Meta, private Konfiguration/Schlüssel → Datenbank. Missbrauchsfälle: State-Replay, fremde Sitzung/Origin, Token-/App-/Kontotausch, fremde Seite, unzulässiger Next-Link, übergroße Antwort, geänderter Zielaccount und Wiederbelebung nach Widerruf.

Verwendet werden vorhandene einmalige browser-/sitzungsgebundene State-Checkpoints, feste Callback-Hostprüfung, getrennte Callback-Pfade, Betreiberzugang und Originprüfung für Mutationen, parametrisierte SQL-Abfragen und verschlüsselte private Tokens. Nur feste HTTPS-Graph-Endpunkte, TLS-Zertifikatsprüfung, kein Redirect oder Umgebungsproxy; 10-s-HTTP-Timeout und 256-KiB-Antwortgrenze. Maximal zehn Seitenlisten-Antworten, ausschließlich selbst konstruierte URLs mit begrenztem Cursor, keine Übernahme von `paging.next`. App-Secret-Proof für Benutzerabfragen. Browser/Antworten enthalten keine Tokens; httpx-Logs entfernen Queryparameter der offiziellen GET-Token-/Debug-Endpunkte, Callback-Logs entfernen Code/State. HTTP-Debugtraces mit Requestheaders nicht im Betrieb einschalten.

Primärquellen am 09.10.2026 geprüft:

- [Meta: Instagram API mit Facebook Login / offizielle Postman-Dokumentation](https://www.postman.com/meta/workspace/instagram/documentation/23987686-9386f468-7714-490f-9bfc-9442db5c8f00): professionelle, mit einer Facebook-Seite verknüpfte Instagram-Ziele und Berechtigungen.
- [Meta Python Business SDK, Versionskonfiguration](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/apiconfig.py): v26.0 als aktuelle SDK-API-Version; keine SDK-Installation vorgenommen.
- [Meta Python Business SDK, Session](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/session.py) und [User](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/user.py): Graph-Endpunkt, App-Secret-Proof, Konten-/Berechtigungsoperationen.
- [Meta, archivierter PHP-SDK-OAuth2Client](https://github.com/facebookarchive/php-graph-sdk/blob/5.x/src/Facebook/Authentication/OAuth2Client.php): Code- und `fb_exchange_token`-Austausch. **Historische Protokollreferenz, keine aktuelle Sicherheitsnorm oder gepflegte Abhängigkeit.** Aktuelle Entwicklerseiten für [Login](https://developers.facebook.com/docs/facebook-login/manually-build-a-login-flow/), [lange Tokens](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived/) und [Changelog](https://developers.facebook.com/docs/graph-api/changelog/) lieferten beim direkten Abruf 429; deren vollständiger aktueller Abgleich und App-spezifische Gültigkeit bleiben vor Live-Aktivierung offen.
- [OWASP OAuth2 Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html): State-Bindung, getrennte Rückwege und begrenzte Rechte. Der implementierte Facebook-Codefluss behauptet **keine PKCE-Unterstützung**; ein aktueller kompatibler Meta-PKCE-Vertrag wurde nicht nachgewiesen. Vor Live-Freigabe App-/Loginmodell, aktuelle Provider-Sicherheitsvorgaben und den exakten zulässigen Rückweg prüfen; keine beliebige öffentliche Callback-URL oder Ausnahme hinzugefügt.

Keine Änderungen an Passwortverfahren, TLS-/Kryptoprofil oder Paketständen. Der in 25 noch offene BSI-PDF-Versionsabgleich wird hier nicht als erledigt behauptet. Keine Sicherheitsgarantie, Zertifizierung oder behauptete Rechtskonformität.

## Tatsächlich geprüft

**97 verschiedene gezielte Backendfälle**, darunter **67 echte Dienstintegrationen**, keine übersprungen. Plattformantworten ausschließlich synthetisch über HTTPx MockTransport; PostgreSQL 17, Redis 7, RQ/Mediengateway/Worker und Test-MP4s tatsächlich lokal verwendet. Kein vollständiger historischer Backend-Gesamtlauf und keine macOS-/Linux-Ausführung behauptet.

| Prüfung | Ergebnis |
|---|---|
| Meta/Social/YouTube-Protokoll, Publication-/Worker-Funktionen | 30/30, final 1,864 s |
| Meta-/Social-Integration | 28/28, 24,780 s; danach neuer Benutzertrennungsfall plus Wiederholung des erweiterten Widerruffalls 2/2 in 3,162 s; **29 verschiedene Fälle** |
| Publication, Datenbank, API, Speech-/Graphics-Migrationsschutz | **21 verschiedene erfolgreiche Fälle** im kombinierten Lauf |
| YouTube-/RQ-/Medienintegration nach Migrationstestkorrektur | 17/17, 58,045 s |
| Projekttests `unittest discover -s tasks -p 'test*.py'` | 10/10, 0,032 s |
| `npm run build --prefix web` | TypeScript und Vite 6.4.4 erfolgreich |
| `npm audit --prefix web --package-lock-only --json` | 0 bekannte Meldungen |
| `pip check` | Keine defekten Anforderungen |

Nachvollziehbare Korrekturen: Ein neuer Test erwartete den API-Fehlerwrapper statt der internen HTTPException-Struktur; korrigiert und erfolgreich nachgeprüft. Der bisherige YouTube-Migrationstest entfernte Migration 9, ließ aber neue Migration 10 stehen; der Lauf verweigerte den nicht zusammenhängenden Versionsstand, weitere Tests desselben Schemas konnten die entfernte Uploadtabelle nicht nutzen (zehn Fehler). Korrekte Rückreihenfolge 10 → 9 ergänzt; anschließend alle 17 YouTube-Fälle erfolgreich. Keine Prüfung oder Datenbankkontrolle abgeschwächt. Der erste Lauf enthielt durch einen Testklassenimport doppelt entdeckte Funktionsfälle; Import durch Modulverweis ersetzt, Zählung oben enthält nur eindeutige Fälle.

## Offen und sichere Übergabe

Echte Meta-App, Kosten-/Konto-/Testnutzer-/Review-/Berechtigungsnachweise, konkrete zulässige Callback-Einrichtung und tatsächliche Verbindung/Prüfung/Widerruf auf dem Installationsrechner bleiben offen. Die derzeitige Loopback-Konfiguration ist keine nachgewiesene Meta-App-Konfiguration; notwendiges HTTPS am Rückweg ist gegebenenfalls zunächst auf dem Installationsrechner bereitzustellen. Browser-/Bedienungsabnahme macht der Betreiber. CLOUD-Abnahme 24/M3 bleibt Voraussetzung für Aktivierung. Es gab keinen echten Meta-/Google-/TikTok-Aufruf, keinen Upload und keinen Modal-/GPU-Aufruf. Betreiberinstallation wurde nicht aktualisiert.

Eigene markierte Testcontainer und private temporäre Dienstkonfiguration nach den Prüfungen entfernt; keine Betreibercontainer oder Medien verändert. Code/Dokumentation werden auf dem bestehenden GitHub-Branch gesichert; tatsächlichen Commit-/Push-/Arbeitsstand vor nächster Arbeit prüfen. Relevante Dateien: `backend/app/meta_providers.py`, `social_api.py`, `social_providers.py`, `social_config.py`, Migration 0010, `test_meta*.py`, `web/src/PlatformConnections.tsx`, [API-Vertrag](api-contract.md).

Der aktuelle Auftrag endet mit diesem technischen Punkt. Kein leerer Nachfolgechat; weitere Punkte der Fünferliste sind nicht beauftragt. Nächste unabhängige Entwicklung bei ausdrücklicher Beauftragung: Punkt 3, Instagram-Reels-Adapter 29. Live-Verbindungen bleiben bis zu den oben genannten Nachweisen gesperrt. Exakten Checkout, Branch und sichere Konfigurationsmechanismen beibehalten; keine Secrets in Übergaben.
