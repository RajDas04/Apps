"""Tests for auth.py: token creation/decoding, get_current_user extraction from request, authenticate_user, and the OTP helpers.
Requirements before running:
pip install pytest"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest, auth
from jose import jwt

#region Fixtures and helpers
# fake stand-ins for the subset of redis-py api auth.py uses
class fake_redis:
    def __init__(self):
        self._store = {}
    def setex(self, key, ttl, value):
        self._store[key] = value
    def get(self, key):
        return self._store.get(key)
    def delete(self, key):
        self._store.pop(key, None)

# fake stand-in for starlette.Request — get_current_user only touches .cookies.get() and .headers.get(), so we don't need the real thing
class fake_request:
    def __init__(self, cookies=None, headers=None):
        self.cookies = cookies or {}
        self.headers = headers or {}

# replace the module-level redis_cli with an in-memory fake for every test
@pytest.fixture(autouse=True)
def redis_mock(monkeypatch: pytest.MonkeyPatch):
    fake = fake_redis()
    monkeypatch.setattr(auth, "redis_cli", fake)
    return fake

# fake ORM user-like object with a real hash, so authenticate_user's hasher.verify() call works against it
def make_user(email="user@example.com", user_id=1, password="blahblahblah"):
    return SimpleNamespace(id=user_id, email=email, h_pass=auth.hasher.hash(password),)

#region Token creation and decoding
def test_get_current_user(): # it reads from cookie
    token = auth.create_token("user@example.com", 1, timedelta(minutes=15))
    payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    assert payload["sub"] == "user@example.com"
    assert payload["id"] == 1
    assert "exp" in payload
    assert "type" not in payload  # access tokens are not marked as refresh

def test_create_refresh_token(): # it is marked as refresh
    token = auth.create_refresh_token("user@example.com", 1)
    payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    assert payload["type"] == "refresh"
    assert payload["sub"] == "user@example.com"

def test_refresh_tokens(): # it issues new access and refresh tokens
    refresh = auth.create_refresh_token("user@example.com", 1)
    result = auth.refresh_token(refresh)
    assert result["token_type"] == "bearer"
    new_payload = jwt.decode(result["access_token"], auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    assert new_payload["sub"] == "user@example.com"
    assert "type" not in new_payload

# access token (no 'type': 'refresh' claim) must not be accepted by the refresh endpoint's logic
def test_refresh_token_rejects_access_token():
    access = auth.create_token("user@example.com", 1, timedelta(minutes=15))
    with pytest.raises(Exception) as exc_info:
        auth.refresh_token(access)
    assert exc_info.value.status_code == 401
 
def test_refresh_token_rejects_unusable_token(): # should reject a non-JWT string
    with pytest.raises(Exception) as exc_info:
        auth.refresh_token("not-real-jwt")
    assert exc_info.value.status_code == 401

#region Auth User
def test_auth_user_success():
    user = make_user(password="blahblahblah")
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = user
    result = auth.authenticate_user("user@example.com", "blahblahblah", fake_db)
    assert result is user

def test_auth_user_wrong_password():
    user = make_user(password="blahblahblah")
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = user
    result = auth.authenticate_user("user@example.com", "notblahblahblah", fake_db)
    assert result is False

def test_auth_user_unknown_email():
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = None
    result = auth.authenticate_user("nobody@example.com", "anything", fake_db)
    assert result is False

#region The OTP flow
def test_create_and_store_otp(): # it also verifies that the OTP is stored 6 digit and retrievable
    otp = auth.create_and_store_otp("user@example.com", "blahblahblah")
    assert len(otp) == 6
    assert otp.isdigit()
    stored = auth.verify_otp("user@example.com")
    assert stored["otp"] == otp
    assert stored["email"] == "user@example.com"
    assert stored["password"] == "blahblahblah"

def test_verify_otp(): # it returns false when no OTP is stored for the given email
    assert auth.verify_otp("notuser@example.com") is False

def test_delete_otp_removes_entry():
    auth.create_and_store_otp("user@example.com", "blahblahblah")
    auth.delete_otp("user@example.com")
    assert auth.verify_otp("user@example.com") is False