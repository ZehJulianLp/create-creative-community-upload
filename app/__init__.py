import os
import secrets
from datetime import timedelta
from pathlib import Path

from flask import Flask, render_template
from werkzeug.exceptions import HTTPException

from . import db, security


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "app.sqlite3"),
        UPLOAD_FOLDER=str(Path(app.instance_path) / "uploads"),
        SECRET_KEY=os.environ.get("CCC_SECRET_KEY"),
        MAX_CONTENT_LENGTH=30 * 1024 * 1024,
        MAX_FORM_MEMORY_SIZE=256 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("CCC_COOKIE_SECURE") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    )

    if test_config is not None:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    if not app.config["SECRET_KEY"]:
        key_path = Path(app.instance_path) / "secret.key"
        try:
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "w") as key_file:
                key_file.write(secrets.token_hex(32))
        app.config["SECRET_KEY"] = key_path.read_text().strip()

    from .admin import admin
    from .auth import auth
    from .routes import main

    db.init_app(app)
    security.init_app(app)
    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(admin)

    @app.errorhandler(HTTPException)
    def http_error(error):
        messages = {
            400: "Die Anfrage konnte nicht verarbeitet werden. Lade die Seite neu und versuche es erneut.",
            403: "Du hast keine Berechtigung für diese Aktion.",
            404: "Diese Seite oder Kreation wurde nicht gefunden.",
            413: "Der Upload ist zu groß. Bild: maximal 8 MB, Schematic: maximal 20 MB.",
            429: "Zu viele Anmeldeversuche. Bitte versuche es in 15 Minuten erneut.",
        }
        return render_template("error.html", code=error.code,
                               message=messages.get(error.code, "Die Anfrage ist fehlgeschlagen.")), error.code

    return app
