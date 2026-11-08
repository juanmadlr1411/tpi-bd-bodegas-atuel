"""Añade documentos pendientes a una base H3 ya cargada, sin impactar stock.

Por defecto solo consulta. Para aplicar: --aplicar --confirmo-base-aislada.
Requiere variables POSTGRES_* en .env y conexión a la BD elegida.
"""

import argparse
from conexion import conectar

ESTADOS = ("en_confeccion", "terminado")
POR_ESTADO_Y_TIPO = 2


def obtener_resumen(cur):
    cur.execute("""
        SELECT tipo, estado, COUNT(*)::integer
        FROM (
            SELECT 'ingreso'::text AS tipo, estado FROM ingreso
            UNION ALL
            SELECT 'transferencia'::text AS tipo, estado FROM transferencia
        ) d
        WHERE estado <> 'procesado'
        GROUP BY tipo, estado
        ORDER BY tipo, estado
    """)
    return {(tipo, estado): total for tipo, estado, total in cur.fetchall()}


def imprimir_resumen(cur):
    cur.execute("SELECT current_database()")
    print("Base de datos:", cur.fetchone()[0])
    resumen = obtener_resumen(cur)
    for tipo in ("ingreso", "transferencia"):
        for estado in ESTADOS:
            print(f"{tipo} / {estado}: {resumen.get((tipo, estado), 0)}")
    cur.execute("SELECT COUNT(*) FROM vw_documentos_pendientes")
    print("vw_documentos_pendientes:", cur.fetchone()[0])
    return resumen


def exigir_triggers(cur):
    requeridos = {
        "trg_validar_estado_ingreso",
        "trg_validar_estado_transferencia",
        "trg_bloquear_renglon_ingreso",
        "trg_bloquear_renglon_transferencia",
        "trg_fecha_confeccion_transferencia",
    }
    cur.execute("""
        SELECT tgname FROM pg_trigger
        WHERE NOT tgisinternal AND tgenabled IN ('O', 'A')
    """)
    activos = {fila[0] for fila in cur.fetchall()}
    faltantes = requeridos - activos
    if faltantes:
        raise RuntimeError("Triggers H2 faltantes o desactivados: " + ", ".join(sorted(faltantes)))


def insertar_pendientes(cur):
    # Evita duplicados en ejecuciones repetidas: si hay pendientes preexistentes,
    # el script no añade nuevos sin inspección manual.
    existentes = obtener_resumen(cur)
    if existentes:
        raise RuntimeError(
            "Ya existen documentos pendientes. Se canceló para evitar duplicados. "
            "Revisá los resultados del modo de consulta."
        )
    exigir_triggers(cur)

    cur.execute("""
        SELECT v.cod_vino, v.cuit_bodega, t.cod_transporte
        FROM vino v CROSS JOIN transportista t
        ORDER BY v.cod_vino, t.cod_transporte LIMIT 1
    """)
    datos = cur.fetchone()
    cur.execute("SELECT id_sala FROM sala_venta ORDER BY id_sala LIMIT 1")
    sala_fila = cur.fetchone()
    if datos is None or sala_fila is None:
        raise RuntimeError("Faltan vinos, bodegas, transportistas o salas: cargar maestros primero.")
    vino, bodega, transporte = datos
    sala = sala_fila[0]

    cur.execute("SELECT COALESCE(SUM(cantidad), 0) FROM stock_deposito")
    stock_deposito_inicial = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(cantidad), 0) FROM stock_sala")
    stock_sala_inicial = cur.fetchone()[0]

    for estado in ESTADOS:
        for _ in range(POR_ESTADO_Y_TIPO):
            # Estado inicial correcto; los renglones se insertan antes de finalizar.
            cur.execute("""
                INSERT INTO ingreso (fecha, cod_transporte, cuit_bodega)
                VALUES (CURRENT_DATE, %s, %s) RETURNING cod_ingreso
            """, (transporte, bodega))
            cod_ingreso = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO renglon_ingreso (cod_ingreso, cod_vino, cantidad)
                VALUES (%s, %s, 1)
            """, (cod_ingreso, vino))
            if estado == "terminado":
                cur.execute("UPDATE ingreso SET estado = 'terminado' WHERE cod_ingreso = %s", (cod_ingreso,))

            # El trigger RN-11 asigna la fecha actual de confección.
            cur.execute("""
                INSERT INTO transferencia (id_sala) VALUES (%s)
                RETURNING nro_transferencia
            """, (sala,))
            nro_transferencia = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO renglon_transferencia (nro_transferencia, cod_vino, cantidad)
                VALUES (%s, %s, 1)
            """, (nro_transferencia, vino))
            if estado == "terminado":
                cur.execute("""
                    UPDATE transferencia SET estado = 'terminado'
                    WHERE nro_transferencia = %s
                """, (nro_transferencia,))

    cur.execute("SELECT COALESCE(SUM(cantidad), 0) FROM stock_deposito")
    if cur.fetchone()[0] != stock_deposito_inicial:
        raise RuntimeError("Stock de depósito alterado indebidamente")
    cur.execute("SELECT COALESCE(SUM(cantidad), 0) FROM stock_sala")
    if cur.fetchone()[0] != stock_sala_inicial:
        raise RuntimeError("Stock de sala alterado indebidamente")
    resumen = obtener_resumen(cur)
    for tipo in ("ingreso", "transferencia"):
        for estado in ESTADOS:
            if resumen.get((tipo, estado)) != POR_ESTADO_Y_TIPO:
                raise RuntimeError(f"Estado inesperado: {tipo}/{estado}")
    cur.execute("SELECT COUNT(*) FROM vw_documentos_pendientes")
    if cur.fetchone()[0] != POR_ESTADO_Y_TIPO * len(ESTADOS) * 2:
        raise RuntimeError("Vista vw_documentos_pendientes no refleja los ocho documentos")


def main():
    parser = argparse.ArgumentParser(description="Crea 8 documentos pendientes en H3")
    parser.add_argument("--aplicar", action="store_true", help="Inserta ocho documentos y confirma")
    parser.add_argument("--confirmo-base-aislada", action="store_true", help="Declara que la BD es una copia local de H3")
    args = parser.parse_args()
    if args.aplicar and not args.confirmo_base_aislada:
        parser.error("Para modificar datos agregá --confirmo-base-aislada")
    conn = conectar()
    try:
        with conn.cursor() as cur:
            if args.aplicar:
                # Dos ejecuciones simultáneas de este script no pueden duplicar el lote.
                cur.execute("SELECT pg_advisory_xact_lock(hashtext('h3_pendientes_2026'))")
                insertar_pendientes(cur)
                print("Pendientes insertados y validados. COMMIT en curso.")
                conn.commit()
            else:
                print("Solo lectura: ninguna fila será modificada.")
            imprimir_resumen(cur)
        conn.rollback()  # En modo lectura evita dejar transacciones abiertas.
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
