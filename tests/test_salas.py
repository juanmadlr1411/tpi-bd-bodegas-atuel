import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_listar_salas(client):
    response = client.get("/salas")
    assert response.status_code == 200
    salas = response.json()
    assert isinstance(salas, list)
    assert len(salas) > 0
    assert {"id_sala", "calle", "numero", "dia_cierre", "localidad_nombre"} <= set(salas[0].keys())
