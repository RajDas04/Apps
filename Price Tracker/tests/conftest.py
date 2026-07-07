"""Shared fixtures for the whole tests,
To handle some import-time/runtime hazards found in this codebase that would otherwise make tests unstable to run."""
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
def test_app_module(): # import main.py exactly once per test session, after sys.path is set up
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
def test_client(test_app_module, test_db_session, fake_redis, monkeypatch): # it is wired to test db, redis and no rate limiting
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
def test_make_user(test_db_session, test_app_module): # for test it creates a User row and returns it, using the real password hasher
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
def test_auth_cookies(test_app_module): # dict of cookies to attach to a client request using the app token creation logic
    import auth as auth_module
    def _cookies(user):
        access = auth_module.create_token(
            user.email, user.id, timedelta(minutes=auth_module.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        refresh = auth_module.create_refresh_token(user.email, user.id)
        return {"access_token": access, "refresh_token": refresh}
    return _cookies