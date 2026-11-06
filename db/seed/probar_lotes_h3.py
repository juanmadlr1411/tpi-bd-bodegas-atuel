import random
from collections import Counter
from time import perf_counter

from carga_transaccional import conectar
from datos_maestros import obtener_datos_maestros
from inventario_historico import InventarioHistorico
from plan_carga import ConfiguracionCarga, planificar_carga
from simular_carga_58_meses import simular_mes

from persistencia_transaccional import (
    insertar_ingreso,
    insertar_transferencia,
    consultar_estado,
    consultar_stock_detallado,
)


MESES_PRUEBA = 3


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


def ejecutar_prueba(modo, plan, datos, semilla):

    rng = random.Random(semilla)
    inventario = InventarioHistorico()

    totales = Counter()
    ventas_simuladas = Counter()

    conn = conectar()

    try:
        if conn.autocommit:
            raise RuntimeError("Autocommit debe estar desactivado.")

        with conn.cursor() as cur:

            estado_inicial = consultar_estado(cur)

            deposito_inicial, salas_inicial = (
                consultar_stock_detallado(cur)
            )

            def registrar_venta(documento):

                for renglon in documento["renglones"]:
                    clave = (
                        documento["id_sala"],
                        renglon["cod_vino"]
                    )

                    ventas_simuladas[clave] += renglon["cantidad"]

            inicio = perf_counter()

            for periodo in plan:

                if modo == "individual":

                    resultado = simular_mes(
                        periodo,
                        datos,
                        inventario,
                        rng,
                        emitir_ingreso=lambda doc: insertar_ingreso(
                            cur, doc
                        ),
                        emitir_transferencia=lambda doc: insertar_transferencia(
                            cur, doc
                        ),
                        emitir_comprobante=registrar_venta
                    )

                elif modo == "lotes":

                    ingresos = []
                    transferencias = []

                    # Generar documentos del mes en memoria.
                    resultado = simular_mes(
                        periodo,
                        datos,
                        inventario,
                        rng,
                        emitir_ingreso=ingresos.append,
                        emitir_transferencia=transferencias.append,
                        emitir_comprobante=registrar_venta
                    )

                    # Persistir ingresos ANTES de transferencias.
                    insertar_lote_ingresos(cur, ingresos)

                    insertar_lote_transferencias(
                        cur, transferencias
                    )

                else:
                    raise ValueError(f"Modo desconocido: {modo}")

                totales.update(resultado)

            duracion = perf_counter() - inicio

            estado_final = consultar_estado(cur)

            # Validar los registros insertados.
            for clave in (
                "ingresos",
                "renglones_ingreso",
                "transferencias",
                "renglones_transferencia"
            ):

                diferencia = (
                    estado_final[clave]
                    - estado_inicial[clave]
                )

                assert diferencia == totales[clave], (
                    f"Cantidad incorrecta en {clave}"
                )

            # Conciliación detallada del inventario.
            deposito_final, salas_final = (
                consultar_stock_detallado(cur)
            )

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

                assert variacion_sql == (
                    inventario.deposito.get(cod_vino, 0)
                ), f"Diferencia en depósito para vino {cod_vino}"

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

                esperado = (
                    inventario.salas.get(clave, 0)
                    + ventas_simuladas.get(clave, 0)
                )

                assert variacion_sql == esperado, (
                    f"Diferencia en sala/vino {clave}"
                )

            assert sum(ventas_simuladas.values()) == (
                totales["botellas_vendidas"]
            )

            documentos_sql = (
                totales["ingresos"]
                + totales["transferencias"]
            )

            velocidad = documentos_sql / duracion

            return {
                "modo": modo,
                "duracion": duracion,
                "velocidad": velocidad,
                "documentos": documentos_sql,
                "registros": sum(
                    totales[clave]
                    for clave in (
                        "ingresos",
                        "renglones_ingreso",
                        "transferencias",
                        "renglones_transferencia"
                    )
                )
            }

    finally:
        try:
            conn.rollback()
            print(f"ROLLBACK ejecutado: {modo}")
        finally:
            conn.close()


def main():

    config = ConfiguracionCarga()

    # Tres meses para evitar una prueba demasiado grande.
    plan = planificar_carga(config)[:MESES_PRUEBA]

    with conectar() as conn:
        datos = obtener_datos_maestros(conn)

    print("COMPARACIÓN DE ESTRATEGIAS DE PERSISTENCIA")
    print("-" * 60)

    resultados = []

    for modo in ("individual", "lotes"):

        print(f"\nEjecutando estrategia: {modo}")

        resultado = ejecutar_prueba(
            modo,
            plan,
            datos,
            config.semilla
        )

        resultados.append(resultado)

        print(f"Documentos: {resultado['documentos']}")
        print(f"Registros SQL: {resultado['registros']}")
        print(f"Tiempo: {resultado['duracion']:.3f} s")
        print(f"Velocidad: {resultado['velocidad']:.2f} doc/s")
        print("Integridad: CORRECTA")

    individual, lotes = resultados

    mejora = (
        (individual["duracion"] - lotes["duracion"])
        / individual["duracion"]
        * 100
    )

    print("\nRESULTADO COMPARATIVO")
    print("-" * 60)

    print(f"Individual: {individual['duracion']:.3f} s")
    print(f"Por lotes: {lotes['duracion']:.3f} s")
    print(f"Mejora temporal: {mejora:.2f}%")

    if mejora > 0:
        print("La estrategia por lotes fue más rápida.")
    else:
        print("La estrategia por lotes no mejoró el tiempo.")

    print("\nAMBAS ESTRATEGIAS VALIDADAS")
    print("No se conservaron cambios en PostgreSQL.")


if __name__ == "__main__":
    main()