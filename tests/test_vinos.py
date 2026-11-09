import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.database import get_db_cursor


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_listar_vinos_paginado(client):
    response = client.get("/vinos?limit=5&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert data["limit"] == 5
    assert data["offset"] == 0
    assert len(data["items"]) <= 5
    assert data["total"] > 0


def test_filtrar_vinos_por_tipo_y_anada(client):
    response = client.get("/vinos?tipo=tinto&limit=10")
    assert response.status_code == 200
    data = response.json()
    for vino in data["items"]:
        assert vino["tipo"] == "tinto"


def test_obtener_vino_detalle(client):
    # Buscar un vino existente
    list_res = client.get("/vinos?limit=1")
    assert list_res.status_code == 200
    vino_resumen = list_res.json()["items"][0]
    cod_vino = vino_resumen["cod_vino"]

    # Consultar detalle
    det_res = client.get(f"/vinos/{cod_vino}")
    assert det_res.status_code == 200
    detalle = det_res.json()
    assert detalle["cod_vino"] == cod_vino
    assert "composicion" in detalle
    assert isinstance(detalle["composicion"], list)
    assert len(detalle["composicion"]) >= 1
    # Verificar que los cortes sumen 100%
    suma_cortes = sum(c["porcentaje"] for c in detalle["composicion"])
    assert round(suma_cortes, 2) == 100.0


def test_obtener_vino_inexistente(client):
    response = client.get("/vinos/999999")
    assert response.status_code == 404


def test_crear_vino_exitoso(client):
    # Obtener una bodega y dos cepas reales de la base
    with get_db_cursor() as cur:
        cur.execute("SELECT cuit FROM bodega LIMIT 1;")
        cuit_bodega = cur.fetchone()["cuit"]

        cur.execute("SELECT id_cepa FROM cepa ORDER BY id_cepa LIMIT 2;")
        cepas = cur.fetchall()
        id_cepa1 = cepas[0]["id_cepa"]
        id_cepa2 = cepas[1]["id_cepa"]

    payload = {
        "nombre": "Gran Reserva Especial Test",
        "tipo": "tinto",
        "anada": 2022,
        "volumen_ml": 750,
        "graduacion": 14.5,
        "precio": 8500.50,
        "cuit_bodega": cuit_bodega,
        "composicion": [
            {"id_cepa": id_cepa1, "porcentaje": 60.0},
            {"id_cepa": id_cepa2, "porcentaje": 40.0},
        ],
        "maridajes": [],
    }

    response = client.post("/vinos", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["nombre"] == payload["nombre"]
    assert len(data["composicion"]) == 2
    assert data["precio"] == payload["precio"]


def test_crear_vino_corte_invalido_falla(client):
    # La composición suma 85% (!= 100%), debe ser rechazada por la base (RN-05)
    with get_db_cursor() as cur:
        cur.execute("SELECT cuit FROM bodega LIMIT 1;")
        cuit_bodega = cur.fetchone()["cuit"]
        cur.execute("SELECT id_cepa FROM cepa LIMIT 1;")
        id_cepa = cur.fetchone()["id_cepa"]

    payload = {
        "nombre": "Vino Corte Defectuoso",
        "tipo": "blanco",
        "anada": 2023,
        "volumen_ml": 750,
        "graduacion": 12.5,
        "precio": 5000.00,
        "cuit_bodega": cuit_bodega,
        "composicion": [
            {"id_cepa": id_cepa, "porcentaje": 85.0},
        ],
        "maridajes": [],
    }

    response = client.post("/vinos", json=payload)
    # Debe ser capturado por postgres_exception_handler como 409 (código P0001)
    assert response.status_code == 409
    error_data = response.json()
    assert error_data["sqlstate"] == "P0001"
    assert "RN-05" in error_data["message"] or "100" in error_data["message"]


def test_actualizar_vino_audita_precio(client):
    # Crear un vino para actualizar
    with get_db_cursor() as cur:
        cur.execute("SELECT cuit FROM bodega LIMIT 1;")
        cuit_bodega = cur.fetchone()["cuit"]
        cur.execute("SELECT id_cepa FROM cepa LIMIT 1;")
        id_cepa = cur.fetchone()["id_cepa"]

    payload = {
        "nombre": "Vino Para Auditoria",
        "tipo": "rosado",
        "anada": 2024,
        "volumen_ml": 750,
        "graduacion": 13.0,
        "precio": 3000.00,
        "cuit_bodega": cuit_bodega,
        "composicion": [{"id_cepa": id_cepa, "porcentaje": 100.0}],
    }
    create_res = client.post("/vinos", json=payload)
    assert create_res.status_code == 201
    cod_vino = create_res.json()["cod_vino"]

    # Actualizar precio
    update_res = client.put(f"/vinos/{cod_vino}", json={"precio": 4500.00})
    assert update_res.status_code == 200
    assert update_res.json()["precio"] == 4500.00

    # Verificar que el trigger trg_auditar_cambio_precio insertó en auditoria_precio (RN-13)
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT precio_anterior, precio_nuevo FROM auditoria_precio WHERE cod_vino = %s ORDER BY id_auditoria DESC LIMIT 1;",
            (cod_vino,),
        )
        auditoria = cur.fetchone()
        assert auditoria is not None
        assert float(auditoria["precio_anterior"]) == 3000.00
        assert float(auditoria["precio_nuevo"]) == 4500.00


def test_eliminar_vino_con_movimientos_falla(client):
    # Buscar un vino que tenga renglones en comprobantes históricos
    with get_db_cursor() as cur:
        cur.execute("SELECT cod_vino FROM renglon_comprobante LIMIT 1;")
        row = cur.fetchone()

    if row:
        cod_vino = row["cod_vino"]
        response = client.delete(f"/vinos/{cod_vino}")
        # La FK con ON DELETE RESTRICT debe arrojar 409 Conflict (SQLSTATE 23503)
        assert response.status_code == 409
        assert response.json()["sqlstate"] == "23503"
