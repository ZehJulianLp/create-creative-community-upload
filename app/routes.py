import sqlite3

from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect,
                   render_template, request, send_from_directory, url_for)

from .db import get_db
from .posts import categories, get_post, list_posts
from .security import can_manage, login_required, roles_required
from .uploads import read_image, read_schematic, remove_uploads, write_uploads

main = Blueprint("main", __name__)


@main.get("/")
def index():
    return gallery("community")


@main.get("/professional")
def professional():
    return gallery("professional")


@main.get("/meine-kreationen")
@login_required
def mine():
    return gallery("mine")


def gallery(area):
    category = request.args.get("kategorie", "")
    page = max(1, request.args.get("seite", 1, type=int))
    category_list = categories()
    if category and category not in {item["slug"] for item in category_list}:
        abort(404)
    posts, total = list_posts(professional=area == "professional", category=category,
                             owner=g.user["id"] if area == "mine" else None, page=page)
    return render_template("index.html", area=area, posts=posts, total=total,
                           categories=category_list, category=category, page=page,
                           pages=max(1, (total + 11) // 12))


@main.get("/kreationen/<int:post_id>")
def detail(post_id):
    return render_template("detail.html", post=get_post(post_id))


@main.get("/kreationen/<int:post_id>/bild")
def post_image(post_id):
    post = get_post(post_id)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], post["image_filename"], mimetype="image/webp")


@main.get("/kreationen/<int:post_id>/download")
def download(post_id):
    post = get_post(post_id)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], post["schematic_filename"],
                               as_attachment=True, download_name=post["original_filename"],
                               mimetype="application/octet-stream")


@main.route("/hochladen", methods=("GET", "POST"))
@login_required
def create():
    return edit_form()


@main.route("/kreationen/<int:post_id>/bearbeiten", methods=("GET", "POST"))
@login_required
def edit(post_id):
    post = get_post(post_id)
    if not can_manage(post):
        abort(403)
    return edit_form(post)


def edit_form(post=None):
    error = None
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id", type=int)
        files = []
        try:
            if not 3 <= len(title) <= 100:
                raise ValueError("Der Name muss zwischen 3 und 100 Zeichen lang sein.")
            if not 10 <= len(description) <= 10000:
                raise ValueError("Die Beschreibung muss zwischen 10 und 10.000 Zeichen lang sein.")
            if not get_db().execute("SELECT id FROM categories WHERE id = ?", (category_id,)).fetchone():
                raise ValueError("Bitte wähle eine gültige Kategorie.")
            image = request.files.get("image")
            schematic = request.files.get("schematic")
            image_name = post["image_filename"] if post else None
            schematic_name = post["schematic_filename"] if post else None
            original_name = post["original_filename"] if post else None
            if image and image.filename:
                image_name, image_data = read_image(image)
                files.append((image_name, image_data))
            elif not post:
                raise ValueError("Bitte füge ein Bild deiner Kreation hinzu.")
            if schematic and schematic.filename:
                schematic_name, schematic_data, original_name = read_schematic(schematic)
                files.append((schematic_name, schematic_data))
            elif not post:
                raise ValueError("Bitte füge deine Schematic hinzu.")
            write_uploads(files)
            try:
                with get_db() as connection:
                    values = (title, description, category_id, image_name, schematic_name, original_name)
                    if post:
                        connection.execute(
                            """UPDATE posts SET title = ?, description = ?, category_id = ?, image_filename = ?,
                               schematic_filename = ?, original_filename = ?, updated_at = CURRENT_TIMESTAMP,
                               approved_at = NULL, approved_by = NULL WHERE id = ?""", (*values, post["id"]),
                        )
                        post_id = post["id"]
                    else:
                        cursor = connection.execute(
                            """INSERT INTO posts (title, description, category_id, image_filename,
                               schematic_filename, original_filename, owner_id) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (*values, g.user["id"]),
                        )
                        post_id = cursor.lastrowid
            except Exception:
                remove_uploads([name for name, _ in files])
                raise
            if post:
                remove_uploads([post[key] for key, new in (("image_filename", image_name),
                                ("schematic_filename", schematic_name)) if post[key] != new])
            flash("Kreation gespeichert." if post else "Deine Kreation ist jetzt in der Community!", "success")
            if post and post["approved_at"]:
                flash("Nach der Bearbeitung ist eine erneute manuelle Professional-Freigabe nötig. Die Top-10-Auswahl bleibt unabhängig davon aktiv.", "info")
            return redirect(url_for("main.detail", post_id=post_id))
        except ValueError as exception:
            error = str(exception)
        except (OSError, sqlite3.Error):
            current_app.logger.exception("Kreation konnte nicht gespeichert werden")
            error = "Speichern ist gerade nicht möglich. Bitte versuche es erneut."
    return render_template("post_form.html", post=post, categories=categories(), error=error), 400 if error else 200


@main.post("/kreationen/<int:post_id>/loeschen")
@login_required
def delete(post_id):
    post = get_post(post_id)
    if not can_manage(post):
        abort(403)
    with get_db() as connection:
        connection.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    remove_uploads([post["image_filename"], post["schematic_filename"]])
    flash("Kreation gelöscht.", "success")
    return redirect(url_for("main.mine" if g.user["id"] == post["owner_id"] else "admin.posts"))


@main.post("/kreationen/<int:post_id>/like")
@login_required
def like(post_id):
    get_post(post_id)
    action = request.form.get("action")
    if action not in ("like", "unlike"):
        abort(400)
    with get_db() as connection:
        if action == "like":
            connection.execute("INSERT OR IGNORE INTO likes (post_id, user_id) VALUES (?, ?)", (post_id, g.user["id"]))
        else:
            connection.execute("DELETE FROM likes WHERE post_id = ? AND user_id = ?", (post_id, g.user["id"]))
    return redirect(url_for("main.detail", post_id=post_id))


@main.post("/kreationen/<int:post_id>/freigabe")
@roles_required("moderator", "admin")
def approve(post_id):
    get_post(post_id)
    action = request.form.get("action")
    if action not in ("approve", "revoke"):
        abort(400)
    with get_db() as connection:
        if action == "approve":
            connection.execute("UPDATE posts SET approved_at = CURRENT_TIMESTAMP, approved_by = ? WHERE id = ?", (g.user["id"], post_id))
        else:
            connection.execute("UPDATE posts SET approved_at = NULL, approved_by = NULL WHERE id = ?", (post_id,))
    flash("Professional-Freigabe erteilt." if action == "approve" else "Manuelle Freigabe aufgehoben. Die Top-10-Auswahl bleibt unabhängig davon aktiv.", "success")
    return redirect(url_for("main.detail", post_id=post_id))


@main.get("/api/health")
def health():
    try:
        get_db().execute("SELECT p.id FROM posts p JOIN users u ON u.id = p.owner_id JOIN categories c ON c.id = p.category_id LEFT JOIN likes l ON l.post_id = p.id LIMIT 1").fetchone()
    except sqlite3.Error:
        current_app.logger.exception("SQLite-Statusprüfung fehlgeschlagen")
        return jsonify(status="error", database="unavailable"), 503

    return jsonify(status="ok", database="ok")
