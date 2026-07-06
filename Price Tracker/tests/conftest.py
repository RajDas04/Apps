"""
Shared fixtures for the whole test suite.

Handles four import-time/runtime hazards found in this codebase that would
otherwise make tests flaky, slow, or dangerous to run:

1. `database.py` builds a real SQLAlchemy engine from settings.database_url
   at import time, and `main.py` calls Base.metadata.create_all(bind=engine)
   at import time too. Left alone, importing main for TestClient would
   create tables in whatever DB your .env points at. We override get_db
   with a throwaway in-memory SQLite engine before any test touches the DB.

2. `auth.py` builds `redis_cli = redis.from_url(...)` at import time and
   uses it synchronously inside request handlers (OTP register/verify).
   Without a real Redis running, these calls raise redis.exceptions.
   ConnectionError. We monkeypatch auth.redis_cli with an in-memory fake.

3. Two endpoints (/auth/signin/request at 3/min, /auth/refresh/cookie at
   10/min) are rate-limited via slowapi. Confirmed directly from the
   installed slowapi source: Limiter checks `self.enabled` at request time
   (slowapi/extension.py), so setting app.state.limiter.enabled = False
   disables limiting for the whole test session without touching route code.

4. main.py imports scraper.py, tasks.py, and notify.py at module level.
   Those files weren't part of what was reviewed, and even if they exist
   in the real repo, tests must never trigger real scraping, real Celery
   dispatch, or real emails. This conftest doesn't stub them — that's done
   at the environment level (see README note in the test package) — but
   if you run this suite and imports fail here, that's almost certainly why.

Run with your working directory set to the project root (so relative
"templates"/"static" paths in main.py resolve), and with a .env file (or
exported env vars) satisfying every field in config.Settings — pydantic
raises at import time otherwise, before pytest even collects tests.
"""

from datetime import timedelta
import pytest, sys, os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_DB_URL = "sqlite:///:memory:"
# test database: in-memory SQLite engine, in StaticPool otherwise it'll not work fastapi's one-session-per-request
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

class FakeRedis:
    def __init__(self):
        self._store = {}
    def setex(self, key, ttl, value):
        self._store[key] = value
    def get(self, key):
        return self._store.get(key)
    def delete(self, key):
        self._store.pop(key, None)

#region App & db fixtures
@pytest.fixture(scope="session")
def test_app_module(): # import main.py exactly once per test session, after sys.path is set up.
    sys.path.insert(0, os.getcwd())
    import main as main_module
    return main_module

@pytest.fixture()
def test_db_session(test_app_module): # fresh schema for every test, create yield and drop
    import db_models
    db_models.Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        db_models.Base.metadata.drop_all(bind=test_engine)

@pytest.fixture()
def fake_redis():
    return FakeRedis()

@pytest.fixture()
def test_client(test_app_module, test_db_session, fake_redis, monkeypatch): # it is wired to test db, redis and no rate limiting.
    import database
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass  # db_session fixture owns closing this
    test_app_module.app.dependency_overrides[database.get_db] = override_get_db
    import auth
    monkeypatch.setattr(auth, "redis_cli", fake_redis)
    test_app_module.limiter.enabled = False

    with TestClient(test_app_module.app) as c:
        yield c
    test_app_module.app.dependency_overrides.clear()

#region User & auth
@pytest.fixture()
def test_make_user(test_db_session, test_app_module): # for test it creates a User row and returns it, using the real password hasher.
    import auth as auth_module
    from db_models import User
    created = []

    def _make(email="user@example.com", password="correct-password"):
        user = User(email=email, h_pass=auth_module.hasher.hash(password))
        test_db_session.add(user)
        test_db_session.commit()
        test_db_session.refresh(user)
        created.append(user)
        return user
    return _make

@pytest.fixture()
def test_auth_cookies(test_app_module): # dict of cookies to attach to a client request using the app token creation logic.
    import auth as auth_module
    def _cookies(user):
        access = auth_module.create_token(
            user.email, user.id, timedelta(minutes=auth_module.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        refresh = auth_module.create_refresh_token(user.email, user.id)
        return {"access_token": access, "refresh_token": refresh}
    return _cookies