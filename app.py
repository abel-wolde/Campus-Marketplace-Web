"""
Campus Marketplace — web rebuild
=================================
A peer-to-peer campus marketplace for Dakota State University students,
rebuilt as a web app from the original C# console app.

Stack choice: Flask (not FastAPI) because this is a small, server-rendered
app with a handful of endpoints. Flask's built-in dev server, Jinja
templates, and session handling keep the whole app explainable in one
read-through, with no async boilerplate. The REST API is plain Flask
routes returning JSON, so the same endpoints serve both the web UI
(via fetch) and any future client.

Storage: SQLite (stdlib sqlite3, one file, no server to run).
Auth: Werkzeug password hashing (scrypt) + Flask signed session cookies.
No passwords are ever stored in plain text.
"""

import os
import sqlite3
from functools import wraps

from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

CATEGORIES = ["Books", "Electronics", "Furniture", "Clothing", "Other"]
CONDITIONS = ["New", "Like new", "Good", "Fair"]


def create_app(database=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get(
        "MARKETPLACE_SECRET_KEY", "dev-secret-key-change-in-production"
    )
    app.config["DATABASE"] = database or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "marketplace.db"
    )

    # ------------------------------------------------------------------ db
    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(_exc=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def init_db():
        db = get_db()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
                category TEXT NOT NULL,
                condition TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_listings_category
                ON listings(category);
            CREATE INDEX IF NOT EXISTS idx_listings_title
                ON listings(title);
            """
        )
        db.commit()

    with app.app_context():
        init_db()

    app.init_db = init_db

    # -------------------------------------------------------------- helpers
    def current_user():
        user_id = session.get("user_id")
        if not user_id:
            return None
        return get_db().execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user():
                return jsonify({"error": "login required"}), 401
            return view(*args, **kwargs)

        return wrapped

    @staticmethod
    def listing_to_dict(row):
        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "price_cents": row["price_cents"],
            "price_dollars": row["price_cents"] / 100,
            "category": row["category"],
            "condition": row["condition"],
            "seller_id": row["user_id"],
            "seller_name": row["seller_name"],
            "created_at": row["created_at"],
        }

    # ----------------------------------------------------------- html pages
    @app.route("/")
    def index():
        return render_template("index.html", categories=CATEGORIES)

    @app.route("/login")
    def login_page():
        return render_template("login.html")

    @app.route("/register")
    def register_page():
        return render_template("register.html")

    @app.route("/new")
    def new_listing_page():
        if not current_user():
            return redirect(url_for("login_page"))
        return render_template("new_listing.html", categories=CATEGORIES,
                               conditions=CONDITIONS)

    # ------------------------------------------------------------- rest api
    @app.route("/api/me")
    def api_me():
        user = current_user()
        if not user:
            return jsonify({"user": None})
        return jsonify({"user": dict(user)})

    @app.route("/api/register", methods=["POST"])
    def api_register():
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        if not name or not email or "@" not in email:
            return jsonify({"error": "name and a valid email are required"}), 400
        if len(password) < 8:
            return jsonify({"error": "password must be at least 8 characters"}), 400
        db = get_db()
        existing = db.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            return jsonify({"error": "an account with that email already exists"}), 409
        cur = db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        db.commit()
        session["user_id"] = cur.lastrowid
        return jsonify({"id": cur.lastrowid, "name": name, "email": email}), 201

    @app.route("/api/login", methods=["POST"])
    def api_login():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        row = get_db().execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        if row is None or not check_password_hash(row["password_hash"], password):
            return jsonify({"error": "invalid email or password"}), 401
        session["user_id"] = row["id"]
        return jsonify({"id": row["id"], "name": row["name"], "email": row["email"]})

    @app.route("/api/logout", methods=["POST"])
    def api_logout():
        session.pop("user_id", None)
        return jsonify({"ok": True})

    @app.route("/api/listings", methods=["GET"])
    def api_list_listings():
        query = (request.args.get("q") or "").strip()
        category = request.args.get("category") or ""
        max_price = request.args.get("max_price") or ""
        sql = """
            SELECT l.*, u.name AS seller_name FROM listings l
            JOIN users u ON u.id = l.user_id
        """
        clauses, params = [], []
        if query:
            clauses.append("(l.title LIKE ? OR l.description LIKE ?)")
            params += [f"%{query}%", f"%{query}%"]
        if category in CATEGORIES:
            clauses.append("l.category = ?")
            params.append(category)
        if max_price:
            try:
                cents = int(round(float(max_price) * 100))
            except ValueError:
                return jsonify({"error": "max_price must be a number"}), 400
            clauses.append("l.price_cents <= ?")
            params.append(cents)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY l.created_at DESC, l.id DESC"
        rows = get_db().execute(sql, params).fetchall()
        return jsonify([listing_to_dict(r) for r in rows])

    @app.route("/api/listings", methods=["POST"])
    @login_required
    def api_create_listing():
        user = current_user()
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()
        category = data.get("category") or ""
        condition = data.get("condition") or ""
        try:
            price_cents = int(round(float(data.get("price", "")) * 100))
        except (TypeError, ValueError):
            return jsonify({"error": "price must be a number"}), 400
        if not title:
            return jsonify({"error": "title is required"}), 400
        if price_cents < 0:
            return jsonify({"error": "price cannot be negative"}), 400
        if category not in CATEGORIES:
            return jsonify({"error": f"category must be one of {CATEGORIES}"}), 400
        if condition not in CONDITIONS:
            return jsonify({"error": f"condition must be one of {CONDITIONS}"}), 400
        db = get_db()
        cur = db.execute(
            """INSERT INTO listings
               (user_id, title, description, price_cents, category, condition)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user["id"], title, description, price_cents, category, condition),
        )
        db.commit()
        row = db.execute(
            """SELECT l.*, u.name AS seller_name FROM listings l
               JOIN users u ON u.id = l.user_id WHERE l.id = ?""",
            (cur.lastrowid,),
        ).fetchone()
        return jsonify(listing_to_dict(row)), 201

    @app.route("/api/listings/<int:listing_id>", methods=["GET"])
    def api_get_listing(listing_id):
        row = get_db().execute(
            """SELECT l.*, u.name AS seller_name FROM listings l
               JOIN users u ON u.id = l.user_id WHERE l.id = ?""",
            (listing_id,),
        ).fetchone()
        if row is None:
            return jsonify({"error": "listing not found"}), 404
        return jsonify(listing_to_dict(row))

    @app.route("/api/listings/<int:listing_id>", methods=["DELETE"])
    @login_required
    def api_delete_listing(listing_id):
        user = current_user()
        db = get_db()
        row = db.execute(
            "SELECT user_id FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "listing not found"}), 404
        if row["user_id"] != user["id"]:
            return jsonify({"error": "only the seller can delete this listing"}), 403
        db.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
        db.commit()
        return jsonify({"ok": True})

    return app


app = create_app()

if __name__ == "__main__":
    # Development server only. For production use a WSGI server
    # (e.g. gunicorn) behind a reverse proxy, with a real secret key.
    app.run(host="127.0.0.1", port=5000, debug=True)
