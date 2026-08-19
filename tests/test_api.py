import pytest
from unittest.mock import patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from database.models import Base
from database.connection import get_db
from database.crud import save_rate_if_changed

# Database test in-memory dengan StaticPool agar data persist selama lifecycle test
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "online"
    assert "endpoints" in json_data


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "ok"
    assert json_data["database"] == "connected"


def test_latest_endpoint_not_found_when_empty():
    with patch("scraper.bs4_scraper.BS4Scraper.fetch_data", side_effect=Exception("Scraper offline")):
        response = client.get("/latest")
        assert response.status_code == 404
        assert "Belum ada data kurs" in response.json()["detail"]


def test_latest_endpoint_success_with_data():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    save_rate_if_changed(db, "USD/IDR", 15750.25, 0.12, now)
    db.close()

    response = client.get("/latest")
    assert response.status_code == 200
    json_data = response.json()

    assert json_data["pair"] == "USD/IDR"
    assert json_data["price"] == 15750.25
    assert json_data["change_percent"] == 0.12
    assert "timestamp" in json_data


def test_history_endpoint_pagination():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    for i in range(5):
        save_rate_if_changed(db, "USD/IDR", 15700.0 + i * 10, 0.1 * i, now)
    db.close()

    response = client.get("/history?limit=2&offset=0")
    assert response.status_code == 200
    json_data = response.json()

    assert json_data["pair"] == "USD/IDR"
    assert json_data["total"] == 5
    assert json_data["limit"] == 2
    assert json_data["offset"] == 0
    assert len(json_data["data"]) == 2
    assert json_data["data"][0]["price"] == 15740.0


def test_pantau_treasury_endpoint():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    save_rate_if_changed(db, "USD/IDR", 17804.50, -0.15, now)
    db.close()

    response = client.get("/api/pantau-treasury")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["price"] == 17804.50
    assert data["price_formatted"] == "17804.5000"
    assert len(data["history"]) >= 1
    assert data["history"][0]["value"] == 17804.50


def test_open_er_api_mock_endpoint():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    save_rate_if_changed(db, "USD/IDR", 17800.00, 0.05, now)
    db.close()

    response = client.get("/v6/latest/USD")
    assert response.status_code == 200
    data = response.json()
    assert data["result"] == "success"
    assert data["rates"]["IDR"] == 17800.00


def test_websocket_connection():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    save_rate_if_changed(db, "USD/IDR", 17804.00, -0.10, now)
    db.close()

    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "INITIAL_DATA"
        assert data["price"] == 17804.00
        assert len(data["history"]) >= 1

        websocket.send_text("ping")
        assert websocket.receive_text() == "pong"


def test_cors_headers():
    response = client.options(
        "/latest",
        headers={
            "Origin": "https://mywebsite.com",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in ["*", "https://mywebsite.com"]
