"""API tests for Campus Marketplace. Run: python -m pytest -q"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "test.db"
    test_app = create_app(database=str(db_path))
    test_app.config["TESTING"] = True
    with test_app.test_client() as test_client:
        yield test_client


def register(client, name="Abel", email="abel@example.com", password="password123"):
    return client.post(
        "/api/register",
        json={"name": name, "email": email, "password": password},
    )


def test_register_and_login_hashes_password(client, tmp_path):
    res = register(client)
    assert res.status_code == 201
    assert res.get_json()["email"] == "abel@example.com"

    # The stored hash must not be (or contain) the plain password.
    import sqlite3

    db = sqlite3.connect(str(tmp_path / "test.db"))
    stored = db.execute("SELECT password_hash FROM users").fetchone()[0]
    assert stored != "password123"
    assert "password123" not in stored

    # Duplicate email is rejected.
    assert register(client).status_code == 409
    # Short passwords are rejected.
    assert register(client, email="other@example.com", password="short").status_code == 400

    # Login works, wrong password does not.
    assert client.post("/api/login", json={"email": "abel@example.com", "password": "password123"}).status_code == 200
    assert client.post("/api/login", json={"email": "abel@example.com", "password": "wrongpass"}).status_code == 401


def test_create_and_search_listings(client):
    register(client)
    listing = {
        "title": "Data Structures textbook",
        "description": "Used one semester, good condition",
        "price": 25.00,
        "category": "Books",
        "condition": "Good",
    }
    res = client.post("/api/listings", json=listing)
    assert res.status_code == 201
    created = res.get_json()
    assert created["title"] == listing["title"]
    assert created["price_cents"] == 2500
    assert created["seller_name"] == "Abel"

    # A second listing in another category.
    client.post("/api/listings", json={
        "title": "Mini fridge", "description": "", "price": 60,
        "category": "Furniture", "condition": "Like new",
    })

    all_items = client.get("/api/listings").get_json()
    assert len(all_items) == 2

    # Keyword search.
    assert len(client.get("/api/listings?q=textbook").get_json()) == 1
    assert client.get("/api/listings?q=textbook").get_json()[0]["title"] == "Data Structures textbook"
    # Category filter.
    assert len(client.get("/api/listings?category=Furniture").get_json()) == 1
    # Max-price filter.
    assert len(client.get("/api/listings?max_price=30").get_json()) == 1
    # Combined search + filter.
    assert len(client.get("/api/listings?q=fridge&category=Furniture").get_json()) == 1
    assert len(client.get("/api/listings?q=fridge&category=Books").get_json()) == 0

    # Single listing lookup, and 404 for a missing one.
    assert client.get(f"/api/listings/{created['id']}").status_code == 200
    assert client.get("/api/listings/9999").status_code == 404


def test_create_listing_requires_login(client):
    res = client.post("/api/listings", json={
        "title": "Laptop", "description": "", "price": 100,
        "category": "Electronics", "condition": "Good",
    })
    assert res.status_code == 401


def test_listing_validation(client):
    register(client)
    base = {"title": "Chair", "description": "", "price": 10,
            "category": "Furniture", "condition": "Good"}
    assert client.post("/api/listings", json={**base, "title": ""}).status_code == 400
    assert client.post("/api/listings", json={**base, "price": -5}).status_code == 400
    assert client.post("/api/listings", json={**base, "price": "free"}).status_code == 400
    assert client.post("/api/listings", json={**base, "category": "Cars"}).status_code == 400
    assert client.post("/api/listings", json={**base, "condition": "Mint"}).status_code == 400


def test_only_seller_can_delete(client):
    register(client)
    res = client.post("/api/listings", json={
        "title": "Lamp", "description": "", "price": 5,
        "category": "Furniture", "condition": "Good",
    })
    listing_id = res.get_json()["id"]

    # A different user cannot delete it.
    client.post("/api/logout")
    register(client, name="Sam", email="sam@example.com")
    assert client.delete(f"/api/listings/{listing_id}").status_code == 403

    # The seller can.
    client.post("/api/logout")
    client.post("/api/login", json={"email": "abel@example.com", "password": "password123"})
    assert client.delete(f"/api/listings/{listing_id}").status_code == 200
    assert client.get(f"/api/listings/{listing_id}").status_code == 404


def test_html_pages_render(client):
    for path in ["/", "/login", "/register"]:
        assert client.get(path).status_code == 200
    # /new redirects to login when signed out.
    assert client.get("/new").status_code == 302
