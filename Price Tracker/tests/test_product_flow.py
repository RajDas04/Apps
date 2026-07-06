"""Tests for product flow, required authentication and authorization, and ownership."""
import pytest

def test_add_product_with_auth(test_client):
    resp = test_client.post("/products", json={"name": "Widget", "data_id": "abc123"})
    assert resp.status_code == 401

def test_add_product_success(test_client, test_make_user, test_auth_cookies):
    user = test_make_user()
    cookies = test_auth_cookies(user)
    resp = test_client.post("/products",json={"name": "Widget", "data_id": "abc123"},
                            cookies=cookies,)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Widget"
    assert body["search_q"] == "Widget"  # crud.create_product always sets search_q = name

def test_get_products(test_client, test_make_user, test_auth_cookies): # requires auth, returns only the user's products.
    owner = test_make_user(email="owner@example.com")
    other = test_make_user(email="other@example.com")
    test_client.post("/products", json={"name": "Owner Widget", "data_id": "a1"}, cookies=test_auth_cookies(owner))
    test_client.post("/products", json={"name": "Other Widget", "data_id": "a2"}, cookies=test_auth_cookies(other))
    resp = test_client.get("/products", cookies=test_auth_cookies(owner))
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert names == ["Owner Widget"]

def test_get_products(test_client, test_make_user, test_auth_cookies): # for new user, returns empty list.
    user = test_make_user()
    resp = test_client.get("/products", cookies=test_auth_cookies(user))
    assert resp.status_code == 200
    assert resp.json() == []

def test_delete_products(test_client, test_make_user, test_auth_cookies): # for user, deletes their own product and returns successful.
    user = test_make_user()
    cookies = test_auth_cookies(user)
    created = test_client.post(
        "/products", json={"name": "Widget", "data_id": "abc"}, cookies=cookies
    ).json()
    resp = test_client.delete(f"/products/{created['id']}", cookies=cookies)
    assert resp.status_code == 204
    remaining = test_client.get("/products", cookies=cookies).json()
    assert remaining == []

def test_delete_product_another_user_returns_404(test_client, test_make_user, test_auth_cookies): # it should filter and return 404, not 403, and the product should remain in the DB.
    owner = test_make_user(email="owner@example.com")
    attacker = test_make_user(email="badguy@example.com")
    created = test_client.post(
        "/products", json={"name": "Owner", "data_id": "a1"}, cookies=test_auth_cookies(owner)
    ).json()
    resp = test_client.delete(f"/products/{created['id']}", cookies=test_auth_cookies(attacker))
    assert resp.status_code == 404
    still_there = test_client.get("/products", cookies=test_auth_cookies(owner)).json()
    assert len(still_there) == 1

def test_delete_nonexistent_product_returns_404(test_client, test_make_user, test_auth_cookies): # it should return 404 for a product ID that doesn't exist, even the auth user.
    user = test_make_user()
    resp = test_client.delete("/products/999999", cookies=test_auth_cookies(user))
    assert resp.status_code == 404

def test_delete_product_requires_auth(test_client):
    resp = test_client.delete("/products/1")
    assert resp.status_code == 401

def test_add_product_also_creates_auto_alert(test_client, test_make_user, test_auth_cookies, test_db_session): # it create alert with product, can only be verified by querying the DB directly.
    from db_models import Alert
    user = test_make_user()
    created = test_client.post(
        "/products", json={"name": "Widget", "data_id": "abc123"}, cookies=test_auth_cookies(user)
    ).json()
    alert = test_db_session.query(Alert).filter(Alert.product_id == created["id"]).first()
    assert alert is not None
    assert alert.user_id == user.id
    assert alert.threshold == 0
    assert alert.is_active is True

def test_delete_product_success(test_client, test_make_user, test_auth_cookies): # it includes hx-redirect header
    user = test_make_user()
    cookies = test_auth_cookies(user)
    created = test_client.post(
        "/products", json={"name": "Widget", "data_id": "abc"}, cookies=cookies
    ).json()
    resp = test_client.delete(f"/products/{created['id']}", cookies=cookies)
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect") == "/dashboard?deleted=1"

def test_delete_product_404(test_client, test_make_user, test_auth_cookies): # it doesn't include hx-redirect header, on 404 it should not leak through from the response object that was mutated before.
    user = test_make_user()
    resp = test_client.delete("/products/999999", cookies=test_auth_cookies(user))
    assert resp.status_code == 404
    assert "HX-Redirect" not in resp.headers

def test_add_product_missing_data_id(test_client, test_make_user, test_auth_cookies): # it should return 422.
    user = test_make_user()
    resp = test_client.post("/products", json={"name": "Widget"}, cookies=test_auth_cookies(user))
    assert resp.status_code == 422


def test_add_product_missing_name(test_client, test_make_user, test_auth_cookies): # it should return 422.
    user = test_make_user()
    resp = test_client.post("/products", json={"data_id": "abc123"}, cookies=test_auth_cookies(user))
    assert resp.status_code == 422


def test_add_duplicate_product(test_client, test_make_user, test_auth_cookies):
    user = test_make_user()
    cookies = test_auth_cookies(user)
    payload = {"name": "Widget", "data_id": "same-id"}
    first = test_client.post("/products", json=payload, cookies=cookies)
    second = test_client.post("/products", json=payload, cookies=cookies)
    assert first.status_code == 200
    assert second.status_code == 200
    all_products = test_client.get("/products", cookies=cookies).json()
    assert len(all_products) == 2
    # its a design choice that the app allows duplicate products for the same user, the test is here to document current behavior, not desired behavior.