import sqlite3

from flask import Blueprint, current_app, jsonify, render_template

from .db import get_db

main = Blueprint("main", __name__)


@main.get("/")
def index():
    return render_template("index.html")


@main.get("/api/health")
def health():
    try:
        # Prüft die Verbindung und ob das Schema initialisiert wurde.
        get_db().execute("SELECT id FROM items LIMIT 1").fetchone()
    except sqlite3.Error:
        current_app.logger.exception("SQLite-Statusprüfung fehlgeschlagen")
        return jsonify(status="error", database="unavailable"), 503

    return jsonify(status="ok", database="ok")
