"""Tests for the OTP-based registration flow and the cookie-based login/refresh flow, it doesn't include tests for the JWT-based login/refresh flow,
which is tested in test_auth.py, email delivery and rate limiting."""
import json, pytest

#region OTP flow
def test_otp_request(test_client, fake_redis): # it send otp for new user registration and stores in redis
    resp = test_client.post("/auth/signin/request",
                       json={"email": "new_user@example.com", "password": "blahblahblah"},)
    assert resp.status_code == 202
    stored_raw = fake_redis.get("new_user@example.com")
    assert stored_raw is not None
    stored = json.loads(stored_raw)
    assert stored["email"] == "new_user@example.com"
    assert len(stored["otp"]) == 6

def test_otp_request_existing_user(test_client, test_make_user): # it shouldn't send otp for already registered user and returns 400
    test_make_user(email="taken@example.com")
    resp = test_client.post("/auth/signin/request",
                            json={"email": "taken@example.com", "password": "blahblahblah"},)
    assert resp.status_code == 400

def test_otp_request_rejects_duplicate(test_client): # it should reject a second request for same email before the first otp is consumed or expired and returns 400
    payload = {"email": "pending@example.com", "password": "blahblahblah"}
    first = test_client.post("/auth/signin/request", json=payload)
    assert first.status_code == 202
    second = test_client.post("/auth/signin/request", json=payload)
    assert second.status_code == 400

def test_signin_verify(test_client, fake_redis, test_db_session): # it should verify the otp and create a user and consume the otp so it can't be re-used
    test_client.post("/auth/signin/request", json={"email": "user@example.com", "password": "blahblahblah"})
    otp = json.loads(fake_redis.get("user@example.com"))["otp"]
    resp = test_client.post("/auth/signin/verify", json={"email": "user@example.com", "otp": otp})
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "user@example.com"
    assert "id" in body
    assert fake_redis.get("user@example.com") is None # otp should be consumed and reusing it should fail

def test_signin_verify_rejects(test_client): # it should reject an invalid otp and return 400
    test_client.post("/auth/signin/request", json={"email": "not_otp@example.com", "password": "blahblahblah"})
    resp = test_client.post("/auth/signin/verify", json={"email": "not_otp@example.com", "otp": "000000"})
    assert resp.status_code == 400

def test_signin_verify_rejects_no_otp(test_client): # it should reject if there's no otp in redis or requested
    resp = test_client.post("/auth/signin/verify", json={"email": "ghost@example.com", "otp": "123456"})
    assert resp.status_code == 400

#region Cookie-based login/refresh flow
def test_login_cookie(test_client, test_make_user): # it should login and return access_token and refresh_token in cookies
    test_make_user(email="user@example.com", password="blahblahblah")
    resp = test_client.post("/auth/login/cookie",
                            data={"username": "user@example.com", "password": "blahblahblah"},)
    assert resp.status_code == 200
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies
    body = resp.json()
    assert body["token_type"] == "bearer"

def test_login_cookie_wrong_password(test_client, test_make_user): # it should reject wrong password and return 401
    test_make_user(email="user@example.com", password="blahblahblah")
    resp = test_client.post("/auth/login/cookie",
                            data={"username": "user@example.com", "password": "notblahblahblah"},)
    assert resp.status_code == 401

def test_login_cookie_unknown_email(test_client): # it should reject unknown email and return 401
    resp = test_client.post("/auth/login/cookie",
                            data={"username": "not_user@example.com", "password": "blahblahblah"},)
    assert resp.status_code == 401

def test_refresh_cookie(test_client, test_make_user, test_auth_cookies): # it should refresh the access_token and refresh_token in cookies
    user = test_make_user()
    cookies = test_auth_cookies(user)
    resp = test_client.post("/auth/refresh/cookie", cookies={"refresh_token": cookies["refresh_token"]})
    assert resp.status_code == 200
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies

def test_refresh_cookie_no_token(test_client): # it should return 401 if no refresh_token cookie is provided
    resp = test_client.post("/auth/refresh/cookie")
    assert resp.status_code == 401

def test_refresh_cookie_rejects_access_token(test_client, test_make_user, test_auth_cookies): # it should reject if the access_token cookie is provided instead of the refresh_token cookie and return 401
    user = test_make_user()
    cookies = test_auth_cookies(user)
    resp = test_client.post("/auth/refresh/cookie", cookies={"refresh_token": cookies["access_token"]})
    assert resp.status_code == 401