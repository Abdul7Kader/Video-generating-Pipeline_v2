# Schritt 26 – Veröffentlichungsfreigabe

Stand: 09.10.2026. Beauftragt durch „mach die 5“; Originalpunkt 5 entspricht Aufgabe 26. **Technischer Teil implementiert und funktional geprüft; Betreiber-Bedienungsabnahme und Gesamtabschluss offen.** Voraussetzungen 24/M3 und echte Plattformnachweise aus 25 fehlen weiterhin. Keine öffentliche Bereitstellung, reale Plattformanfrage, Veröffentlichung oder Modal-Nutzung. Uploadadapter 27–31 wurden nicht implementiert.

## Implementiert

- „Veröffentlichung vorbereiten“ unter dem fertigen Video: geschützte Videovorschau, Titel/Beschreibung, Quellen, Zielgruppen-/KI-/Werbekennzeichnung und fünf Plattformkarten mit konkreten Sperrgründen. Zielkonten und Sichtbarkeit werden bewusst ausgewählt; keine voreingestellte Sichtbarkeit. Instagram/Facebook und X bleiben gesperrt. Quellen werden serverseitig aus dem passenden SCENES-Checkpoint übernommen; fremde oder gemischte Herkunft wird abgewiesen. CLOUD erzwingt die KI-Kennzeichnung; kontrollierte Wan-Testclips dürfen keine Veröffentlichungsfreigabe erhalten.
- Versionierter Entwurf und separate Freigabe der gespeicherten Angaben. Die vorhandene Bild-/Tonfreigabe `VIDEO` bleibt Voraussetzung. Drei ausdrückliche Bestätigungen, aktuelle Skriptversion, Datei-SHA-256 und Herkunftsdigest binden die neue Freigabe an das geprüfte Video. Die Freigabe prüft die echte Datei über den Medien-Worker, nicht nur eine Browserangabe.
- YouTube-Profil: Titel, Beschreibung samt Herkunft, Sichtbarkeit, `containsSyntheticMedia`, `selfDeclaredMadeForKids` und bezahlte Produktplatzierung. TikTok-Profil: Caption samt Herkunft, aktuelle Privacy-Option, `is_aigc`, eigene/fremde Markenwerbung und einzeln gewählte Interaktionen. YouTube-Beschreibung maximal 5000 UTF-8-Bytes, TikTok-Caption maximal 2200 UTF-16-Einheiten. Zu lange Kombinationen werden abgewiesen, Quellen nicht abgeschnitten.
- TikTok: explizite Kontooptionsabfrage mit aktuellem Creator-Namen, erlaubten Sichtbarkeiten/Interaktionen und Höchstdauer. Interaktionen zunächst aus; gesperrte Interaktionen dürfen auch serverseitig nicht aktiviert werden. Music Usage Confirmation sowie bei bezahlter Partnerschaft Branded Content Policy erforderlich; bezahlte Partnerschaft mit `SELF_ONLY` gesperrt. Providerantworten sind begrenzt und validiert, Avatar-/Fremd-URLs werden nicht abgerufen.
- Unveränderlicher Snapshot pro Freigabe: Metadaten, Herkunft, Plattformprofile, Kontokennung, OAuth-Verbindungs-UUID und Konfigurationsfingerabdruck; keine Tokens. Jede neue OAuth-Zustimmung erhält eine neue Verbindungs-UUID, auch für dasselbe Konto. Erneutes Verbinden erfordert daher Speichern und erneute Freigabe.
- Atomar genau ein `QUEUED`-Datensatz je Plattform. Gleichzeitige/wiederholte Freigaben liefern dieselben Kennungen. Entwurfsänderungen entwerten die bisherige Freigabe und entfernen nur noch wartende Aufträge; gestartete Aufträge bleiben unverändert. Projekt-/Provider-Sperren, Versionskonflikte und zusätzliche Datenbankkontrollen verhindern doppelte oder veraltete Aufträge.
- Migration **0008** ergänzt Entwürfe, Freigaben und Auftragssnapshots. Historische Aufträge ohne `release_id` erhalten keine erfundene Zustimmung. Rückmigration verweigert das Verwerfen vorhandener Entwürfe/Freigaben. Keine Datenmigration an einer Betreiberinstallation ausgeführt.

**`QUEUED` bedeutet vorbereitet, nicht veröffentlicht.** Es gibt keine RQ-Uploadzustellung und keinen Uploadworker; API meldet `upload_available=false`. Zukünftige Adapter müssen vor jeder externen Veröffentlichung Datei/Herkunft, aktuelle Freigabe, Konto/Scopes, Kosten-/Reviewnachweise und TikTok-Creatorgrenzen erneut prüfen. Historische Aufträge ohne Freigabesnapshot dürfen sie nicht ausführen. Siehe [API-Vertrag](api-contract.md#veröffentlichungsfreigabe--schritt-26).

## Tatsächlich geprüft

**47 verschiedene gezielte Backendfälle** bestanden, verteilt auf fokussierte Läufe; kein vollständiger historischer Backend-Gesamtlauf behauptet:

- 12 Funktionen (vier Veröffentlichung, acht bestehende Social-Verträge) in **1,978 s**. Vier Veröffentlichungsfunktionen nach letzter Profilkorrektur erneut erfolgreich geprüft.
- Finale **11 Veröffentlichungsintegrationen in 27,541 s**: parallele Freigaben für zwei Plattformen; Revision/Metadatenänderung; reale Dateibeschädigung und falscher SHA; fehlender Zugang/Origin/Scopes/Kosten/MVP; neue Skriptversion/geänderte Herkunft; Kontowechsel und Wiederverbinden desselben Kontos; gestarteter Auftrag/SQL-Snapshotmanipulation; private Sichtbarkeit/Creatorgrenzen; Musik-/Interaktionsbestätigungen; Rückmigration/fehlende VIDEO-Freigabe; TikTok-Eigenkonto-Utility vor jeder Provideranfrage gesperrt.
- 14 bestehende Social-Integrationen nach Änderung der Verbindungsidentität erneut bestanden, gemeinsam mit einem wiederholten Veröffentlichungstest **15 Fälle in 15,756 s**.
- Vier API-Vertrags- und vier Datenbankregeltests erfolgreich; zwei historische Migrationsfälle nach Anpassung der erwarteten Schemaanzahl von sieben auf acht in **2,372 s** bestanden.

Echte getrennte PostgreSQL-/Redis-Dienste, HTTP-API, Medien-Worker-RPC und lokale FFmpeg-Datei-/Manifestprüfung. Pro Test ein isoliertes Schema; synthetische Pexels-Herkunft und OAuth-/Creatorantworten über `httpx.MockTransport`. Eine echte CPU-FFmpeg-MP4 von einer Sekunde dient ausschließlich dem Datei-/Freigabevertrag, nicht dem Nachweis eines vollständigen oder inhaltlich abgenommenen Videos. Kein echter Anbieterzugang verwendet.

Frühe Testfehler: ein Helfer übergab den SHA doppelt; zwei historische Migrationsannahmen erwarteten Schema 7. Helfer/Erwartungen korrigiert und betroffene Prüfungen erneut bestanden. Keine Produktkontrolle abgeschaltet.

**10/10 Projekttests in 0,022 s**, `npm run build --prefix web` mit TypeScript/Vite 6.4.4 bestanden (37 Module). `pip check` und erneutes npm-Audit bestanden, **0 npm-Meldungen**. Keine neuen Pakete; direkte Python-Pins unverändert gegenüber dem heutigen begrenzten OSV-Nachweis aus 25. Keine vollständige Abhängigkeits-/Sicherheitsgarantie.

Belege ignoriert unter `.data/step26-*.log` und `.data/step26-npm-audit.json`. Eigene eindeutig markierte Testcontainer und private temporäre Dienstkonfiguration nach Abschluss entfernt; Betreibercontainer/Daten unverändert. Docker Desktop bleibt gestartet. **Keine Browserprüfung durch Codex.** API/Web einer vorhandenen Betreiberinstallation wurden nicht neu gebaut oder gestartet.

## Offene Abnahme und Aktivierung

Nach Aktualisierung der lokalen Installation (API-Start migriert Schema 8) übernimmt der Betreiber die Bedienungsprüfung:

1. Unter „Speicher & Videos“ anmelden, fertiges aktuelles Video öffnen und Bild/Ton freigeben.
2. „Veröffentlichung vorbereiten“ öffnen; Vorschau, Quellen und Sperrhinweise prüfen. Nur nach tatsächlichen Plattformnachweisen verfügbare Ziele wählen, aktuelle Kontooptionen abrufen und Sichtbarkeit ausdrücklich wählen.
3. Titel/Beschreibung/Zielgruppe/Kennzeichnungen und gegebenenfalls TikTok-Bedingungen prüfen; Entwurf speichern. Gespeicherte Angaben über drei Prüfpunkte bestätigen und Veröffentlichungsfreigabe speichern.
4. Doppelklick, erneutes Laden und Metadatenänderung prüfen: je Plattform nur ein wartender Auftrag; Änderungen erfordern neue Freigabe. Datei-/Kontenänderungen müssen abgewiesen werden. Diese Browserabnahme ist offen, funktionale Negativfälle sind geprüft.

Die private Plattformkonfiguration ergänzt zwei standardmäßig falsche Nachweisfelder: `public_upload_approved` (tatsächlich erforderlichen öffentlichen Upload-Audit nachgewiesen) und TikTok `public_creator_app_confirmed` (zulässige App für einen breiten Creator-Nutzungskreis nachgewiesen). Sie sind **keine Umgehung von Anbieterregeln** und wurden in keiner echten Betreiberkonfiguration aktiviert. `APPROVED` allein macht Uploads nicht öffentlich. Testkonfigurationen mit bestätigten Feldern sind synthetische Vertragsfixtures, keine realen App-Nachweise.

**Offener Produktkonflikt vor 28:** TikTok schließt reine Werkzeuge für eigene/Teamkonten vom Direct Post aus. Der aktuelle lokale Eigengebrauch belegt daher keinen zulässigen Nutzungskreis. Eine lokale Anwendung für einen breiten Creator-Kreis wäre separat zu prüfen; keine solche Produktentscheidung getroffen, keine Abnahmekriterien still geändert. Bis zum Nachweis sperrt der Server bereits Kontooptionsabfrage und Veröffentlichungsfreigabe. Vollständige Export-UX, echte Posts/Status, Audit und zulässiges Appmodell bleiben 28. Echte CLOUD-Abnahme, Konten/Kosten/Rechte und Meta-OAuth bleiben 24–25; X benötigt separate Kostenentscheidung.

## Sicherheit und Quellen

Schützenswert: private MP4, Titel/Beschreibung, Herkunft/Rechte, Zielkonten und verschlüsselte Tokens. Grenzen: Betreiberbrowser → authentisierte API → Datenbank/Medien-Worker → fest erlaubter HTTPS-Anbieter. Missbrauch: CSRF, manipulierte Datei/Herkunft, Kontoverwechslung, veraltete Zustimmung, parallele Aufträge und gefälschte Providerantworten. Gegenmaßnahmen: bestehende Sitzungs-/Originprüfungen, strikte Eingaben, parameterisierte SQL, React-Ausgabekodierung, `no-store`/`no-referrer`, begrenzte feste Providerendpunkte mit TLS-Prüfung, serverseitige Gates und unveränderliche Snapshots. API gibt keine Tokens aus. Obige Negativfälle tatsächlich geprüft; gesamte Sicherheitsabnahme 32 und BSI-Versionsabgleich aus 25 bleiben offen.

Offizielle Quellen am **09.10.2026** geprüft:

- [YouTube Video-Ressource](https://developers.google.com/youtube/v3/docs/videos): Metadaten, Bytegrenzen, Kennzeichnungen und Sichtbarkeit.
- [TikTok Direct Post](https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post), Stand 24.08.2026: Caption/Privacy/KI-/Werbefelder.
- [TikTok Creator-Abfrage](https://developers.tiktok.com/docs/en/content-posting-api-reference-query-creator-info), Stand 04.08.2026: aktuelle Kontooptionen und Dauergrenze.
- [TikTok Content Sharing Guidelines](https://developers.tiktok.com/docs/en/content-sharing-guidelines), Stand 04.08.2026: zulässiger Nutzungskreis und Zustimmungs-/Auswahlanforderungen. [Music Usage Confirmation](https://www.tiktok.com/legal/page/global/music-usage-confirmation/en), [Branded Content Policy](https://www.tiktok.com/legal/page/global/bc-policy/en).
- [Pexels-Lizenz](https://www.pexels.com/license/): Herkunft wird nach Projektanforderung sichtbar übernommen; keine pauschale Behauptung, die allgemeine Lizenz verlange Namensnennung.
- Sicherheits-/OAuth-/Bibliotheksquellen und Grenzen aus [Prüfbericht 25](step25-acceptance.md#sicherheit-quellen-und-grenzen) bleiben einschlägig; keine neue Kryptografie oder TLS-Konfiguration.

## Sichere Übergabe / CTX-001

Gleicher lokaler Windows-Checkout `C:/Users/Public/Projekte/Video pipline/Video-generating-Pipeline v2`, Branch `codex/step10-in-progress`, Basis vor 26 **710ede6**. Code, Migration, Tests und Dokumentation werden gemeinsam committed/gepusht. Ignorierte Prüfhelfer/Medien/Secrets gehören nicht dazu. Abschließenden Commit und sauberen/synchronen Arbeitsstand über Git prüfen. Kein passender gespeicherter App-Projekteintrag für genau diesen Ordner; kein Wechsel zum ähnlich benannten anderen Checkout.

Aktueller Auftrag endet hier. Kein Auftrag für 27–31 ableiten und keinen leeren Folgechat erzeugen. Nächste notwendige Nachweise: Betreiberbedienung sowie unverändert fehlende Voraussetzungen 24–25 und TikTok-Nutzungskreis; echte Aktivierung erst danach. Erfolgreiche unveränderte Funktionen nicht nochmals prüfen. Private Konfigurationspfade und laufenden Medien-Worker auf dem jeweiligen Installationsrechner prüfen; temporäre Test-DSNs sind entfernt und werden nicht übertragen.
