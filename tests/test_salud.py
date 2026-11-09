import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_endpoint_salud(client):
    response = client.get("/salud")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"
    assert data["usuario"] == "operador_atuel"
    assert data["database"] == "bodegas_atuel"
