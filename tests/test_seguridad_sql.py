import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_inyeccion_sql_filtro_bodega_es_tratada_como_literal(client):
    """
    Paso 9 de Etapa 6: Demostración de inyección SQL fallida.
    Al enviar un payload malicioso como `' OR '1'='1`, la capa DAL parametrizada
    (%s) trata el contenido como texto literal y no altera la semántica del WHERE.
    """
    payload_malicioso = "' OR '1'='1"
    response = client.get(f"/vinos?bodega={payload_malicioso}")

    assert response.status_code == 200
    datos = response.json()
    # No debe retornar todos los vinos del catálogo (que son más de 40),
    # sino únicamente los que coincidan literalmente con la cadena (es decir, 0).
    assert datos["total"] == 0
    assert len(datos["items"]) == 0


def test_inyeccion_sql_filtro_cepa_es_tratada_como_literal(client):
    """
    Inyección maliciosa tipo UNION SELECT en el filtro de cepa.
    Debe tratarse como búsqueda textual dentro del subquery EXISTS.
    """
    payload_malicioso = "Malbec' UNION SELECT 1, 'hack', 'hack', 2026, 750, 14, 1000, '30111111118'--"
    response = client.get(f"/vinos?cepa={payload_malicioso}")

    assert response.status_code == 200
    datos = response.json()
    assert datos["total"] == 0
    assert len(datos["items"]) == 0


def test_inyeccion_sql_stacking_queries_falla_por_tipo(client):
    """
    Intento de apilar comandos (ej. inyectar un DELETE o DROP).
    """
    payload_malicioso = "tinto'; DELETE FROM vino;--"
    response = client.get(f"/vinos?tipo={payload_malicioso}")

    # FastAPI / Pydantic valida el enum o el DAL busca el literal.
    # Si pasa a Pydantic, devuelve 422 por no pertenecer al enum TipoVinoEnum.
    assert response.status_code == 422
