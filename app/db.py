import sqlite3

import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    """Eine SQLite-Verbindung pro Anwendungskontext bereitstellen."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


def close_db(error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    with current_app.open_resource("schema.sql", mode="r") as schema:
        get_db().executescript(schema.read())


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Fehlende Tabellen anlegen; vorhandene Daten bleiben erhalten."""
    init_db()
    click.echo("SQLite-Datenbank initialisiert.")


def init_app(app):
    from .auth import create_admin

    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(create_admin)
