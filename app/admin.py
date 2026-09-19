from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .db import get_db
from .posts import list_posts
from .security import ROLE_LABELS, roles_required
from .uploads import remove_uploads

admin = Blueprint("admin", __name__, url_prefix="/verwaltung")


@admin.get("/beitraege")
@roles_required("moderator", "admin")
def posts():
    page = max(1, request.args.get("seite", 1, type=int))
    items, total = list_posts(page=page)
    return render_template("manage_posts.html", posts=items, total=total,
                           page=page, pages=max(1, (total + 11) // 12))


@admin.get("/user")
@roles_required("admin")
def users():
    page = max(1, request.args.get("seite", 1, type=int))
    total = get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0]
    items = get_db().execute(
        "SELECT id, display_name, email, role, is_active, created_at FROM users ORDER BY id DESC LIMIT 25 OFFSET ?",
        ((page - 1) * 25,),
    ).fetchall()
    return render_template("manage_users.html", users=items, total=total,
                           page=page, pages=max(1, (total + 24) // 25))


@admin.post("/user/<int:user_id>")
@roles_required("admin")
def update_user(user_id):
    connection = get_db()
    # Serialisiert Änderungen, damit nicht zwei Admins gleichzeitig den letzten entfernen.
    connection.execute("BEGIN IMMEDIATE")
    files = []
    with connection:
        target = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if target is None:
            abort(404)
        if user_id == g.user["id"]:
            flash("Dein eigenes Admin-Konto kannst du hier nicht ändern oder löschen.", "error")
            return redirect(url_for("admin.users"))
        action = request.form.get("action")
        if action not in ("update", "delete"):
            abort(400)
        role = request.form.get("role")
        active = int(request.form.get("is_active") == "1")
        if action == "update" and role not in ROLE_LABELS:
            abort(400)
        loses_admin = action == "delete" or role != "admin" or not active
        if target["role"] == "admin" and target["is_active"] and loses_admin:
            count = connection.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1").fetchone()[0]
            if count <= 1:
                flash("Mindestens ein aktives Admin-Konto muss erhalten bleiben.", "error")
                return redirect(url_for("admin.users"))
        if action == "delete":
            owned_posts = connection.execute("SELECT image_filename, schematic_filename FROM posts WHERE owner_id = ?", (user_id,)).fetchall()
            files = [name for post in owned_posts for name in post]
            connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        else:
            connection.execute("UPDATE users SET role = ?, is_active = ? WHERE id = ?", (role, active, user_id))
    remove_uploads(files)
    flash("Konto und zugehörige Beiträge gelöscht." if action == "delete" else "Konto aktualisiert.", "success")
    return redirect(url_for("admin.users"))
