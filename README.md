# create-creative-community-upload
Schematic Upload for Create Livaries

Grundstruktur mit Flask, SQLite und einem Frontend aus HTML, CSS und JavaScript.

## Lokal starten

Voraussetzung: Python 3.9 oder neuer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m flask --app app init-db
python -m flask --app app run --debug
```

Anschließend http://127.0.0.1:5000 öffnen. Der Debug-Modus ist für die lokale
Entwicklung gedacht. Das Frontend wird direkt von Flask ausgeliefert und benötigt
keinen separaten Build-Schritt.

## Projektstruktur

```text
app/
├── __init__.py          # Flask-App und Konfiguration
├── db.py                # SQLite-Verbindungen und init-db-Befehl
├── routes.py            # Seiten und API-Routen
├── schema.sql           # Datenbankschema mit Beispiel-Tabelle items
├── templates/
│   └── index.html       # HTML-Startseite
└── static/
    ├── css/style.css    # Styles
    └── js/main.js       # Frontend-Logik mit API-Abfrage
instance/
└── .gitkeep             # app.sqlite3 wird lokal hier angelegt
.gitignore
requirements.txt
```

## Datenbank und API

- `python -m flask --app app init-db` legt die SQLite-Datei
  `instance/app.sqlite3` und fehlende Tabellen an. Bestehende Daten bleiben erhalten.
- Das Beispiel-Datenmodell liegt in `app/schema.sql`. Änderungen an vorhandenen
  Tabellen benötigen später eigene Migrationen; `init-db` ändert bestehende
  Tabellenspalten nicht.
- `GET /` liefert die Startseite.
- `GET /api/health` prüft die Datenbankverbindung und die Beispiel-Tabelle.
  Bei Erfolg antwortet die Route mit `{"status": "ok", "database": "ok"}`,
  bei einem Datenbankfehler mit HTTP 503.

Virtuelle Umgebungen, lokale Konfigurationen, Datenbanken und Cache-Dateien werden
durch `.gitignore` ausgeschlossen.

Weiterführend: [SQLite mit Flask](https://flask.palletsprojects.com/en/stable/tutorial/database/).
