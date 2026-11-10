import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_reporte_top_vinos(client):
    response = client.get("/reportes/top-vinos?limit=5")
    assert response.status_code == 200
    datos = response.json()
    assert isinstance(datos, list)
    assert len(datos) <= 5
    if len(datos) > 0:
        item = datos[0]
        assert "cod_vino" in item
        assert "nombre" in item
        assert "total_botellas" in item
        assert item["total_botellas"] >= 0
        # Verificar orden descendente
        if len(datos) > 1:
            assert datos[0]["total_botellas"] >= datos[1]["total_botellas"]


def test_reporte_ventas_por_sala(client):
    response = client.get("/reportes/ventas-por-sala")
    assert response.status_code == 200
    datos = response.json()
    assert isinstance(datos, list)
    assert len(datos) > 0
    item = datos[0]
    assert {"id_sala", "calle", "numero", "cod_postal", "localidad", "monto_total_trimestre"} <= set(item.keys())
    # Verificar orden descendente por facturación
    if len(datos) > 1:
        assert datos[0]["monto_total_trimestre"] >= datos[1]["monto_total_trimestre"]


def test_reporte_vinos_sin_stock(client):
    response = client.get("/reportes/vinos-sin-stock?id_sala=1")
    assert response.status_code == 200
    datos = response.json()
    assert isinstance(datos, list)
    for item in datos:
        assert {"cod_vino", "nombre", "stock_deposito"} <= set(item.keys())
        assert item["stock_deposito"] > 0


def test_reporte_transportista_activo(client):
    response = client.get("/reportes/transportista-activo")
    assert response.status_code == 200
    datos = response.json()
    assert "cod_transporte" in datos
    assert "razon_social" in datos
    assert "cantidad_traslados" in datos
    assert datos["cantidad_traslados"] >= 0


def test_reporte_trazabilidad_vino(client):
    response = client.get("/reportes/trazabilidad/1")
    assert response.status_code == 200
    datos = response.json()
    assert datos["cod_vino"] == 1
    assert "vino" in datos
    assert "bodega" in datos
    assert "composicion" in datos
    assert "maridajes" in datos
    assert "stock_total" in datos
    assert datos["stock_total"] >= 0


def test_reporte_trazabilidad_vino_inexistente(client):
    response = client.get("/reportes/trazabilidad/999999")
    assert response.status_code == 404
