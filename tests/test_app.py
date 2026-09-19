import gzip
import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash

from app import create_app
from app.db import get_db, init_db
from app.posts import get_post, list_posts


class CCCUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = "test-password-123"
        cls.password_hash = generate_password_hash(cls.password, method="pbkdf2:sha256:1000")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.app = create_app({
            "TESTING": True, "SECRET_KEY": "test-only-secret",
            "DATABASE": str(self.root / "test.sqlite3"),
            "UPLOAD_FOLDER": str(self.root / "uploads"),
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            init_db()
            with get_db() as connection:
                for name, role in (("Owner", "user"), ("Other", "user"), ("Mod", "moderator"), ("Admin", "admin")):
                    connection.execute(
                        "INSERT INTO users (email, display_name, password_hash, role) VALUES (?, ?, ?, ?)",
                        (name.lower() + "@example.com", name, self.password_hash, role),
                    )

    def login_as(self, user_id, client=None):
        client = client or self.client
        with client.session_transaction() as session:
            session.clear()
            session["user_id"] = user_id
            session["csrf_token"] = "test-csrf"

    def post(self, path, data=None, client=None, **kwargs):
        client = client or self.client
        with client.session_transaction() as session:
            token = session.setdefault("csrf_token", "test-csrf")
        return client.post(path, data={"csrf_token": token, **(data or {})}, **kwargs)

    def upload(self, **overrides):
        image = io.BytesIO()
        Image.new("RGB", (24, 16), "green").save(image, format="PNG")
        image.seek(0)
        data = {
            "title": "Grüner Regionalzug", "description": "Ein Regionalzug für Minecraft Create.",
            "category_id": "1", "image": (image, "train.png"),
            "schematic": (io.BytesIO(gzip.compress(b"\x0a\x00\x00\x00")), "train.nbt"),
        }
        data.update(overrides)
        return self.post("/hochladen", data, content_type="multipart/form-data")

    def seed_post(self, title="Testkreation", category_id=1, owner_id=1):
        with self.app.app_context():
            with get_db() as connection:
                result = connection.execute(
                    """INSERT INTO posts (owner_id, category_id, title, description,
                       image_filename, schematic_filename, original_filename)
                       VALUES (?, ?, ?, 'Eine Testbeschreibung', 'image.webp', 'file.nbt', 'original.nbt')""",
                    (owner_id, category_id, title),
                )
                return result.lastrowid

    def test_public_pages_and_assets(self):
        for path in ("/", "/professional", "/registrieren", "/anmelden"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"CCC Upload", response.data)
            self.assertIn("no-store", response.headers["Cache-Control"])
        for path in ("/static/css/style.css", "/static/css/theme.css", "/static/js/main.js"):
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/health").json, {"database": "ok", "status": "ok"})
        self.assertEqual(self.client.get("/?kategorie=unknown").status_code, 404)
        self.assertEqual(self.client.get("/unknown").status_code, 404)

    def test_registration_login_logout(self):
        data = {"email": " New@Example.com ", "display_name": "New Builder", "password": self.password,
                "password_confirm": self.password, "role": "admin"}
        self.assertEqual(self.post("/registrieren", data).status_code, 302)
        with self.app.app_context():
            user = get_db().execute("SELECT * FROM users WHERE email = 'new@example.com'").fetchone()
            self.assertEqual(user["role"], "user")
            self.assertNotEqual(user["password_hash"], self.password)
            self.assertTrue(check_password_hash(user["password_hash"], self.password))
        self.assertEqual(self.post("/registrieren", data).status_code, 400)
        response = self.post("/anmelden", {"email": "NEW@example.com", "password": self.password})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/hochladen").status_code, 200)
        self.assertEqual(self.post("/abmelden").status_code, 302)
        self.assertEqual(self.client.get("/hochladen").status_code, 302)

    def test_invalid_registration(self):
        base = {"email": "fresh@example.com", "display_name": "Fresh", "password": self.password, "password_confirm": self.password}
        for change in ({"email": "broken"}, {"display_name": "x"}, {"password": "short"}, {"password_confirm": "mismatch"}):
            self.assertEqual(self.post("/registrieren", {**base, **change}).status_code, 400)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0], 4)

    def test_csrf_and_guest_mutations(self):
        self.assertEqual(self.client.post("/registrieren", data={}).status_code, 400)
        with self.client.session_transaction() as session:
            session["csrf_token"] = "expected"
        self.assertEqual(self.client.post("/registrieren", data={"csrf_token": "ä"}).status_code, 400)
        post_id = self.seed_post()
        for suffix in ("like", "loeschen", "freigabe"):
            self.assertEqual(self.post(f"/kreationen/{post_id}/{suffix}").status_code, 302)
        self.assertEqual(self.client.get("/abmelden").status_code, 405)

    def test_upload_detail_download_and_cleanup(self):
        self.login_as(1)
        response = self.upload()
        self.assertEqual(response.status_code, 302)
        detail = self.client.get(response.location)
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Grüner Regionalzug".encode(), detail.data)
        self.assertNotIn(b"owner@example.com", detail.data)
        image = self.client.get(response.location + "/bild")
        self.assertEqual(image.mimetype, "image/webp")
        image.close()
        download = self.client.get(response.location + "/download")
        self.assertIn("attachment", download.headers["Content-Disposition"])
        self.assertIn("train.nbt", download.headers["Content-Disposition"])
        self.assertEqual(gzip.decompress(download.data), b"\x0a\x00\x00\x00")
        download.close()
        self.assertEqual(len(list((self.root / "uploads").iterdir())), 2)
        self.assertEqual(self.post(response.location + "/loeschen").status_code, 302)
        self.assertEqual(list((self.root / "uploads").iterdir()), [])
        self.assertEqual(self.client.get(response.location + "/download").status_code, 404)

    def test_invalid_uploads_leave_no_files_or_posts(self):
        self.login_as(1)
        bad_inputs = [
            {"image": (io.BytesIO(b"<script>oops</script>"), "fake.png")},
            {"schematic": (io.BytesIO(b"anything"), "file.exe")},
            {"schematic": (io.BytesIO(b"not NBT"), "file.nbt")},
            {"schematic": (io.BytesIO(b"\x1f\x8bgarbage"), "broken.nbt")},
            {"category_id": "999"}, {"title": "x"}, {"description": "short"},
            {"image": (io.BytesIO(b""), "")}, {"schematic": (io.BytesIO(b""), "")},
        ]
        for data in bad_inputs:
            with self.subTest(data=list(data)):
                self.assertEqual(self.upload(**data).status_code, 400)
        self.assertEqual(list((self.root / "uploads").iterdir()), [])
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM posts").fetchone()[0], 0)

    def test_upload_size_limits(self):
        self.login_as(1)
        self.assertEqual(self.upload(image=(io.BytesIO(b"x" * (8 * 1024 * 1024 + 1)), "large.png")).status_code, 400)
        self.app.config["MAX_CONTENT_LENGTH"] = 100
        self.assertEqual(self.upload().status_code, 413)

    def test_compressed_schematic_limits(self):
        self.login_as(1)
        with patch("app.uploads.NBT_LIMIT", 32):
            compressed = gzip.compress(b"\x0a\x00\x00" + b"x" * 100 + b"\x00")
            self.assertEqual(self.upload(schematic=(io.BytesIO(compressed), "large.nbt")).status_code, 400)
        broken = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03\xff\xff\xff\xff"
        self.assertEqual(self.upload(schematic=(io.BytesIO(broken), "corrupt.nbt")).status_code, 400)
        self.assertEqual(list((self.root / "uploads").iterdir()), [])

    def test_replacing_files_cleans_old_uploads(self):
        self.login_as(1)
        location = self.upload().location
        previous_files = set((self.root / "uploads").iterdir())
        image = io.BytesIO()
        Image.new("RGB", (30, 20), "blue").save(image, format="PNG")
        image.seek(0)
        response = self.post(location + "/bearbeiten", {
            "title": "Neues Vorschaubild", "description": "Überarbeitete Schematic mit neuem Bild.",
            "category_id": 1, "image": (image, "../../fake.html"),
            "schematic": (io.BytesIO(gzip.compress(b"\x0a\x00\x00\x00")), "../../new.nbt"),
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)
        current_files = set((self.root / "uploads").iterdir())
        self.assertEqual(len(current_files), 2)
        self.assertFalse(previous_files & current_files)
        with self.app.test_request_context():
            self.assertEqual(get_post(1)["original_filename"], "new.nbt")

    def test_database_failure_removes_new_upload_files(self):
        self.login_as(1)
        with self.app.app_context():
            with get_db() as connection:
                connection.execute("CREATE TRIGGER reject_post BEFORE INSERT ON posts BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        self.app.logger.disabled = True
        response = self.upload()
        self.app.logger.disabled = False
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list((self.root / "uploads").iterdir()), [])

    def test_ownership_moderation_and_user_management_permissions(self):
        post_id = self.seed_post()
        self.login_as(2)
        for suffix in ("bearbeiten", "loeschen", "freigabe"):
            self.assertEqual(self.post(f"/kreationen/{post_id}/{suffix}").status_code, 403)
        self.assertEqual(self.client.get("/verwaltung/beitraege").status_code, 403)
        self.login_as(3)
        self.assertEqual(self.client.get("/verwaltung/beitraege").status_code, 200)
        self.assertEqual(self.client.get(f"/kreationen/{post_id}/bearbeiten").status_code, 200)
        self.assertEqual(self.client.get("/verwaltung/user").status_code, 403)
        self.assertEqual(self.post("/verwaltung/user/2", {"action": "delete"}).status_code, 403)
        self.assertEqual(self.post(f"/kreationen/{post_id}/freigabe", {"action": "approve"}).status_code, 302)
        with self.app.test_request_context():
            self.assertTrue(get_post(post_id)["is_professional"])
        self.assertEqual(self.post(f"/kreationen/{post_id}/loeschen").status_code, 302)

    def test_like_is_unique_idempotent_and_reversible(self):
        post_id = self.seed_post()
        self.login_as(2)
        for _ in range(2):
            self.assertEqual(self.post(f"/kreationen/{post_id}/like", {"action": "like"}).status_code, 302)
        with self.app.test_request_context():
            post = get_post(post_id)
            self.assertEqual(post["like_count"], 1)
            self.assertTrue(post["is_top"])
        self.assertEqual(self.post(f"/kreationen/{post_id}/like", {"action": "dislike"}).status_code, 400)
        for _ in range(2):
            self.post(f"/kreationen/{post_id}/like", {"action": "unlike"})
        with self.app.test_request_context():
            self.assertEqual(get_post(post_id)["like_count"], 0)
            self.assertFalse(get_post(post_id)["is_professional"])

    def test_global_top_ten_ties_and_manual_approval(self):
        ids = [self.seed_post(title=f"Kreation {number}", category_id=2 if number == 10 else 1) for number in range(12)]
        with self.app.test_request_context():
            self.assertEqual(list_posts(professional=True)[1], 0)
            with get_db() as connection:
                connection.executemany("INSERT INTO likes (post_id, user_id) VALUES (?, 2)", [(post_id,) for post_id in ids[:11]])
            top, total = list_posts(professional=True)
            self.assertEqual(total, 10)
            self.assertEqual([post["id"] for post in top], ids[:10])
            self.assertEqual(list_posts(professional=True, category="haeuser")[1], 0)
            with get_db() as connection:
                connection.execute("INSERT INTO likes (post_id, user_id) VALUES (?, 3)", (ids[10],))
                connection.execute("UPDATE posts SET approved_at = CURRENT_TIMESTAMP, approved_by = 3 WHERE id = ?", (ids[11],))
            self.assertFalse(get_post(ids[9])["is_top"])
            self.assertTrue(get_post(ids[10])["is_top"])
            self.assertTrue(get_post(ids[11])["is_professional"])
            self.assertEqual(list_posts(professional=True)[1], 11)
            self.assertEqual(list_posts(professional=True, category="haeuser")[1], 1)

    def test_edit_preserves_files_and_resets_manual_approval(self):
        self.login_as(1)
        response = self.upload()
        location = response.location
        before = sorted((self.root / "uploads").iterdir())
        self.login_as(3)
        self.post(location + "/freigabe", {"action": "approve"})
        self.login_as(1)
        response = self.post(location + "/bearbeiten", {"title": "Neuer Name", "description": "Neue Beschreibung für den Zug.", "category_id": 2})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(before, sorted((self.root / "uploads").iterdir()))
        with self.app.test_request_context():
            post = get_post(1)
            self.assertEqual(post["title"], "Neuer Name")
            self.assertEqual(post["category_id"], 2)
            self.assertIsNone(post["approved_at"])
            self.assertEqual(post["owner_id"], 1)

    def test_revoking_manual_approval_preserves_top_ten_membership(self):
        post_id = self.seed_post()
        self.login_as(3)
        self.post(f"/kreationen/{post_id}/like", {"action": "like"})
        self.post(f"/kreationen/{post_id}/freigabe", {"action": "approve"})
        self.post(f"/kreationen/{post_id}/freigabe", {"action": "revoke"})
        with self.app.test_request_context():
            self.assertIsNone(get_post(post_id)["approved_at"])
            self.assertTrue(get_post(post_id)["is_professional"])

    def test_admin_roles_deactivation_and_existing_sessions(self):
        user_client = self.app.test_client()
        self.login_as(2, user_client)
        self.login_as(4)
        self.assertEqual(self.client.get("/verwaltung/user").status_code, 200)
        response = self.post("/verwaltung/user/2", {"action": "update", "role": "moderator", "is_active": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(user_client.get("/verwaltung/beitraege").status_code, 200)
        self.post("/verwaltung/user/2", {"action": "update", "role": "user"})
        self.assertEqual(user_client.get("/hochladen").status_code, 302)
        response = self.post("/anmelden", {"email": "other@example.com", "password": self.password}, client=user_client)
        self.assertEqual(response.status_code, 400)
        self.post("/verwaltung/user/2", {"action": "update", "role": "user", "is_active": "1"})
        response = self.post("/anmelden", {"email": "other@example.com", "password": self.password}, client=user_client)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(user_client.get("/verwaltung/beitraege").status_code, 403)

    def test_admin_self_protection_and_cascading_user_deletion(self):
        self.login_as(1)
        self.upload()
        self.login_as(4)
        self.post("/verwaltung/user/4", {"action": "delete"})
        self.post("/verwaltung/user/4", {"action": "update", "role": "user"})
        self.post("/verwaltung/user/1", {"action": "delete"})
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT role FROM users WHERE id = 4").fetchone()[0], "admin")
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM posts").fetchone()[0], 0)
            self.assertIsNone(get_db().execute("SELECT id FROM users WHERE id = 1").fetchone())
        self.assertEqual(list((self.root / "uploads").iterdir()), [])

    def test_login_throttle(self):
        for _ in range(10):
            self.assertEqual(self.post("/anmelden", {"email": "owner@example.com", "password": "wrong"}).status_code, 400)
        self.assertEqual(self.post("/anmelden", {"email": "owner@example.com", "password": self.password}).status_code, 429)

    def test_content_is_escaped(self):
        post_id = self.seed_post(title='<script>alert("x")</script>')
        detail = self.client.get(f"/kreationen/{post_id}").data
        self.assertNotIn(b'<script>alert("x")</script>', detail)
        self.assertIn(b"&lt;script&gt;", detail)

    def test_init_db_is_repeatable_and_admin_cli(self):
        post_id = self.seed_post()
        runner = self.app.test_cli_runner()
        self.assertEqual(runner.invoke(args=["init-db"]).exit_code, 0)
        with self.app.test_request_context():
            self.assertEqual(get_post(post_id)["title"], "Testkreation")
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM categories").fetchone()[0], 8)
        result = runner.invoke(args=["create-admin", "--email", "cli@example.com", "--name", "CLI Admin"],
                               input=self.password + "\n" + self.password + "\n")
        self.assertEqual(result.exit_code, 0, result.output)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT role FROM users WHERE email = 'cli@example.com'").fetchone()[0], "admin")

    def test_forms_render_with_csrf(self):
        self.login_as(1)
        self.upload()
        for path in ("/hochladen", "/meine-kreationen", "/kreationen/1", "/kreationen/1/bearbeiten"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            forms = re.findall(rb'<form\b.*?</form>', response.data, re.S)
            self.assertTrue(forms)
            self.assertTrue(all(b'name="csrf_token"' in form for form in forms))


if __name__ == "__main__":
    unittest.main()
