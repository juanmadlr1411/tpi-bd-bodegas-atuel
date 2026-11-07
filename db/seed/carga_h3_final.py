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

from conexion import conectar
from datos_maestros import obtener_datos_maestros
from inventario_historico import InventarioHistorico
from plan_carga import ConfiguracionCarga, planificar_carga
from simular_carga_58_meses import simular_mes
from persistencia_transaccional import insertar_lote_ingresos, insertar_lote_transferencias
from persistencia_transaccional import consultar_estado, consultar_stock_detallado


FECHA_PRUEBA = date(2026, 10, 20)
CLAVES_CANTIDAD = ("ingresos", "renglones_ingreso", "transferencias",
                   "renglones_transferencia", "comprobantes", "renglones_venta")


def verificar_reglas_ventas(conn):
    """Prueba RN-08, RN-09 y descuento en una transaccion reversible.

    Funciona tambien en una base limpia: crea stock temporal y lo revierte.
    """
    from decimal import Decimal, ROUND_HALF_UP

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.id_sala, v.cod_vino, v.precio
                  FROM sala_venta s CROSS JOIN vino v
                 WHERE v.anada <= %s
                 ORDER BY s.id_sala, v.cod_vino
                 LIMIT 1
            """, (FECHA_PRUEBA.year,))
            item = cur.fetchone()
            if item is None:
                return False, "Faltan salas o vinos para comprobar las ventas."
            sala, vino, precio = item

            cur.execute("""
                SELECT id_cliente, porcentaje_descuento
                  FROM cliente
                 WHERE fecha_alta <= %s AND porcentaje_descuento > 0
                 ORDER BY id_cliente LIMIT 1
            """, (FECHA_PRUEBA,))
            cliente_fila = cur.fetchone()
            if cliente_fila is None:
                return False, "No hay clientes con descuento para verificar RN-08."
            cliente, descuento = cliente_fila

            # Inventario provisional, siempre revertido al salir.
            cur.execute("""
                INSERT INTO stock_sala (id_sala, cod_vino, cantidad)
                VALUES (%s, %s, 5)
                ON CONFLICT (id_sala, cod_vino)
                DO UPDATE SET cantidad = stock_sala.cantidad + 5
                RETURNING cantidad
            """, (sala, vino))
            stock_antes = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO comprobante (fecha, id_cliente, id_sala)
                VALUES (%s, %s, %s) RETURNING nro_comprobante
            """, (FECHA_PRUEBA, cliente, sala))
            nro = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO renglon_comprobante
                    (nro_comprobante, cod_vino, cantidad, precio_unitario,
                     descuento, subtotal)
                VALUES (%s, %s, 1, %s, %s, %s)
            """, (nro, vino, precio, descuento, precio))

            cur.execute("""
                SELECT total, fn_total_comprobante(%s)
                  FROM comprobante
                 WHERE nro_comprobante = %s
            """, (nro, nro))
            total_cabecera, total_funcion = cur.fetchone()
            cur.execute("""
                SELECT cantidad FROM stock_sala
                 WHERE id_sala = %s AND cod_vino = %s
            """, (sala, vino))
            stock_despues = cur.fetchone()[0]
            cur.execute("""
                SELECT descuento, subtotal FROM renglon_comprobante
                 WHERE nro_comprobante = %s AND cod_vino = %s
            """, (nro, vino))
            descuento_guardado, subtotal_guardado = cur.fetchone()

            esperado = (precio * (
                Decimal('1') - descuento / Decimal('100')
            )).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            rn08 = (
                total_cabecera == total_funcion == esperado
                and subtotal_guardado == esperado
                and descuento_guardado == descuento
            )
            rn09 = stock_despues == stock_antes - 1
            mensaje = (
                f"RN-08: {'OK' if rn08 else 'PENDIENTE'} "
                f"(cabecera={total_cabecera}, funcion={total_funcion}, "
                f"esperado={esperado}, descuento={descuento}%) | "
                f"RN-09: {'OK' if rn09 else 'PENDIENTE'} "
                f"(stock {stock_antes} -> {stock_despues})"
            )
            return rn08 and rn09, mensaje
    finally:
        conn.rollback()  # NUNCA conserva cambios de este chequeo.


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
    # No basta con totales correctos: cada venta debe aplicar el
    # descuento del cliente y el importe calculado por RN-08.
    cur.execute("""
        SELECT COUNT(*)
          FROM renglon_comprobante r
          JOIN comprobante c USING (nro_comprobante)
          JOIN cliente cl ON cl.id_cliente = c.id_cliente
         WHERE r.descuento IS DISTINCT FROM cl.porcentaje_descuento
    """)
    assert cur.fetchone()[0] == 0, "Ventas con descuento incorrecto"
    cur.execute("""
        SELECT COUNT(*) FROM comprobante c
         WHERE c.total IS DISTINCT FROM fn_total_comprobante(c.nro_comprobante)
    """)
    assert cur.fetchone()[0] == 0, "Totales de ventas incorrectos"
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
            requeridos = {
                "trg_actualizar_totales_comprobante",
                "trg_validar_stock_venta",
                "trg_actualizar_stock_venta",
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
                raise RuntimeError(
                    "Triggers H2 desactivados o ausentes: "
                    + ", ".join(sorted(faltantes))
                    + ". Ejecutar la restauracion post-carga de maestros."
                )

            # Excepcion controlada SOLO para el seed historico H3.
            # PostgreSQL revierte el ALTER TABLE si la transaccion falla.
            cur.execute("""
                ALTER TABLE transferencia
                DISABLE TRIGGER trg_fecha_confeccion_transferencia
            """)
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
                # Verificar que RN-11 no reemplace la fecha historica.
                fecha_historica = date(periodo["anio"], periodo["mes"], 15)
                cur.execute(
                    "SELECT COUNT(*) FROM transferencia WHERE fecha_confeccion = %s",
                    (fecha_historica,),
                )
                anteriores_en_fecha = cur.fetchone()[0]
                insertar_lote_transferencias(cur, transferencias)
                cur.execute(
                    "SELECT COUNT(*) FROM transferencia WHERE fecha_confeccion = %s",
                    (fecha_historica,),
                )
                assert cur.fetchone()[0] - anteriores_en_fecha == len(transferencias), (
                    "Las fechas historicas de transferencia no se conservaron"
                )
                insertar_lote_comprobantes(cur, comprobantes)
                totales.update(resultado)
                print(
                    f"{periodo['anio']}-{periodo['mes']:02d}: "
                    f"I={len(ingresos)} T={len(transferencias)} "
                    f"V={len(comprobantes)}"
                )
            validar_estado(cur, inicial, totales, inventario, stock_inicial)
            # Reactivar ANTES del COMMIT; la regla RN11 sigue vigente
            # para las operaciones normales posteriores a la carga.
            cur.execute("""
                ALTER TABLE transferencia
                ENABLE TRIGGER trg_fecha_confeccion_transferencia
            """)
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
