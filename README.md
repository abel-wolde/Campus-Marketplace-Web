# Campus Marketplace — Web Rebuild

A peer-to-peer campus marketplace for Dakota State University students,
rebuilt as a web app from the original C# console app
([Campus-Marketplace-Application2](https://github.com/abel-wolde/Campus-Marketplace-Application2)).

The console version had user registration, password hashing, item listings,
and search/filtering — all in a single file with no persistence. This rebuild
keeps those features and adds what the console app could not do: a real
database, a REST API, a web UI, and tests.

## Features

- **User accounts** — register and log in; passwords are hashed with
  Werkzeug's scrypt hashing and never stored in plain text.
- **Listings** — create a listing with title, description, price, category
  (Books, Electronics, Furniture, Clothing, Other), and condition.
- **Search & filter** — search by keyword in title/description, filter by
  category, and set a max price, alone or combined.
- **Ownership** — only the seller who posted a listing can delete it.
- **Persistent storage** — SQLite database (`marketplace.db`, created on
  first run).

## Tech stack

| Layer | Choice | Why |
| --- | --- | --- |
| Web framework | **Flask 3** | Small, server-rendered app; built-in dev server, Jinja templates, and session handling keep it explainable in one read-through, with no async boilerplate. |
| Database | **SQLite** (stdlib `sqlite3`) | One file, no server to run, foreign keys on, indexed on category/title. |
| Auth | Werkzeug password hashing + Flask signed session cookies | Standard, no extra dependencies. |
| Frontend | HTML + CSS + vanilla JS (`fetch`) | No build step; the same REST API serves the UI and any future client. |
| Tests | **pytest** | 6 test functions covering auth, listings, search, validation, and ownership. |

## Project structure

```
campus-marketplace-web/
├── app.py                 # Flask app: DB schema, auth, HTML pages, REST API
├── requirements.txt       # Flask + pytest
├── static/
│   ├── style.css          # Clean, responsive styling
│   └── app.js             # Header sign-in state
├── templates/
│   ├── base.html          # Shared layout
│   ├── index.html         # Browse + search/filter UI
│   ├── login.html
│   ├── register.html
│   └── new_listing.html   # Post a listing (login required)
└── tests/
    └── test_api.py        # API tests (temporary SQLite DB per test)
```

## How to run

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the tests
python -m pytest -q

# 4. Start the server
python app.py
# or: flask --app app run

# 5. Open http://127.0.0.1:5000
```

Register an account, then post a listing from **Sell an item**. The database
file `marketplace.db` is created automatically on first run and is git-ignored
— the repo ships with no listings and no users.

Set a real secret key in production:

```bash
MARKETPLACE_SECRET_KEY=<a-long-random-value> python app.py
```

## REST API

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| POST | `/api/register` | — | `{name, email, password}` (min. 8 chars) → 201 |
| POST | `/api/login` | — | `{email, password}` → 200, sets session |
| POST | `/api/logout` | — | Clears the session |
| GET | `/api/me` | — | Current user, or `{"user": null}` |
| GET | `/api/listings?q=&category=&max_price=` | — | List, search, and filter listings |
| POST | `/api/listings` | Yes | Create a listing → 201 |
| GET | `/api/listings/<id>` | — | One listing, or 404 |
| DELETE | `/api/listings/<id>` | Yes, owner only | Delete a listing |

Prices are accepted in dollars (`"price": 25.00`) and stored as integer
cents (`price_cents`) to avoid floating-point rounding.

## Usage notes

1. Register at `/register`, then log in — the header shows who is signed in.
2. Browse at `/` — try searching "textbook", filtering by category, or
   setting a max price.
3. Post a listing at **Sell an item** (login required); it appears on the
   home page immediately.
4. Listings can only be deleted by their seller (via the API for now —
   the delete button in the UI is a planned addition).

## What this rebuild adds over the console version

- Persistent SQLite storage instead of in-memory lists that vanish on exit
- A REST API with JSON responses and proper HTTP status codes (400/401/403/404/409)
- Password hashing with a real library instead of the console app's approach
- A web UI anyone can use without a terminal
- Automated tests covering registration, login, search/filter, validation,
  and delete permissions

## Limitations / honest notes

- This is a student project, not production software: the Flask dev server
  is for local use only; production needs a WSGI server (e.g. gunicorn)
  behind a reverse proxy, a real `SECRET_KEY`, and HTTPS.
- No email verification, password reset, image uploads, or messaging
  between buyers and sellers yet — those are the next features.
- No fake users or listings are seeded; the database starts empty.

## Author

Abel Wolde — Computer Science, Dakota State University (expected May 2029).
GitHub: https://github.com/abel-wolde
