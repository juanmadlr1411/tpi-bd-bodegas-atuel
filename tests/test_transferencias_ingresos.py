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

    # 6. RN-10: impedir que un ingreso se procese dos veces
    res_reprocesar = client.post(f"/ingresos/{cod_ingreso}/procesar")
    assert res_reprocesar.status_code == 409
    error = res_reprocesar.json()
    assert error["sqlstate"] == "P0001"
    assert "RN-10" in error["message"]
    assert _stock_deposito(cod_vino) == stock_final


def test_2_circuito_feliz_transferencia(client: TestClient):
    """
    2. Circuito feliz de transferencia: crear -> renglón -> terminar -> procesar
       -> validar descuento en depósito y alta/incremento en stock_sala.
    """
    cod_vino, _, _, id_sala = _obtener_datos_maestros()
    stock_dep_antes = _stock_deposito(cod_vino)
    stock_sala_antes = _stock_sala(id_sala, cod_vino)
    cantidad_transferir = 10

    # 1. Crear transferencia en_confeccion
    res_crear = client.post(
        "/transferencias",
        json={"id_sala": id_sala},
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

    # 6. RN-11: impedir que una transferencia se procese dos veces
    res_reprocesar = client.post(f"/transferencias/{nro_transferencia}/procesar")
    assert res_reprocesar.status_code == 409
    error = res_reprocesar.json()
    assert error["sqlstate"] == "P0001"
    assert "RN-11" in error["message"]
    assert _stock_deposito(cod_vino) == stock_dep_despues
    assert _stock_sala(id_sala, cod_vino) == stock_sala_despues


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


def test_4_rn12_bloquear_renglones_transferencia_terminada(client: TestClient):
    """RN-12: una transferencia terminada no admite nuevos renglones."""
    cod_vino, _, _, id_sala = _obtener_datos_maestros()
    stock_deposito_antes = _stock_deposito(cod_vino)
    stock_sala_antes = _stock_sala(id_sala, cod_vino)

    # 1. Crear transferencia
    res_crear = client.post("/transferencias", json={"id_sala": id_sala})
    assert res_crear.status_code == 201, res_crear.text
    nro = res_crear.json()["nro_transferencia"]

    # 2. Agregar un renglón válido
    res_renglon = client.post(
        f"/transferencias/{nro}/renglones",
        json={"cod_vino": cod_vino, "cantidad": 5},
    )
    assert res_renglon.status_code == 201, res_renglon.text

    # 3. Terminar el documento
    res_terminar = client.post(f"/transferencias/{nro}/terminar")
    assert res_terminar.status_code == 200, res_terminar.text
    assert res_terminar.json()["estado"] == "terminado"

    # 4. Intentar agregar otro renglón
    res_rechazo = client.post(
        f"/transferencias/{nro}/renglones",
        json={"cod_vino": cod_vino, "cantidad": 10},
    )

    # 5. Verificar RN-12
    assert res_rechazo.status_code == 409, res_rechazo.text
    error = res_rechazo.json()
    assert error["sqlstate"] == "P0001"
    assert "RN-12" in error["message"]

    # 6. Verificar que no se modificó el documento
    res_get = client.get(f"/transferencias/{nro}")
    assert res_get.status_code == 200, res_get.text
    datos = res_get.json()
    assert datos["estado"] == "terminado"
    assert len(datos["renglones"]) == 1
    assert datos["renglones"][0]["cantidad"] == 5

    # 7. Comprobar que tampoco cambió el inventario
    assert _stock_deposito(cod_vino) == stock_deposito_antes
    assert _stock_sala(id_sala, cod_vino) == stock_sala_antes


def test_5_rn10_bloquear_renglones_ingreso_terminado(client: TestClient):
    """RN-12 / RN-10: un ingreso terminado no admite nuevos renglones."""
    cod_vino, cuit_bodega, cod_transporte, _ = _obtener_datos_maestros()
    stock_antes = _stock_deposito(cod_vino)

    # 1. Crear ingreso
    res_crear = client.post(
        "/ingresos",
        json={"cuit_bodega": cuit_bodega, "cod_transporte": cod_transporte},
    )
    assert res_crear.status_code == 201, res_crear.text
    cod_ingreso = res_crear.json()["cod_ingreso"]

    # 2. Agregar renglón
    res_renglon = client.post(
        f"/ingresos/{cod_ingreso}/renglones",
        json={"cod_vino": cod_vino, "cantidad": 5},
    )
    assert res_renglon.status_code == 201, res_renglon.text

    # 3. Terminar ingreso
    res_terminar = client.post(f"/ingresos/{cod_ingreso}/terminar")
    assert res_terminar.status_code == 200, res_terminar.text
    assert res_terminar.json()["estado"] == "terminado"

    # 4. Intentar agregar otro renglón
    res_rechazo = client.post(
        f"/ingresos/{cod_ingreso}/renglones",
        json={"cod_vino": cod_vino, "cantidad": 10},
    )

    # 5. Verificar rechazo por estado terminado
    assert res_rechazo.status_code == 409, res_rechazo.text
    error = res_rechazo.json()
    assert error["sqlstate"] == "P0001"
    assert "RN-12" in error["message"] or "en_confeccion" in error["message"]

    # 6. Comprobar que el ingreso permanece intacto
    res_get = client.get(f"/ingresos/{cod_ingreso}")
    assert res_get.status_code == 200, res_get.text
    datos = res_get.json()
    assert datos["estado"] == "terminado"
    assert len(datos["renglones"]) == 1
    assert datos["renglones"][0]["cantidad"] == 5

    # 7. Comprobar que el stock no cambió
    assert _stock_deposito(cod_vino) == stock_antes


def test_6_rn11_transferencia_stock_insuficiente(client: TestClient):
    """RN-11: rechazar transferencias con stock insuficiente al procesar."""
    cod_vino, _, _, id_sala = _obtener_datos_maestros()
    stock_dep_antes = _stock_deposito(cod_vino)
    stock_sala_antes = _stock_sala(id_sala, cod_vino)

    cantidad_solicitada = stock_dep_antes + 1000

    # 1. Crear transferencia
    res_crear = client.post("/transferencias", json={"id_sala": id_sala})
    assert res_crear.status_code == 201, res_crear.text
    nro = res_crear.json()["nro_transferencia"]

    # 2. Agregar renglón con cantidad mayor al stock
    res_renglon = client.post(
        f"/transferencias/{nro}/renglones",
        json={"cod_vino": cod_vino, "cantidad": cantidad_solicitada},
    )
    assert res_renglon.status_code == 201, res_renglon.text

    # 3. Terminar la transferencia
    res_terminar = client.post(f"/transferencias/{nro}/terminar")
    assert res_terminar.status_code == 200, res_terminar.text
    assert res_terminar.json()["estado"] == "terminado"

    # 4. Intentar procesar la transferencia -> Debe fallar por stock insuficiente
    res_procesar = client.post(f"/transferencias/{nro}/procesar")
    assert res_procesar.status_code == 409, res_procesar.text
    error = res_procesar.json()
    assert error["sqlstate"] == "P0001"
    assert "RN-11" in error["message"]
    assert "Stock insuficiente" in error["message"]

    # 5. Verificar que las existencias no cambiaron
    assert _stock_deposito(cod_vino) == stock_dep_antes
    assert _stock_sala(id_sala, cod_vino) == stock_sala_antes

    # 6. Verificar que el documento continúa terminado
    res_get = client.get(f"/transferencias/{nro}")
    assert res_get.status_code == 200, res_get.text
    datos = res_get.json()
    assert datos["estado"] == "terminado"
    assert len(datos["renglones"]) == 1
    assert datos["renglones"][0]["cantidad"] == cantidad_solicitada


def test_7_atomicidad_transferencia_dos_vinos(client: TestClient):
    """
    RN-11: si falla el segundo renglón, PostgreSQL debe revertir
    atómicamente los movimientos del primero.
    """
    _, _, _, id_sala = _obtener_datos_maestros()

    # 1. Buscar dos vinos con stock positivo en depósito
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cod_vino, cantidad
                FROM stock_deposito
                WHERE cantidad > 0
                ORDER BY cod_vino
                LIMIT 2;
            """)
            vinos = cur.fetchall()

    assert len(vinos) == 2, "La prueba requiere al menos dos vinos con stock positivo en depósito"
    vino_1 = vinos[0]["cod_vino"]
    vino_2 = vinos[1]["cod_vino"]

    deposito_1_antes = _stock_deposito(vino_1)
    deposito_2_antes = _stock_deposito(vino_2)
    sala_1_antes = _stock_sala(id_sala, vino_1)
    sala_2_antes = _stock_sala(id_sala, vino_2)

    cantidad_vino_1 = 1
    cantidad_vino_2 = deposito_2_antes + 500

    # 2. Crear transferencia
    res_crear = client.post("/transferencias", json={"id_sala": id_sala})
    assert res_crear.status_code == 201, res_crear.text
    nro = res_crear.json()["nro_transferencia"]

    # 3. Primer vino con stock suficiente
    res_renglon_1 = client.post(
        f"/transferencias/{nro}/renglones",
        json={"cod_vino": vino_1, "cantidad": cantidad_vino_1},
    )
    assert res_renglon_1.status_code == 201, res_renglon_1.text

    # 4. Segundo vino con stock insuficiente
    res_renglon_2 = client.post(
        f"/transferencias/{nro}/renglones",
        json={"cod_vino": vino_2, "cantidad": cantidad_vino_2},
    )
    assert res_renglon_2.status_code == 201, res_renglon_2.text

    # 5. Terminar transferencia
    res_terminar = client.post(f"/transferencias/{nro}/terminar")
    assert res_terminar.status_code == 200, res_terminar.text

    # 6. Procesar: debe fallar por el segundo vino
    res_procesar = client.post(f"/transferencias/{nro}/procesar")
    assert res_procesar.status_code == 409, res_procesar.text
    error = res_procesar.json()
    assert error["sqlstate"] == "P0001"
    assert "RN-11" in error["message"]
    assert "Stock insuficiente" in error["message"]

    # 7. Verificar ROLLBACK del primer vino y que nada cambió
    assert _stock_deposito(vino_1) == deposito_1_antes
    assert _stock_sala(id_sala, vino_1) == sala_1_antes
    assert _stock_deposito(vino_2) == deposito_2_antes
    assert _stock_sala(id_sala, vino_2) == sala_2_antes

    res_get = client.get(f"/transferencias/{nro}")
    assert res_get.status_code == 200, res_get.text
    datos = res_get.json()
    assert datos["estado"] == "terminado"
    assert len(datos["renglones"]) == 2


def test_8_transferencia_rechaza_campos_desconocidos(client: TestClient):
    """
    La API no debe aceptar campos que no puede almacenar (extra='forbid').
    """
    _, _, _, id_sala = _obtener_datos_maestros()
    res = client.post(
        "/transferencias",
        json={"id_sala": id_sala, "id_transportista": 999},
    )
    assert res.status_code == 422, res.text
    errores = res.json()["detail"]
    assert any("id_transportista" in str(error["loc"]) for error in errores)
