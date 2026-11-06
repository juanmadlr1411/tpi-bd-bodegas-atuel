"""Carga H3 Bodegas del Atuel (reutiliza simulador e insertores ya probados).

Modos:
    python db/seed/carga_h3_final.py --verificar
    python db/seed/carga_h3_final.py --probar --meses 1
    python db/seed/carga_h3_final.py --probar --meses 58
    python db/seed/carga_h3_final.py --cargar --confirmo-carga-definitiva

IMPORTANTE: --cargar solo sobre una BD de carga LIMPIA y AISLADA.
"""

import argparse
from collections import Counter
from datetime import date
from time import perf_counter

from carga_transaccional import conectar
from datos_maestros import obtener_datos_maestros
from inventario_historico import InventarioHistorico
from plan_carga import ConfiguracionCarga, planificar_carga
from simular_carga_58_meses import simular_mes
from probar_lotes_h3 import insertar_lote_ingresos, insertar_lote_transferencias
from persistencia_transaccional import consultar_estado, consultar_stock_detallado


FECHA_PRUEBA = date(2026, 10, 20)
CLAVES_CANTIDAD = ("ingresos", "renglones_ingreso", "transferencias",
                   "renglones_transferencia", "comprobantes", "renglones_venta")


def verificar_reglas_ventas(conn):
    """Prueba RN-08/RN-09 en una transaccion que siempre se revierte."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.id_sala, s.cod_vino, s.cantidad, v.precio
                FROM stock_sala s
                JOIN vino v ON v.cod_vino = s.cod_vino
                WHERE s.cantidad >= 2 AND v.anada <= %s
                ORDER BY s.id_sala, s.cod_vino
                LIMIT 1
            """, (FECHA_PRUEBA.year,))
            item = cur.fetchone()
            if item is None:
                return False, "No hay stock de sala suficiente para verificar RN-09."
            sala, vino, stock_antes, precio = item
            cur.execute("""
                SELECT id_cliente FROM cliente
                WHERE fecha_alta <= %s AND porcentaje_descuento > 0
                ORDER BY id_cliente LIMIT 1
            """, (FECHA_PRUEBA,))
            cliente_fila = cur.fetchone()
            if cliente_fila is None:
                return False, "No hay cliente con descuento para comprobar RN-08."
            cliente = cliente_fila[0]
            cur.execute("""
                INSERT INTO comprobante (fecha, id_cliente, id_sala)
                VALUES (%s, %s, %s) RETURNING nro_comprobante
            """, (FECHA_PRUEBA, cliente, sala))
            nro = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO renglon_comprobante
                    (nro_comprobante, cod_vino, cantidad, precio_unitario,
                     descuento, subtotal)
                VALUES (%s, %s, 1, %s, 0, %s)
            """, (nro, vino, precio, precio))
            cur.execute("""
                SELECT total, fn_total_comprobante(%s)
                FROM comprobante WHERE nro_comprobante = %s
            """, (nro, nro))
            total_cabecera, total_funcion = cur.fetchone()
            cur.execute("""
                SELECT cantidad FROM stock_sala
                WHERE id_sala = %s AND cod_vino = %s
            """, (sala, vino))
            stock_despues = cur.fetchone()[0]
            rn08 = total_cabecera == total_funcion
            rn09 = stock_despues == stock_antes - 1
            mensaje = (f"RN-08: {'OK' if rn08 else 'PENDIENTE'} "
                       f"(cabecera={total_cabecera}, funcion={total_funcion}) | "
                       f"RN-09: {'OK' if rn09 else 'PENDIENTE'} "
                       f"(stock {stock_antes} -> {stock_despues})")
            return rn08 and rn09, mensaje
    finally:
        conn.rollback()  # La verificacion JAMAS deja una venta guardada.


def insertar_lote_comprobantes(cur, documentos):
    """Inserta cabeceras y detalles del mes. Los triggers calculan totales y stock."""
    if not documentos:
        return
    cur.executemany("""
        INSERT INTO comprobante (fecha, id_cliente, id_sala)
        VALUES (%s, %s, %s)
        RETURNING nro_comprobante
    """, [(d["fecha"], d["id_cliente"], d["id_sala"]) for d in documentos], returning=True)
    ids = [c.fetchone()[0] for c in cur.results()]
    if len(ids) != len(documentos):
        raise AssertionError("No se recuperaron todos los IDs de comprobante.")
    detalles = [
        (nro, r["cod_vino"], r["cantidad"], r["precio_unitario"],
         r["descuento"], r["subtotal"])
        for nro, documento in zip(ids, documentos)
        for r in documento["renglones"]
    ]
    cur.executemany("""
        INSERT INTO renglon_comprobante
            (nro_comprobante, cod_vino, cantidad, precio_unitario, descuento, subtotal)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, detalles)


def validar_estado(cur, inicial, totales, inventario, stock_inicial):
    actual = consultar_estado(cur)
    for nombre, clave in (
        ("ingresos", "ingresos"), ("renglones_ingreso", "renglones_ingreso"),
        ("transferencias", "transferencias"),
        ("renglones_transferencia", "renglones_transferencia"),
    ):
        assert actual[nombre] - inicial[nombre] == totales[clave], nombre
    # Los contadores de comprobantes pueden no estar en consultar_estado().
    cur.execute("SELECT COUNT(*) FROM comprobante")
    actual_comprobantes = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM renglon_comprobante")
    actual_renglones = cur.fetchone()[0]
    assert actual_comprobantes - inicial["comprobantes"] == totales["comprobantes"]
    assert actual_renglones - inicial["renglones_venta"] == totales["renglones_venta"]

    deposito_antes, salas_antes = stock_inicial
    deposito_despues, salas_despues = consultar_stock_detallado(cur)
    for vino in set(deposito_antes) | set(deposito_despues) | set(inventario.deposito):
        diferencia = deposito_despues.get(vino, 0) - deposito_antes.get(vino, 0)
        assert diferencia == inventario.deposito.get(vino, 0), f"Depósito: vino {vino}"
    for clave in set(salas_antes) | set(salas_despues) | set(inventario.salas):
        diferencia = salas_despues.get(clave, 0) - salas_antes.get(clave, 0)
        assert diferencia == inventario.salas.get(clave, 0), f"Sala/vino: {clave}"
    assert all(cantidad >= 0 for cantidad in inventario.deposito.values())
    assert all(cantidad >= 0 for cantidad in inventario.salas.values())


def cargar(meses, confirmar):
    config = ConfiguracionCarga()
    if meses < 1 or meses > 58:
        raise ValueError("--meses debe estar entre 1 y 58.")
    if confirmar and meses != 58:
        raise ValueError("La carga definitiva requiere exactamente 58 meses.")
    plan = planificar_carga(config)[:meses]
    import random
    rng = random.Random(config.semilla)
    inventario = InventarioHistorico()
    totales = Counter()

    conn = conectar()
    try:
        if conn.autocommit:
            raise RuntimeError("Se requiere una conexión sin autocommit.")
        correcto, explicacion = verificar_reglas_ventas(conn)
        print("Chequeo previo:", explicacion)
        if not correcto:
            raise RuntimeError("No se cargó nada: falta corregir RN-08/RN-09 en esta BD.")

        with conn.cursor() as cur:
            inicial = consultar_estado(cur)
            cur.execute("SELECT COUNT(*) FROM comprobante")
            inicial["comprobantes"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM renglon_comprobante")
            inicial["renglones_venta"] = cur.fetchone()[0]
            if confirmar and any(inicial[c] for c in (
                "ingresos", "renglones_ingreso", "transferencias", "renglones_transferencia",
                "comprobantes", "renglones_venta"
            )):
                raise RuntimeError(
                    "Carga definitiva bloqueada: existen transacciones previas. "
                    "Usá una base AISLADA y limpia, sin borrar datos automáticamente."
                )
            stock_inicial = consultar_stock_detallado(cur)
            datos = obtener_datos_maestros(conn)
            inicio = perf_counter()
            for periodo in plan:
                ingresos, transferencias, comprobantes = [], [], []
                resultado = simular_mes(
                    periodo, datos, inventario, rng,
                    emitir_ingreso=ingresos.append,
                    emitir_transferencia=transferencias.append,
                    emitir_comprobante=comprobantes.append,
                )
                # Persistencia cronológica dentro del mes.
                insertar_lote_ingresos(cur, ingresos)
                insertar_lote_transferencias(cur, transferencias)
                insertar_lote_comprobantes(cur, comprobantes)
                totales.update(resultado)
                print(
                    f"{periodo['anio']}-{periodo['mes']:02d}: "
                    f"I={len(ingresos)} T={len(transferencias)} "
                    f"V={len(comprobantes)}"
                )
            validar_estado(cur, inicial, totales, inventario, stock_inicial)
            if confirmar:
                assert totales["ingresos"] == config.ingresos
                assert totales["transferencias"] == config.transferencias
                assert totales["comprobantes"] == config.comprobantes
                assert totales["renglones_ingreso"] > 10000
                assert totales["renglones_transferencia"] > 10000
                assert totales["renglones_venta"] == config.comprobantes * 4
            print("\nIntegridad, cantidades y existencias: CORRECTAS")
            for c in CLAVES_CANTIDAD:
                print(f"{c}: {totales[c]}")
            print(f"Tiempo de generación y persistencia: {perf_counter()-inicio:.2f} s")
            if confirmar:
                conn.commit()
                print("COMMIT: carga definitiva conservada.")
            else:
                conn.rollback()
                print("ROLLBACK: prueba revertida.")
    finally:
        try:
            if not conn.closed:
                conn.rollback()
        finally:
            conn.close()


def main():
    p = argparse.ArgumentParser(description="Carga transaccional H3 — Bodegas del Atuel")
    modo = p.add_mutually_exclusive_group(required=True)
    modo.add_argument("--verificar", action="store_true", help="Comprobar RN-08/RN-09; rollback")
    modo.add_argument("--probar", action="store_true", help="Carga reversible (rollback)")
    modo.add_argument("--cargar", action="store_true", help="Carga definitiva con validaciones")
    p.add_argument("--meses", type=int, default=1, help="1 a 58 para --probar")
    p.add_argument("--confirmo-carga-definitiva", action="store_true")
    args = p.parse_args()
    if args.verificar:
        conn = conectar()
        try:
            correcto, detalle = verificar_reglas_ventas(conn)
            print(detalle)
            print("Estado:", "LISTO" if correcto else "PENDIENTE RN-08/RN-09")
        finally:
            conn.close()
        return
    if args.cargar and not args.confirmo_carga_definitiva:
        p.error("Para --cargar se requiere --confirmo-carga-definitiva")
    if args.probar and args.confirmo_carga_definitiva:
        p.error("No combinar --probar con confirmación definitiva")
    cargar(58 if args.cargar else args.meses, confirmar=args.cargar)


if __name__ == "__main__":
    main()
