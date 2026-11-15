from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200

def test_login_success():
    response = client.post("/api/login", json={"passcode": "1111"})
    assert response.status_code == 200
    assert response.json()["role"] == "senior"

def test_login_invalid():
    response = client.post("/api/login", json={"passcode": "9999"})
    assert response.status_code == 401

def test_dashboard_data():
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "medications" in data
    assert "streak" in data