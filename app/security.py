import secrets
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for

from .db import get_db

ROLE_LABELS = {"user": "User", "moderator": "Moderator", "admin": "Admin"}


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Bitte melde dich zuerst an.", "info")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorate(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorate


def can_manage(post):
    return g.user is not None and (
        g.user["id"] == post["owner_id"] or g.user["role"] in ("admin", "moderator")
    )


def init_app(app):
    @app.before_request
    def load_user_and_check_csrf():
        g.user = None
        if session.get("user_id"):
            g.user = get_db().execute(
                "SELECT id, email, display_name, role FROM users WHERE id = ? AND is_active = 1",
                (session["user_id"],),
            ).fetchone()
            if g.user is None:
                session.clear()
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            expected = session.get("csrf_token", "")
            actual = request.form.get("csrf_token", "")
            if not expected or not secrets.compare_digest(expected.encode(), actual.encode()):
                abort(400)

    @app.context_processor
    def template_helpers():
        return dict(csrf_token=csrf_token, can_manage=can_manage, role_labels=ROLE_LABELS)

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' blob:; style-src 'self'; "
            "script-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store"
        return response
