import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.database import get_db_connection, get_db_cursor


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _obtener_contexto_venta(offset_vino: int = 0) -> dict:
    with get_db_cursor() as cur:
        cur.execute("SELECT cod_vino, precio FROM vino ORDER BY cod_vino OFFSET %s LIMIT 1;", (offset_vino,))
        vino = cur.fetchone()

        cur.execute("SELECT id_cliente, porcentaje_descuento FROM cliente ORDER BY id_cliente LIMIT 1;")
        cliente = cur.fetchone()

        cur.execute("SELECT id_sala FROM sala_venta ORDER BY id_sala LIMIT 1;")
        sala = cur.fetchone()

    return {
        "cod_vino": vino["cod_vino"],
        "precio": float(vino["precio"]),
        "id_cliente": cliente["id_cliente"],
        "descuento": float(cliente["porcentaje_descuento"]),
        "id_sala": sala["id_sala"],
    }


def _fijar_stock(id_sala: int, cod_vino: int, cantidad: int) -> None:
    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO stock_sala (id_sala, cod_vino, cantidad)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id_sala, cod_vino)
                    DO UPDATE SET cantidad = EXCLUDED.cantidad;
                    """,
                    (id_sala, cod_vino, cantidad),
                )


def _stock_actual(id_sala: int, cod_vino: int) -> int:
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT cantidad FROM stock_sala WHERE id_sala = %s AND cod_vino = %s;",
            (id_sala, cod_vino),
        )
        return cur.fetchone()["cantidad"]


def _contar_comprobantes() -> int:
    with get_db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM comprobante;")
        return cur.fetchone()["total"]


def test_crear_venta_exitosa_calcula_total_y_descuenta_stock(client):
    ctx = _obtener_contexto_venta(offset_vino=0)
    cantidad = 3
    _fijar_stock(ctx["id_sala"], ctx["cod_vino"], 50)

    payload = {
        "id_cliente": ctx["id_cliente"],
        "id_sala": ctx["id_sala"],
        "renglones": [{"cod_vino": ctx["cod_vino"], "cantidad": cantidad}],
    }

    response = client.post("/comprobantes", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["id_cliente"] == ctx["id_cliente"]
    assert data["id_sala"] == ctx["id_sala"]
    assert len(data["renglones"]) == 1

    renglon = data["renglones"][0]
    assert renglon["cod_vino"] == ctx["cod_vino"]
    assert renglon["cantidad"] == cantidad
    assert float(renglon["precio_unitario"]) == ctx["precio"]
    assert float(renglon["descuento"]) == ctx["descuento"]

    total_esperado = round(cantidad * ctx["precio"] * (1 - ctx["descuento"] / 100.0), 2)
    assert float(data["total"]) == total_esperado
    assert float(renglon["subtotal"]) == total_esperado

    with get_db_cursor() as cur:
        cur.execute(
            "SELECT fn_total_comprobante(%s) AS total;",
            (data["nro_comprobante"],),
        )
        total_bd = float(cur.fetchone()["total"])
    assert float(data["total"]) == total_bd

    assert _stock_actual(ctx["id_sala"], ctx["cod_vino"]) == 50 - cantidad

    detalle = client.get(f"/comprobantes/{data['nro_comprobante']}")
    assert detalle.status_code == 200
    assert detalle.json()["nro_comprobante"] == data["nro_comprobante"]
    assert float(detalle.json()["total"]) == total_esperado


def test_crear_venta_sin_stock_rechaza_y_revierte_transaccion(client):
    ctx = _obtener_contexto_venta(offset_vino=1)
    stock_disponible = 5
    _fijar_stock(ctx["id_sala"], ctx["cod_vino"], stock_disponible)

    comprobantes_antes = _contar_comprobantes()

    payload = {
        "id_cliente": ctx["id_cliente"],
        "id_sala": ctx["id_sala"],
        "renglones": [{"cod_vino": ctx["cod_vino"], "cantidad": stock_disponible + 1}],
    }

    response = client.post("/comprobantes", json=payload)

    assert response.status_code == 409
    error = response.json()
    assert error["sqlstate"] == "P0001"
    assert "RN-09" in error["message"] or "Stock insuficiente" in error["message"]

    assert _contar_comprobantes() == comprobantes_antes
    assert _stock_actual(ctx["id_sala"], ctx["cod_vino"]) == stock_disponible


def test_obtener_comprobante_inexistente(client):
    response = client.get("/comprobantes/999999999")
    assert response.status_code == 404
