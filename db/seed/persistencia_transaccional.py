import random

from carga_transaccional import conectar
from datos_maestros import obtener_datos_maestros
from inventario_historico import InventarioHistorico
from plan_carga import ConfiguracionCarga, planificar_carga
from simular_carga_58_meses import simular_mes
from collections import Counter


def insertar_ingreso(cur, documento):
    """Inserta y procesa un ingreso completo."""

    cur.execute("""
        INSERT INTO ingreso (
            fecha, cod_transporte, cuit_bodega
        )
        VALUES (%s, %s, %s)
        RETURNING cod_ingreso
    """, (
        documento["fecha"],
        documento["cod_transporte"],
        documento["cuit_bodega"]
    ))

    cod_ingreso = cur.fetchone()[0]

    renglones = [
        (
            cod_ingreso,
            renglon["cod_vino"],
            renglon["cantidad"]
        )
        for renglon in documento["renglones"]
    ]

    cur.executemany("""
        INSERT INTO renglon_ingreso (
            cod_ingreso, cod_vino, cantidad
        )
        VALUES (%s, %s, %s)
    """, renglones)

    cur.execute("""
        UPDATE ingreso
        SET estado = 'terminado'
        WHERE cod_ingreso = %s
    """, (cod_ingreso,))

    cur.execute(
        "CALL sp_procesar_ingreso(%s)",
        (cod_ingreso,)
    )

    return cod_ingreso


def insertar_transferencia(cur, documento):
    """Inserta y procesa una transferencia completa."""

    cur.execute("""
        INSERT INTO transferencia (
            fecha_confeccion, id_sala
        )
        VALUES (%s, %s)
        RETURNING nro_transferencia
    """, (
        documento["fecha_confeccion"],
        documento["id_sala"]
    ))

    nro_transferencia = cur.fetchone()[0]

    renglones = [
        (
            nro_transferencia,
            renglon["cod_vino"],
            renglon["cantidad"]
        )
        for renglon in documento["renglones"]
    ]

    cur.executemany("""
        INSERT INTO renglon_transferencia (
            nro_transferencia, cod_vino, cantidad
        )
        VALUES (%s, %s, %s)
    """, renglones)

    cur.execute("""
        UPDATE transferencia
        SET estado = 'terminado'
        WHERE nro_transferencia = %s
    """, (nro_transferencia,))

    cur.execute(
        "CALL sp_procesar_transferencia(%s)",
        (nro_transferencia,)
    )

    return nro_transferencia


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

def main():

    config = ConfiguracionCarga()

    # Probar solamente enero de 2022.
    periodo = planificar_carga(config)[0]

    rng = random.Random(config.semilla)
    inventario = InventarioHistorico()

    # Obtener los datos maestros.
    with conectar() as conn:
        datos = obtener_datos_maestros(conn)

    print("PRUEBA TRANSACCIONAL DE PERSISTENCIA")
    print("-" * 55)

    conn = conectar()

    try:
        # Evitar escrituras permanentes por una configuración inesperada.
        if conn.autocommit:
            raise RuntimeError(
                "La conexión tiene autocommit activado."
            )

        with conn.cursor() as cur:

            estado_inicial = consultar_estado(cur)
            deposito_inicial, salas_inicial = consultar_stock_detallado(
                cur
            )

            ventas_simuladas = Counter()

            def registrar_venta(documento):
                for renglon in documento["renglones"]:
                    clave = (
                        documento["id_sala"],
                        renglon["cod_vino"]
                    )

                    ventas_simuladas[clave] += renglon["cantidad"]

            # Cada documento generado se inserta inmediatamente.
            resultado = simular_mes(
                periodo,
                datos,
                inventario,
                rng,
                emitir_ingreso=lambda documento: insertar_ingreso(
                    cur, documento
                ),
                emitir_transferencia=lambda documento: insertar_transferencia(
                    cur, documento
                ),
                emitir_comprobante=registrar_venta
            )

            estado_final = consultar_estado(cur)
            deposito_final, salas_final = consultar_stock_detallado(
                cur
            )
            print("\nREGISTROS INSERTADOS EN LA TRANSACCIÓN")
            print("-" * 55)

            for clave in (
                "ingresos",
                "renglones_ingreso",
                "transferencias",
                "renglones_transferencia"
            ):
                diferencia = (
                    estado_final[clave] - estado_inicial[clave]
                )

                assert diferencia == resultado[clave]

                print(f"{clave}: {diferencia}")

            print("\nCONTROL DE INVENTARIO")
            print("-" * 55)

            diferencia_deposito = (
                estado_final["deposito"]
                - estado_inicial["deposito"]
            )

            diferencia_salas = (
                estado_final["salas"]
                - estado_inicial["salas"]
            )

            esperado_deposito = (
                resultado["botellas_ingresadas"]
                - resultado["botellas_transferidas"]
            )

            esperado_salas = resultado["botellas_transferidas"]

            assert diferencia_deposito == esperado_deposito
            assert diferencia_salas == esperado_salas

            print(f"Variación depósito: {diferencia_deposito}")
            print(f"Variación salas: {diferencia_salas}")
            print("\nCONCILIACIÓN DETALLADA DEL INVENTARIO")
            print("-" * 55)

            # Verificar que se capturaron todas las ventas simuladas.
            assert sum(ventas_simuladas.values()) == (
                resultado["botellas_vendidas"]
            )

            # Comparar el depósito vino por vino.
            vinos = (
                set(deposito_inicial)
                | set(deposito_final)
                | set(inventario.deposito)
            )

            for cod_vino in vinos:

                variacion_sql = (
                    deposito_final.get(cod_vino, 0)
                    - deposito_inicial.get(cod_vino, 0)
                )

                variacion_python = inventario.deposito.get(
                    cod_vino, 0
                )

                assert variacion_sql == variacion_python, (
                    f"Diferencia en depósito, vino {cod_vino}: "
                    f"SQL={variacion_sql}, "
                    f"Python={variacion_python}"
                )

            print(f"Vinos verificados en depósito: {len(vinos)}")

            # Comparar las existencias por sala y vino.
            claves_sala = (
                set(salas_inicial)
                | set(salas_final)
                | set(inventario.salas)
                | set(ventas_simuladas)
            )

            for clave in claves_sala:

                variacion_sql = (
                    salas_final.get(clave, 0)
                    - salas_inicial.get(clave, 0)
                )

                # Python descontó las ventas simuladas.
                # PostgreSQL todavía no lo hizo.
                variacion_esperada = (
                    inventario.salas.get(clave, 0)
                    + ventas_simuladas.get(clave, 0)
                )

                assert variacion_sql == variacion_esperada, (
                    f"Diferencia en sala/vino {clave}: "
                    f"SQL={variacion_sql}, "
                    f"Esperado={variacion_esperada}"
                )

            print(
                f"Combinaciones sala-vino verificadas: "
                f"{len(claves_sala)}"
            )

            print("Conciliación detallada: CORRECTA")
            print("\nValidaciones SQL: CORRECTAS")

    finally:
        try:
            # Nunca conservar los registros de esta prueba.
            conn.rollback()
            print("\nROLLBACK ejecutado.")
            print("Las inserciones de prueba fueron revertidas.")
        finally:
            conn.close()


if __name__ == "__main__":
    main()