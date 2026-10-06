import os

import pytest
from careeros.db import Base, build_engine, get_db
from careeros.main import app
from careeros.seed import seed
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path}/test.db"
    engine = build_engine(url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def user(db):
    return seed(db, "mohit@example.com", "Test-password-12345")[0]


@pytest.fixture
def logged(client, user):
    r = client.post("/auth/login", json={"email": user.email, "password": "Test-password-12345"})
    assert r.status_code == 200, r.text
    client.headers["x-csrf-token"] = r.json()["csrf_token"]
    return client
