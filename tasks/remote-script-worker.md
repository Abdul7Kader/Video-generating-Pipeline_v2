# Ubuntu-Worker für Schritt 10

Der Ubuntu-Rechner ist derzeit nur vorgesehene Hardware: Es gibt dort noch keinen eingerichteten Server, kein SSH und keinen nachgewiesenen Antigravity-Zugang. Für die erste Abnahme genügt eine direkte Anmeldung am Rechner mit Bildschirm und Browser. Die Anwendung bleibt über `127.0.0.1` auf **diesem** Rechner erreichbar; SSH und eine öffentliche Freigabe sind nicht erforderlich. Die Entwicklung geschieht weiter am GitHub-Repository.

## 1. Ubuntu, Datenbank und Redis vorbereiten

Nach dem Einschalten auf Ubuntu mit einem dauerhaft verwendeten Benutzer anmelden. Docker Engine mit Compose, Python 3.12 und `venv` installieren und das GitHub-Repository auschecken. Im Checkout ein starkes `POSTGRES_PASSWORD` über eine **nicht versionierte** `.env` bereitstellen. Die Zusatzdatei öffnet PostgreSQL und Redis nur auf `127.0.0.1` dieses Rechners und deaktiviert den Container-Worker im Standardprofil:

```sh
docker compose -f compose.yaml -f compose.remote-worker.yaml up -d --wait db redis
docker compose -f compose.yaml -f compose.remote-worker.yaml config --services
```

In der Serviceliste soll `worker` ohne Profil `container-worker` fehlen. Die Host-Ports sind standardmäßig `5433` (PostgreSQL) und `6380` (Redis); sie können über `HOST_POSTGRES_PORT` und `HOST_REDIS_PORT` in der lokalen `.env` geändert werden. Diese Ports nicht öffentlich freigeben.

## 2. Angemeldeten Host-Worker und Hintergrunddienst vorbereiten

Die [offizielle Antigravity-CLI](https://antigravity.google/docs/cli/install/) als derselbe Ubuntu-Benutzer installieren und **an diesem Rechner** mit dem gewünschten Google-AI-Pro-Konto im lokalen Browser anmelden. Google beschreibt dafür eine [lokale Anmeldung über den Linux-Keyring](https://antigravity.google/docs/cli/install/#local-silent-keyring-sign-in). Die CLI muss als `agy` im `PATH` desselben Benutzers liegen. Bei Keyring-Fehlern D-Bus und Secret Service prüfen; siehe [offizielle Fehlersuche](https://antigravity.google/docs/cli/troubleshooting/). Keine API-Key-Anmeldung verwenden.

In `~/.gemini/antigravity-cli/settings.json` ausdrücklich `"useG1Credits": false` setzen und `modelProvider` entfernen. Ohne diese Einstellung verweigert die Anwendung den Modellaufruf. Das gewählte Pro-Modell vor dem Live-Test mit `agy models` gegen die [offizielle CLI-Modellliste](https://antigravity.google/docs/cli/headless/) prüfen. Keine Tokens, Profilordner oder OAuth-Codes in dieses Repository oder in Chat-Nachrichten kopieren.

Im Checkout die Python-Umgebung vorbereiten:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
```

Der Host-Worker braucht `DATABASE_URL` mit Host `127.0.0.1` und Port `5433` sowie `REDIS_URL=redis://127.0.0.1:6380/0`. Diese Werte als `NAME=WERT`-Zeilen sicher außerhalb des Git-Checkouts in `~/.config/video-pipeline/worker.env` mit Dateirechten `0600` bereitstellen; das Datenbankpasswort muss dem Compose-Passwort entsprechen und in der URL kodiert sein. Bei geänderten Ports auch die URLs anpassen. Zunächst aus dem Verzeichnis `backend` als derselbe angemeldete Benutzer kontrolliert starten:

```sh
set -a
. "$HOME/.config/video-pipeline/worker.env"
set +a
../.venv/bin/rq worker --url "$REDIS_URL" --name pipeline-worker default
```

Danach die Vorlage [`deploy/video-script-worker.service`](../deploy/video-script-worker.service) nach `~/.config/systemd/user/video-script-worker.service` kopieren. Die Platzhalter `REPO_CHECKOUT` und `VENV_RQ` auf die absoluten Pfade des Ubuntu-Checkouts und der ausführbaren Datei `.venv/bin/rq` setzen. Der Dienst liest die geschützte `worker.env` und nimmt `~/.local/bin` für `agy` in den Suchpfad auf. Mit `systemctl --user daemon-reload` und `systemctl --user enable --now video-script-worker.service` starten; `systemctl --user status video-script-worker.service` und `journalctl --user -u video-script-worker.service -n 50 --no-pager` zeigen den Zustand. Der Dienst startet bei Benutzeranmeldung und nach Prozessfehlern erneut.

Ein unbeaufsichtigter Start nach einem Neustart **ohne** Benutzeranmeldung ist noch nicht belegt: Die CLI benötigt Zugriff auf die entsperrte Keyring-Sitzung. `loginctl enable-linger` allein bestätigt diesen Zugriff nicht. Das muss auf dem tatsächlichen Ubuntu-Rechner separat geprüft werden.

## 3. UI starten und Abnahme prüfen

Wenn der Host-Worker in Redis sichtbar ist, API und Web starten:

```sh
docker compose -f compose.yaml -f compose.remote-worker.yaml up -d --build --wait api web
```

Auf **Ubuntu** `http://127.0.0.1:4177/` im Browser öffnen. Idee und Modus speichern, ohne weitere Eingabe ein echtes Pro-Skript erhalten und Speicherung nach Neuladen prüfen. Fehlende Anmeldung, erschöpftes Kontingent und ungültige Antworten müssen als Fehler erscheinen; ein neuer Versuch erfordert einen bewussten Klick. Keine Gemini API und keine zusätzlichen AI-Credits aktivieren.

**Noch offen:** Ubuntu ist noch nicht eingerichtet oder live geprüft. Diese Anleitung ist Vorbereitung, kein behaupteter Live-Test. Der Skript- und Szeneneditor gehört zu Schritt 11; bis dahin zeigt die UI das gespeicherte Skript an, kann es aber noch nicht bearbeiten.
