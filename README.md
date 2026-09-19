# CCC Upload

Eine Community-App für **Minecraft Create Schematics** mit Flask, SQLite und
HTML/CSS/JavaScript. Beiträge enthalten Name, Bild, Beschreibung, Kategorie,
Schematic-Datei und Like-Anzahl.

## Lokal starten

Voraussetzung: **Python 3.10 oder neuer**.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m flask --app app init-db
python -m flask --app app create-admin
python -m flask --app app run --debug
```

Die App ist anschließend unter http://127.0.0.1:5000 erreichbar.
`create-admin` fragt E-Mail, Anzeigename und Passwort interaktiv ab. Es gibt keine
Standardzugangsdaten. Zum Ausprobieren der Community reicht auch ein über die
Oberfläche registriertes User-Konto. Der Debug-Modus dient der lokalen Entwicklung.

**Beim Update der bisherigen Grundstruktur:** `init-db` erneut ausführen. Der
Befehl ergänzt die neuen Tabellen und Kategorien, ohne bestehende Daten zu löschen.
Die alte Beispiel-Tabelle `items` wird nicht mehr verwendet und bleibt unverändert.
Zukünftige Änderungen an bestehenden Tabellenspalten brauchen eigene Migrationen.

## Funktionen und Rechte

| Aktion | Gast | User | Moderator | Admin |
| --- | --- | --- | --- | --- |
| Kreationen ansehen, nach Kategorie filtern und herunterladen | Ja | Ja | Ja | Ja |
| Kreationen hochladen | – | Ja | Ja | Ja |
| Beiträge bearbeiten und löschen | – | Eigene | Alle | Alle |
| Likes vergeben und eigene Likes zurücknehmen | – | Ja | Ja | Ja |
| Manuelle Professional-Freigabe erteilen oder aufheben | – | – | Ja | Ja |
| Konten sperren, aktivieren, löschen und Rollen vergeben | – | – | – | Ja |

- Anmeldung mit **E-Mail und Passwort**; der Anzeigename ist öffentlich, die
  E-Mail-Adresse nur in der Userverwaltung sichtbar.
- Neue Registrierungen erhalten immer die Rolle `user`. Es wird **keine E-Mail
  verschickt**, und eine E-Mail-Bestätigung ist aktuell nicht erforderlich.
- Die Community zeigt alle veröffentlichten Beiträge. Unter **Meine Kreationen**
  verwalten angemeldete Personen ihre eigenen Beiträge.
- Es gibt pro Konto und Beitrag höchstens einen Like. Er kann zurückgenommen
  werden. Es gibt keine Dislikes.
- Kategorien: **Züge, Häuser, Dekoobjekte, Maschinen & Fabriken, Farmen,
  Brücken & Infrastruktur, Fahrzeuge und Sonstiges**.
- Das Löschen eines Beitrags entfernt seine Dateien und Likes. Das Löschen eines
  Kontos entfernt auch dessen Beiträge, Dateien und Likes.
- Gesperrte Konten können sich nicht anmelden. Bestehende Sitzungen werden beim
  nächsten Zugriff ungültig. Beiträge und Likes bleiben beim Sperren erhalten.
- Das eigene Admin-Konto kann in der Userverwaltung nicht geändert oder gelöscht
  werden. Mindestens ein aktives Admin-Konto bleibt erhalten.

## Community und Professional

Der Professional-Bereich ist eine zusätzliche Auswahl aus der Community. Ein
Beitrag erscheint dort, wenn **mindestens eine** dieser Bedingungen zutrifft:

1. Ein Moderator oder Admin hat ihn manuell freigegeben.
2. Er gehört zu den **globalen Top 10 nach Likes** und hat mindestens einen Like.

Bei gleich vielen Likes zählt zuerst der ältere Beitrag, danach die kleinere ID.
Die Top 10 werden vor Kategorie- und Besitzerfiltern bestimmt. Die Auswahl passt
sich an, sobald Likes vergeben, zurückgenommen oder gelöscht werden. Beiträge
fallen ohne manuelle Freigabe wieder heraus, wenn sie nicht mehr zu den Top 10
gehören. Freigegebene Beiträge können zusätzlich zu den Top 10 erscheinen.

Jede Bearbeitung setzt eine vorhandene **manuelle** Freigabe zurück, damit die
geänderte Fassung erneut geprüft werden kann. Die Auswahl über Likes bleibt davon
unabhängig. Ebenso kann das Aufheben der manuellen Freigabe einen aktuellen
Top-10-Beitrag nicht aus Professional entfernen.

## Dateien und Speicherung

- SQLite: `instance/app.sqlite3`
- Uploads: `instance/uploads/`, außerhalb des öffentlichen Static-Verzeichnisses
- Vorschaubilder: PNG, JPEG oder WebP, maximal **8 MiB / 20 Megapixel**. Bilder werden
  geprüft, auf höchstens 2560 × 2560 Pixel verkleinert und ohne Metadaten als WebP
  neu gespeichert.
- Schematics: **`.nbt`**, maximal **20 MiB**; maximal **64 MiB** entpackt.
  Dateiendung, Kompression und grundlegender NBT-Compound-Dateikopf werden geprüft.
  Eine vollständige NBT-Struktur- oder Minecraft-Kompatibilitätsprüfung findet
  nicht statt. Benötigte Mods und Versionen gehören in die Beschreibung.
- Dateien erhalten zufällige interne Namen. Downloads werden als Dateianhang
  ausgeliefert. Fehlgeschlagene Speichervorgänge räumen neue Dateien auf.

Create speichert Schematics im `.nbt`-Format:
[Create-Dokumentation](https://github.com/Creators-of-Create/Create/wiki/Saving-a-Schematic).

## Konfiguration

Ohne zusätzliche Konfiguration erzeugt CCC Upload einen dauerhaften zufälligen
Session-Schlüssel unter `instance/secret.key`. Alternativ lässt er sich über die
Umgebungsvariable `CCC_SECRET_KEY` setzen. Bei einem Betrieb über HTTPS aktiviert
`CCC_COOKIE_SECURE=1` das Secure-Attribut der Session-Cookies. Die App lädt keine
`.env`-Dateien automatisch.

Passwörter werden mit Werkzeug gehasht. Schreibende Formulare sind durch
CSRF-Tokens geschützt, Rollen und Eigentümerschaft werden auf dem Server geprüft.
Nach 10 fehlgeschlagenen Loginversuchen je E-Mail bzw. 30 je IP innerhalb von
15 Minuten greift eine vorübergehende Anmeldesperre. Ein Reverse Proxy muss bei
Bedarf gesondert für vertrauenswürdige Client-IP-Weitergabe konfiguriert werden.

Datenbank, Uploads, Session-Schlüssel, lokale Umgebungen und Cache-Dateien sind in
`.gitignore` ausgeschlossen. Für ein Backup gehören Datenbank und Uploads zusammen.

## Projektstruktur

```text
app/
├── __init__.py          # App-Factory und Konfiguration
├── auth.py              # Registrierung, Login und create-admin
├── security.py          # Rollen, Sitzungen, CSRF und Sicherheitsheader
├── admin.py             # User- und Beitragsverwaltung
├── routes.py            # Galerie, Beiträge, Uploads, Likes und Freigaben
├── posts.py             # Beitragsabfragen und globale Top-10-Auswahl
├── uploads.py           # Datei-Prüfung, Speicherung und Bereinigung
├── db.py                # SQLite-Verbindungen und init-db
├── schema.sql           # Tabellen, Kategorien und Indizes
├── templates/           # HTML-Seiten
└── static/
    ├── css/             # Theme und responsives Layout
    └── js/main.js       # Bildvorschau und Löschbestätigung
instance/                # Lokale Daten, nicht in Git
tests/test_app.py         # Funktions- und Berechtigungstests
```

## Tests

```bash
python -m unittest discover -s tests -v
node --check app/static/js/main.js  # optionaler Syntaxcheck, benötigt Node.js
```

Die Tests verwenden temporäre Datenbanken und Upload-Verzeichnisse. Sie prüfen
Anmeldung, Rollenrechte, CSRF, Upload-Validierung, Downloads, Datei-Bereinigung,
Likes, Top-10-Grenzen, Freigaben, Kontensperren und die Admin-Einrichtung.
`GET /api/health` liefert den Datenbankstatus als JSON.
