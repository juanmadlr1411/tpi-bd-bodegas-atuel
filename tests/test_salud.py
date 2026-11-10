import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.config import settings


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_endpoint_salud(client):
    response = client.get("/salud")
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"

    # La API debe informar el usuario y base de datos configurados
    assert data["usuario"] == settings.DB_USER
    assert data["database"] == settings.DB_NAME
