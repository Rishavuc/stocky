import os, sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["COOKIE_SECURE"] = "false"
os.environ["EYE_DISABLE_NETWORK"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import pytest
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine, event
from app import store

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
store.engine = engine
store.DB.configure(bind=engine)
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(autouse=True)
def schema():
    store.Base.metadata.drop_all(engine)
    store.Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app, headers={"X-Eye-Client": "workspace"}) as c:
        yield c


@pytest.fixture
def alice(client):
    r = client.post(
        "/v1/auth/register",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "correct-horse-123",
        },
    )
    assert r.status_code == 200, r.text
    return client
