import re
import sqlite3

import click
from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from flask.cli import with_appcontext
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

auth = Blueprint("auth", __name__)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
DUMMY_HASH = generate_password_hash("not-a-real-account-password")


def validate_account(email, name, password):
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        return "Bitte gib eine gültige E-Mail-Adresse ein."
    if not 2 <= len(name) <= 40:
        return "Dein Anzeigename muss zwischen 2 und 40 Zeichen lang sein."
    if not 10 <= len(password) <= 128:
        return "Dein Passwort muss zwischen 10 und 128 Zeichen lang sein."
    return None


@auth.route("/registrieren", methods=("GET", "POST"))
def register():
    if g.user:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        error = validate_account(email, name, password)
        if not error and password != request.form.get("password_confirm"):
            error = "Die Passwörter stimmen nicht überein."
        if not error:
            try:
                with get_db() as connection:
                    connection.execute(
                        "INSERT INTO users (email, display_name, password_hash) VALUES (?, ?, ?)",
                        (email, name, generate_password_hash(password)),
                    )
            except sqlite3.IntegrityError:
                error = "Diese E-Mail-Adresse ist bereits registriert."
            else:
                flash("Dein Konto ist bereit. Du kannst dich direkt anmelden.", "success")
                return redirect(url_for("auth.login"))
        return render_template("auth.html", registering=True, error=error), 400
    return render_template("auth.html", registering=True)


@auth.route("/anmelden", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()[:254]
        password = request.form.get("password", "")
        address = request.remote_addr or "unknown"
        connection = get_db()
        with connection:
            connection.execute("DELETE FROM login_attempts WHERE created_at < datetime('now', '-15 minutes')")
        attempts = connection.execute(
            "SELECT SUM(email = ?) AS account, SUM(address = ?) AS address FROM login_attempts",
            (email, address),
        ).fetchone()
        if (attempts["account"] or 0) >= 10 or (attempts["address"] or 0) >= 30:
            abort(429)
        user = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        valid = len(password) <= 128 and check_password_hash(
            user["password_hash"] if user else DUMMY_HASH, password
        )
        if user is None or not valid or not user["is_active"]:
            with connection:
                connection.execute("INSERT INTO login_attempts (email, address) VALUES (?, ?)", (email, address))
            return render_template("auth.html", registering=False,
                                   error="Anmeldung nicht möglich. Prüfe deine Zugangsdaten und ob dein Konto aktiv ist."), 400
        with connection:
            connection.execute("DELETE FROM login_attempts WHERE email = ?", (email,))
        session.clear()
        session["user_id"] = user["id"]
        session.permanent = True
        flash("Willkommen zurück, " + user["display_name"] + "!", "success")
        return redirect(url_for("main.index"))
    return render_template("auth.html", registering=False)


@auth.post("/abmelden")
def logout():
    session.clear()
    flash("Du bist abgemeldet.", "info")
    return redirect(url_for("main.index"))


@click.command("create-admin")
@click.option("--email", prompt="E-Mail")
@click.option("--name", prompt="Anzeigename")
@click.password_option(confirmation_prompt=True)
@with_appcontext
def create_admin(email, name, password):
    """Ein neues Admin-Konto anlegen (kein Standardpasswort)."""
    email, name = email.strip().lower(), name.strip()
    error = validate_account(email, name, password)
    if error:
        raise click.ClickException(error)
    try:
        with get_db() as connection:
            connection.execute(
                "INSERT INTO users (email, display_name, password_hash, role) VALUES (?, ?, ?, 'admin')",
                (email, name, generate_password_hash(password)),
            )
    except sqlite3.IntegrityError as error:
        raise click.ClickException("Die E-Mail-Adresse wird bereits verwendet.") from error
    click.echo("Admin-Konto für CCC Upload angelegt.")
