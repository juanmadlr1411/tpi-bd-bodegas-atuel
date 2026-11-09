import pytest
import uuid
from fastapi.testclient import TestClient

from api.main import app
from api.database import get_db_cursor


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_listar_clientes_paginado(client):
    response = client.get("/clientes?limit=5&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert data["limit"] == 5
    assert len(data["items"]) <= 5
    assert data["total"] > 0


def test_crear_cliente_socio_descuento_10(client):
    unique_dni = f"S{uuid.uuid4().hex[:8]}"
    payload = {
        "nombre_razon_social": "Socio Club Exclusivo",
        "tipo_documento": "DNI",
        "nro_documento": unique_dni,
        "direccion": "Av. Mitre 540",
        "cod_postal": "5500",
        "tipo_cliente": "socio",
    }
    response = client.post("/clientes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id_cliente"] > 0
    assert data["tipo_cliente"] == "socio"
    # RN-06: Socio tiene 10% de descuento asignado por trigger
    assert float(data["porcentaje_descuento"]) == 10.00


def test_crear_cliente_distribuidor_descuento_20(client):
    unique_cuit = f"30{uuid.uuid4().hex[:8]}9"[:11]
    unique_hab = f"HAB-{uuid.uuid4().hex[:6]}"
    payload = {
        "nombre_razon_social": "Distribuidora Los Andes SRL",
        "tipo_documento": "CUIT",
        "nro_documento": unique_cuit,
        "direccion": "Ruta 40 Km 120",
        "cod_postal": "5501",
        "tipo_cliente": "distribuidor",
        "zona_cobertura": "Cuyo y Centro",
        "nro_habilitacion": unique_hab,
    }
    response = client.post("/clientes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["tipo_cliente"] == "distribuidor"
    # RN-06: Distribuidor tiene 20% de descuento
    assert float(data["porcentaje_descuento"]) == 20.00
    assert data["zona_cobertura"] == "Cuyo y Centro"
    assert data["nro_habilitacion"] == unique_hab


def test_crear_cliente_exportador_descuento_30(client):
    unique_cuit = f"30{uuid.uuid4().hex[:8]}8"[:11]
    payload = {
        "nombre_razon_social": "Export Vinos Global SA",
        "tipo_documento": "CUIT",
        "nro_documento": unique_cuit,
        "direccion": "Puerto Madero 100",
        "cod_postal": "5500",
        "tipo_cliente": "exportador",
        "pais_destino": "Estados Unidos",
    }
    response = client.post("/clientes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["tipo_cliente"] == "exportador"
    # RN-06: Exportador tiene 30% de descuento
    assert float(data["porcentaje_descuento"]) == 30.00
    assert data["pais_destino"] == "Estados Unidos"


def test_actualizar_cliente(client):
    # Crear cliente para editar
    unique_doc = f"D{uuid.uuid4().hex[:8]}"
    payload = {
        "nombre_razon_social": "Cliente Para Modificar",
        "tipo_documento": "DNI",
        "nro_documento": unique_doc,
        "direccion": "Calle Vieja 123",
        "cod_postal": "5500",
        "tipo_cliente": "socio",
    }
    res = client.post("/clientes", json=payload)
    assert res.status_code == 201
    id_cliente = res.json()["id_cliente"]

    # Modificar dirección
    update_res = client.put(f"/clientes/{id_cliente}", json={"direccion": "Calle Nueva 456"})
    assert update_res.status_code == 200
    assert update_res.json()["direccion"] == "Calle Nueva 456"


def test_eliminar_cliente_con_comprobantes_falla(client):
    # Buscar un cliente que tenga comprobantes históricos
    with get_db_cursor() as cur:
        cur.execute("SELECT id_cliente FROM comprobante LIMIT 1;")
        row = cur.fetchone()

    if row:
        id_cliente = row["id_cliente"]
        response = client.delete(f"/clientes/{id_cliente}")
        # Restricción de borrado RN-14 -> SQLSTATE 23503 -> 409 Conflict
        assert response.status_code == 409
        assert response.json()["sqlstate"] == "23503"
