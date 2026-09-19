from flask import abort, g

from .db import get_db

# Die Top 10 werden global berechnet, bevor Kategorie oder Besitzer filtern.
POSTS_QUERY = """
WITH scored AS (
    SELECT p.*, u.display_name, c.name AS category_name, c.slug AS category_slug,
           (SELECT COUNT(*) FROM likes WHERE post_id = p.id) AS like_count,
           EXISTS(SELECT 1 FROM likes WHERE post_id = p.id AND user_id = ?) AS liked
    FROM posts p JOIN users u ON u.id = p.owner_id
    JOIN categories c ON c.id = p.category_id
), top_ten AS (
    SELECT id FROM scored WHERE like_count > 0
    ORDER BY like_count DESC, created_at ASC, id ASC LIMIT 10
), enriched AS (
    SELECT scored.*, id IN (SELECT id FROM top_ten) AS is_top,
           (approved_at IS NOT NULL OR id IN (SELECT id FROM top_ten)) AS is_professional
    FROM scored
)
"""


def viewer_id():
    return g.user["id"] if g.get("user") else 0


def get_post(post_id):
    post = get_db().execute(POSTS_QUERY + "SELECT * FROM enriched WHERE id = ?",
                            (viewer_id(), post_id)).fetchone()
    if post is None:
        abort(404)
    return post


def list_posts(*, professional=False, category=None, owner=None, page=1):
    conditions, arguments = ["1 = 1"], [viewer_id()]
    if professional:
        conditions.append("is_professional = 1")
    if category:
        conditions.append("category_slug = ?")
        arguments.append(category)
    if owner is not None:
        conditions.append("owner_id = ?")
        arguments.append(owner)
    where = " WHERE " + " AND ".join(conditions)
    connection = get_db()
    total = connection.execute(POSTS_QUERY + "SELECT COUNT(*) FROM enriched" + where, arguments).fetchone()[0]
    ordering = "like_count DESC, created_at ASC, id ASC" if professional else "created_at DESC, id DESC"
    posts = connection.execute(
        POSTS_QUERY + "SELECT * FROM enriched" + where + " ORDER BY " + ordering + " LIMIT 12 OFFSET ?",
        (*arguments, (page - 1) * 12),
    ).fetchall()
    return posts, total


def categories():
    return get_db().execute("SELECT * FROM categories ORDER BY id").fetchall()
