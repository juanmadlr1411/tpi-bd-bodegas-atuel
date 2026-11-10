import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.database import get_db_connection


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _obtener_datos_maestros():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT cod_vino, cuit_bodega FROM vino ORDER BY cod_vino LIMIT 1;")
            vino = cur.fetchone()
            cur.execute("SELECT cod_transporte FROM transportista ORDER BY cod_transporte LIMIT 1;")
            transp = cur.fetchone()
            cur.execute("SELECT id_sala FROM sala_venta ORDER BY id_sala LIMIT 1;")
            sala = cur.fetchone()
            return vino["cod_vino"], vino["cuit_bodega"].strip(), transp["cod_transporte"], sala["id_sala"]


def _stock_deposito(cod_vino: int) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT cantidad FROM stock_deposito WHERE cod_vino = %s;", (cod_vino,))
            row = cur.fetchone()
            return row["cantidad"] if row else 0


def _stock_sala(id_sala: int, cod_vino: int) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cantidad FROM stock_sala WHERE id_sala = %s AND cod_vino = %s;",
                (id_sala, cod_vino),
            )
            row = cur.fetchone()
            return row["cantidad"] if row else 0


def test_1_circuito_feliz_ingreso(client: TestClient):
    """
    1. Circuito feliz de ingreso: crear -> renglón -> terminar -> procesar -> validar incremento en stock_deposito.
    """
    cod_vino, cuit_bodega, cod_transporte, _ = _obtener_datos_maestros()
    stock_inicial = _stock_deposito(cod_vino)
    cantidad_ingresar = 50

    # 1. Crear ingreso en_confeccion
    res_crear = client.post(
        "/ingresos",
        json={"cuit_bodega": cuit_bodega, "cod_transporte": cod_transporte},
    )
    assert res_crear.status_code == 201, res_crear.text
    datos_ingreso = res_crear.json()
    cod_ingreso = datos_ingreso["cod_ingreso"]
    assert datos_ingreso["estado"] == "en_confeccion"

    # 2. Agregar renglón
    res_renglon = client.post(
        f"/ingresos/{cod_ingreso}/renglones",
        json={"cod_vino": cod_vino, "cantidad": cantidad_ingresar},
    )
    assert res_renglon.status_code == 201, res_renglon.text

    # 3. Terminar ingreso
    res_terminar = client.post(f"/ingresos/{cod_ingreso}/terminar")
    assert res_terminar.status_code == 200, res_terminar.text
    assert res_terminar.json()["estado"] == "terminado"

    # 4. Procesar ingreso (invoca CALL sp_procesar_ingreso)
    res_procesar = client.post(f"/ingresos/{cod_ingreso}/procesar")
    assert res_procesar.status_code == 200, res_procesar.text
    assert res_procesar.json()["estado"] == "procesado"

    # 5. Validar incremento en stock_deposito y detalle GET
    stock_final = _stock_deposito(cod_vino)
    assert stock_final == stock_inicial + cantidad_ingresar

    res_get = client.get(f"/ingresos/{cod_ingreso}")
    assert res_get.status_code == 200
    assert len(res_get.json()["renglones"]) == 1


def test_2_circuito_feliz_transferencia(client: TestClient):
    """
    2. Circuito feliz de transferencia: crear -> renglón -> terminar -> procesar
       -> validar descuento en depósito y alta/incremento en stock_sala.
    """
    cod_vino, _, cod_transporte, id_sala = _obtener_datos_maestros()
    stock_dep_antes = _stock_deposito(cod_vino)
    stock_sala_antes = _stock_sala(id_sala, cod_vino)
    cantidad_transferir = 10

    # 1. Crear transferencia en_confeccion
    res_crear = client.post(
        "/transferencias",
        json={"id_sala": id_sala, "id_transportista": cod_transporte},
    )
    assert res_crear.status_code == 201, res_crear.text
    nro_transferencia = res_crear.json()["nro_transferencia"]
    assert res_crear.json()["estado"] == "en_confeccion"

    # 2. Agregar renglón
    res_renglon = client.post(
        f"/transferencias/{nro_transferencia}/renglones",
        json={"cod_vino": cod_vino, "cantidad": cantidad_transferir},
    )
    assert res_renglon.status_code == 201, res_renglon.text

    # 3. Terminar transferencia
    res_terminar = client.post(f"/transferencias/{nro_transferencia}/terminar")
    assert res_terminar.status_code == 200, res_terminar.text
    assert res_terminar.json()["estado"] == "terminado"

    # 4. Procesar transferencia (invoca CALL sp_procesar_transferencia)
    res_procesar = client.post(f"/transferencias/{nro_transferencia}/procesar")
    assert res_procesar.status_code == 200, res_procesar.text
    assert res_procesar.json()["estado"] == "procesado"

    # 5. Validar impacto atómico en stock_deposito y stock_sala
    stock_dep_despues = _stock_deposito(cod_vino)
    stock_sala_despues = _stock_sala(id_sala, cod_vino)

    assert stock_dep_despues == stock_dep_antes - cantidad_transferir
    assert stock_sala_despues == stock_sala_antes + cantidad_transferir

    res_get = client.get(f"/transferencias/{nro_transferencia}")
    assert res_get.status_code == 200
    assert len(res_get.json()["renglones"]) == 1


def test_3_violacion_procesar_transferencia_en_confeccion(client: TestClient):
    """
    3. Violación: intentar procesar una transferencia que aún está en_confeccion (debe fallar con error 409).
    """
    cod_vino, _, _, id_sala = _obtener_datos_maestros()
    stock_dep_antes = _stock_deposito(cod_vino)

    # 1. Crear transferencia en_confeccion y cargarle un renglón (sin terminarla)
    res_crear = client.post("/transferencias", json={"id_sala": id_sala})
    assert res_crear.status_code == 201
    nro_transferencia = res_crear.json()["nro_transferencia"]

    res_renglon = client.post(
        f"/transferencias/{nro_transferencia}/renglones",
        json={"cod_vino": cod_vino, "cantidad": 5},
    )
    assert res_renglon.status_code == 201

    # 2. Intentar procesarla estando 'en_confeccion' -> Debe fallar con 409 Conflict (SQLSTATE P0001)
    res_procesar = client.post(f"/transferencias/{nro_transferencia}/procesar")
    assert res_procesar.status_code == 409, res_procesar.text
    body = res_procesar.json()
    assert body["sqlstate"] == "P0001"

    # 3. Verificar que el stock en depósito no sufrió alteraciones
    assert _stock_deposito(cod_vino) == stock_dep_antes
