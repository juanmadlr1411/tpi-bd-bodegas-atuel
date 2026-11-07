"""Consultas e inserción por lotes de H3 (PostgreSQL/psycopg)."""


def consultar_estado(cur):
    """Devuelve las cantidades actuales de registros y stock."""

    cur.execute("""
        SELECT
            (SELECT COUNT(*) FROM ingreso),
            (SELECT COUNT(*) FROM renglon_ingreso),
            (SELECT COUNT(*) FROM transferencia),
            (SELECT COUNT(*) FROM renglon_transferencia),
            (SELECT COALESCE(SUM(cantidad), 0) FROM stock_deposito),
            (SELECT COALESCE(SUM(cantidad), 0) FROM stock_sala)
    """)

    return dict(zip(
        (
            "ingresos",
            "renglones_ingreso",
            "transferencias",
            "renglones_transferencia",
            "deposito",
            "salas"
        ),
        cur.fetchone()
    ))


def consultar_stock_detallado(cur):
    """
    Obtiene las existencias por vino y por sala.
    """

    cur.execute("""
        SELECT cod_vino, cantidad
        FROM stock_deposito
    """)

    deposito = dict(cur.fetchall())

    cur.execute("""
        SELECT id_sala, cod_vino, cantidad
        FROM stock_sala
    """)

    salas = {
        (id_sala, cod_vino): cantidad
        for id_sala, cod_vino, cantidad in cur.fetchall()
    }

    return deposito, salas


def insertar_lote_ingresos(cur, documentos):

    if not documentos:
        return

    # 1. Insertar cabeceras y recuperar identificadores.
    parametros = [
        (
            doc["fecha"],
            doc["cod_transporte"],
            doc["cuit_bodega"]
        )
        for doc in documentos
    ]

    cur.executemany("""
        INSERT INTO ingreso (
            fecha, cod_transporte, cuit_bodega
        )
        VALUES (%s, %s, %s)
        RETURNING cod_ingreso
    """, parametros, returning=True)

    identificadores = [
        cursor.fetchone()[0]
        for cursor in cur.results()
    ]

    assert len(identificadores) == len(documentos)

    # 2. Insertar todos los renglones.
    renglones = [
        (cod_ingreso, renglon["cod_vino"], renglon["cantidad"])
        for cod_ingreso, documento in zip(
            identificadores, documentos
        )
        for renglon in documento["renglones"]
    ]

    cur.executemany("""
        INSERT INTO renglon_ingreso (
            cod_ingreso, cod_vino, cantidad
        )
        VALUES (%s, %s, %s)
    """, renglones)

    # 3. Finalizar los ingresos.
    parametros_ids = [(identificador,) for identificador in identificadores]

    cur.executemany("""
        UPDATE ingreso
        SET estado = 'terminado'
        WHERE cod_ingreso = %s
    """, parametros_ids)

    # 4. Ejecutar el procedimiento existente para cada ingreso.
    cur.executemany(
        "CALL sp_procesar_ingreso(%s)",
        parametros_ids
    )


def insertar_lote_transferencias(cur, documentos):

    if not documentos:
        return

    # 1. Insertar cabeceras.
    parametros = [
        (doc["fecha_confeccion"], doc["id_sala"])
        for doc in documentos
    ]

    cur.executemany("""
        INSERT INTO transferencia (
            fecha_confeccion, id_sala
        )
        VALUES (%s, %s)
        RETURNING nro_transferencia
    """, parametros, returning=True)

    identificadores = [
        cursor.fetchone()[0]
        for cursor in cur.results()
    ]

    assert len(identificadores) == len(documentos)

    # 2. Insertar renglones.
    renglones = [
        (numero, renglon["cod_vino"], renglon["cantidad"])
        for numero, documento in zip(
            identificadores, documentos
        )
        for renglon in documento["renglones"]
    ]

    cur.executemany("""
        INSERT INTO renglon_transferencia (
            nro_transferencia, cod_vino, cantidad
        )
        VALUES (%s, %s, %s)
    """, renglones)

    # 3. Finalizar las transferencias.
    parametros_ids = [(identificador,) for identificador in identificadores]

    cur.executemany("""
        UPDATE transferencia
        SET estado = 'terminado'
        WHERE nro_transferencia = %s
    """, parametros_ids)

    # 4. Procesarlas utilizando el procedimiento de H2.
    cur.executemany(
        "CALL sp_procesar_transferencia(%s)",
        parametros_ids
    )
