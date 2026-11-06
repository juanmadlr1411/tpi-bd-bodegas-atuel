import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

import random
from datetime import date, timedelta

from decimal import Decimal, ROUND_HALF_UP

# 1. Cargar la configuración del proyecto
RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ_PROYECTO / ".env")


# 2. Establecer la conexión con PostgreSQL
def conectar():
    return psycopg.connect(
        host="127.0.0.1",
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    )


# 3. Consultar datos maestros existentes
def consultar_datos_maestros(conn):
    tablas = [
        "cliente",
        "vino",
        "bodega",
        "sala_venta",
        "transportista",
    ]

    with conn.cursor() as cursor:
        for tabla in tablas:
            cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
            cantidad = cursor.fetchone()[0]
            print(f"{tabla}: {cantidad} registros")


def probar_ingreso(conn):
    """
    Prueba un ingreso de 25 botellas al depósito central.
    Al finalizar, revierte los cambios para no alterar
    los datos de desarrollo.
    """
    with conn.cursor() as cursor:

        # Buscar un vino y su bodega
        cursor.execute("""
            SELECT cod_vino, cuit_bodega
            FROM vino
            ORDER BY cod_vino
            LIMIT 1
        """)
        cod_vino, cuit_bodega = cursor.fetchone()

        # Buscar un transportista
        cursor.execute("""
            SELECT cod_transporte
            FROM transportista
            ORDER BY cod_transporte
            LIMIT 1
        """)
        cod_transporte = cursor.fetchone()[0]

        # Crear la cabecera del ingreso
        cursor.execute("""
            INSERT INTO ingreso
                (fecha, estado, cod_transporte, cuit_bodega)
            VALUES
                (%s, 'en_confeccion', %s, %s)
            RETURNING cod_ingreso
        """, ("2025-06-15", cod_transporte, cuit_bodega))

        cod_ingreso = cursor.fetchone()[0]

        # Agregar 25 botellas al documento
        cursor.execute("""
            INSERT INTO renglon_ingreso
                (cod_ingreso, cod_vino, cantidad)
            VALUES (%s, %s, %s)
        """, (cod_ingreso, cod_vino, 25))

        # Finalizar el documento
        cursor.execute("""
            UPDATE ingreso
            SET estado = 'terminado'
            WHERE cod_ingreso = %s
        """, (cod_ingreso,))

        # Procesar el ingreso mediante el procedimiento de H2
        cursor.execute(
            "CALL sp_procesar_ingreso(%s)",
            (cod_ingreso,)
        )

        # Comprobar el resultado
        cursor.execute("""
            SELECT cantidad
            FROM stock_deposito
            WHERE cod_vino = %s
        """, (cod_vino,))

        stock = cursor.fetchone()[0]

        print(f"Ingreso de prueba: {cod_ingreso}")
        print(f"Vino: {cod_vino}")
        print(f"Stock observado: {stock} botellas")

    # Deshacer toda la operación de prueba
    conn.rollback()
    print("Prueba revertida: la base no conserva estos cambios.")

def generar_ingresos(conn, cantidad=10):
    """
    Genera ingresos históricos con sus renglones y actualiza
    el stock mediante el procedimiento sp_procesar_ingreso().
    """

    # Semilla fija para repetir los mismos valores aleatorios.
    rng = random.Random(2026)

    with conn.cursor() as cursor:

        # Evitar generar ingresos duplicados accidentalmente.
        cursor.execute("SELECT COUNT(*) FROM ingreso")
        if cursor.fetchone()[0] != 0:
            raise RuntimeError(
                "Ya existen ingresos. Se cancela la carga para evitar duplicados."
            )

        # Obtener los vinos y sus bodegas.
        cursor.execute("""
            SELECT cod_vino, cuit_bodega
            FROM vino
            ORDER BY cod_vino
        """)

        vinos_por_bodega = {}

        for cod_vino, cuit_bodega in cursor.fetchall():
            vinos_por_bodega.setdefault(cuit_bodega, []).append(cod_vino)

        # Obtener transportistas existentes.
        cursor.execute("""
            SELECT cod_transporte
            FROM transportista
            ORDER BY cod_transporte
        """)

        transportistas = [fila[0] for fila in cursor.fetchall()]
        bodegas = sorted(vinos_por_bodega)

        if not bodegas or not transportistas:
            raise RuntimeError("Faltan vinos, bodegas o transportistas.")

        # Período histórico de generación.
        fecha_inicio = date(2022, 1, 1)
        fecha_fin = date(2026, 10, 31)
        dias = (fecha_fin - fecha_inicio).days

        print(f"\nGenerando {cantidad} ingresos históricos...")

        for _ in range(cantidad):

            # Seleccionar una bodega y un transportista.
            cuit_bodega = rng.choice(bodegas)
            cod_transporte = rng.choice(transportistas)

            # Generar una fecha histórica.
            fecha = fecha_inicio + timedelta(
                days=rng.randint(0, dias)
            )

            # Crear la cabecera del ingreso.
            cursor.execute("""
                INSERT INTO ingreso
                    (fecha, estado, cod_transporte, cuit_bodega)
                VALUES (%s, 'en_confeccion', %s, %s)
                RETURNING cod_ingreso
            """, (fecha, cod_transporte, cuit_bodega))

            cod_ingreso = cursor.fetchone()[0]

            # Seleccionar entre 1 y 3 vinos distintos de esa bodega.
            vinos_disponibles = vinos_por_bodega[cuit_bodega]

            cantidad_renglones = rng.randint(
                1, min(3, len(vinos_disponibles))
            )

            vinos_elegidos = rng.sample(
                vinos_disponibles,
                cantidad_renglones
            )

            # Insertar los renglones.
            for cod_vino in vinos_elegidos:

                cantidad_botellas = rng.randint(20, 100)

                cursor.execute("""
                    INSERT INTO renglon_ingreso
                        (cod_ingreso, cod_vino, cantidad)
                    VALUES (%s, %s, %s)
                """, (
                    cod_ingreso,
                    cod_vino,
                    cantidad_botellas
                ))

            # Finalizar el documento.
            cursor.execute("""
                UPDATE ingreso
                SET estado = 'terminado'
                WHERE cod_ingreso = %s
            """, (cod_ingreso,))

            # Procesar el ingreso y actualizar el depósito.
            cursor.execute(
                "CALL sp_procesar_ingreso(%s)",
                (cod_ingreso,)
            )

        print(f"Se generaron {cantidad} ingresos correctamente.")

def probar_transferencia(conn):
    """
    Prueba una transferencia de 10 botellas desde el depósito
    hacia una sala de venta, sin conservar los cambios.
    """

    with conn.cursor() as cursor:

        # 1. Seleccionar una sala de venta.
        cursor.execute("""
            SELECT id_sala
            FROM sala_venta
            ORDER BY id_sala
            LIMIT 1
        """)
        id_sala = cursor.fetchone()[0]

        # 2. Seleccionar un vino con stock suficiente.
        cursor.execute("""
            SELECT cod_vino, cantidad
            FROM stock_deposito
            WHERE cantidad >= 10
            ORDER BY cod_vino
            LIMIT 1
        """)

        resultado = cursor.fetchone()

        if resultado is None:
            raise RuntimeError("No existe un vino con stock suficiente.")

        cod_vino, stock_inicial = resultado

        # 3. Crear la cabecera de la transferencia.
        cursor.execute("""
            INSERT INTO transferencia
                (id_sala, fecha_confeccion, estado)
            VALUES (%s, CURRENT_DATE, 'en_confeccion')
            RETURNING nro_transferencia
        """, (id_sala,))

        nro_transferencia = cursor.fetchone()[0]

        # 4. Registrar el detalle.
        cursor.execute("""
            INSERT INTO renglon_transferencia
                (nro_transferencia, cod_vino, cantidad)
            VALUES (%s, %s, %s)
        """, (nro_transferencia, cod_vino, 10))

        # 5. Finalizar el documento.
        cursor.execute("""
            UPDATE transferencia
            SET estado = 'terminado'
            WHERE nro_transferencia = %s
        """, (nro_transferencia,))

        # 6. Procesar la transferencia mediante H2.
        cursor.execute(
            "CALL sp_procesar_transferencia(%s)",
            (nro_transferencia,)
        )

        # 7. Consultar el stock del depósito.
        cursor.execute("""
            SELECT cantidad
            FROM stock_deposito
            WHERE cod_vino = %s
        """, (cod_vino,))

        stock_final = cursor.fetchone()[0]

        # 8. Consultar el stock de la sala.
        cursor.execute("""
            SELECT cantidad
            FROM stock_sala
            WHERE id_sala = %s AND cod_vino = %s
        """, (id_sala, cod_vino))

        stock_sala = cursor.fetchone()[0]

        print(f"\nTransferencia de prueba: {nro_transferencia}")
        print(f"Sala de venta: {id_sala}")
        print(f"Vino: {cod_vino}")
        print(f"Stock inicial del depósito: {stock_inicial}")
        print(f"Stock final del depósito: {stock_final}")
        print(f"Stock de la sala: {stock_sala}")

        assert stock_final == stock_inicial - 10

    # Revertir la transferencia de prueba.
    conn.rollback()
    print("Transferencia revertida correctamente.")

def generar_transferencias(conn, cantidad=5):
    """
    Genera transferencias desde el depósito central
    hacia las salas de venta.
    """

    rng = random.Random(2026)

    with conn.cursor() as cursor:

        # 1. Evitar cargas duplicadas.
        cursor.execute("SELECT COUNT(*) FROM transferencia")

        if cursor.fetchone()[0] != 0:
            raise RuntimeError(
                "Ya existen transferencias. Se cancela la generación."
            )

        # 2. Obtener las salas disponibles.
        cursor.execute("""
            SELECT id_sala
            FROM sala_venta
            ORDER BY id_sala
        """)

        salas = [fila[0] for fila in cursor.fetchall()]

        if not salas:
            raise RuntimeError("No existen salas de venta.")

        # 3. Obtener la fecha del último ingreso.
        cursor.execute("""
            SELECT MAX(fecha)
            FROM ingreso
        """)

        ultima_fecha = cursor.fetchone()[0]

        if ultima_fecha is None:
            raise RuntimeError("No existen ingresos registrados.")

        fecha_transferencia = ultima_fecha + timedelta(days=1)

        if fecha_transferencia > date.today():
            raise RuntimeError(
                "La fecha calculada está en el futuro."
            )

        # 4. Registrar el stock total antes de transferir.
        cursor.execute("""
            SELECT
                COALESCE((SELECT SUM(cantidad) FROM stock_deposito), 0)
                +
                COALESCE((SELECT SUM(cantidad) FROM stock_sala), 0)
        """)

        stock_total_inicial = cursor.fetchone()[0]

        print(f"\nGenerando {cantidad} transferencias...")

        # 5. Crear las transferencias.
        for _ in range(cantidad):

            id_sala = rng.choice(salas)

            # Consultar el stock actualizado del depósito.
            cursor.execute("""
                SELECT cod_vino, cantidad
                FROM stock_deposito
                WHERE cantidad >= 5
                ORDER BY cod_vino
            """)

            vinos_disponibles = cursor.fetchall()

            if not vinos_disponibles:
                raise RuntimeError(
                    "No hay suficiente stock para generar transferencias."
                )

            # Seleccionar entre uno y dos vinos diferentes.
            cantidad_renglones = rng.randint(
                1, min(2, len(vinos_disponibles))
            )

            vinos_elegidos = rng.sample(
                vinos_disponibles,
                cantidad_renglones
            )

            # Crear cabecera.
            cursor.execute("""
                INSERT INTO transferencia
                    (id_sala, fecha_confeccion, estado)
                VALUES (%s, %s, 'en_confeccion')
                RETURNING nro_transferencia
            """, (id_sala, fecha_transferencia))

            nro_transferencia = cursor.fetchone()[0]

            # Crear renglones.
            for cod_vino, stock_disponible in vinos_elegidos:

                cantidad_botellas = rng.randint(
                    5, min(25, stock_disponible)
                )

                cursor.execute("""
                    INSERT INTO renglon_transferencia
                        (nro_transferencia, cod_vino, cantidad)
                    VALUES (%s, %s, %s)
                """, (
                    nro_transferencia,
                    cod_vino,
                    cantidad_botellas
                ))

            # Finalizar transferencia.
            cursor.execute("""
                UPDATE transferencia
                SET estado = 'terminado'
                WHERE nro_transferencia = %s
            """, (nro_transferencia,))

            # Procesar mediante el procedimiento de H2.
            cursor.execute(
                "CALL sp_procesar_transferencia(%s)",
                (nro_transferencia,)
            )

        # 6. Comprobar que se conserve el stock total.
        cursor.execute("""
            SELECT
                COALESCE((SELECT SUM(cantidad) FROM stock_deposito), 0)
                +
                COALESCE((SELECT SUM(cantidad) FROM stock_sala), 0)
        """)

        stock_total_final = cursor.fetchone()[0]

        if stock_total_final != stock_total_inicial:
            raise RuntimeError(
                "Error: la cantidad total de botellas cambió."
            )

        print(f"Transferencias generadas: {cantidad}")
        print(f"Stock total inicial: {stock_total_inicial}")
        print(f"Stock total final: {stock_total_final}")
        print("Integridad de existencias verificada.")

def probar_venta(conn):
    """
    Prueba una venta de una botella.
    Valida los importes y revierte todos los cambios.
    """

    try:
        with conn.cursor() as cursor:

            # 1. Buscar una sala que tenga botellas disponibles.
            cursor.execute("""
                SELECT s.id_sala, s.cod_vino, s.cantidad, v.precio
                FROM stock_sala s
                JOIN vino v ON s.cod_vino = v.cod_vino
                WHERE s.cantidad > 0
                ORDER BY s.id_sala, s.cod_vino
                LIMIT 1
            """)

            resultado = cursor.fetchone()

            if resultado is None:
                raise RuntimeError("No hay vinos disponibles en las salas.")

            id_sala, cod_vino, stock_inicial, precio = resultado

            # 2. Seleccionar un cliente y su descuento.
            cursor.execute("""
                SELECT id_cliente, porcentaje_descuento
                FROM cliente
                WHERE fecha_alta <= CURRENT_DATE
                ORDER BY id_cliente
                LIMIT 1
            """)

            id_cliente, porcentaje_descuento = cursor.fetchone()

            # 3. Crear la cabecera del comprobante.
            cursor.execute("""
                INSERT INTO comprobante (fecha, id_cliente, id_sala)
                VALUES (CURRENT_DATE, %s, %s)
                RETURNING nro_comprobante
            """, (id_cliente, id_sala))

            nro_comprobante = cursor.fetchone()[0]

            # 4. Registrar la venta de una botella.
            cursor.execute("""
                INSERT INTO renglon_comprobante
                    (nro_comprobante, cod_vino, cantidad,
                     precio_unitario, descuento, subtotal)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                nro_comprobante,
                cod_vino,
                1,
                precio,
                Decimal("0.00"),
                precio
            ))

            # 5. Consultar los importes calculados por el trigger.
            cursor.execute("""
                SELECT subtotal, descuento, total
                FROM comprobante
                WHERE nro_comprobante = %s
            """, (nro_comprobante,))

            subtotal, descuento, total = cursor.fetchone()

            # 6. Calcular el resultado esperado.
            descuento_esperado = (
                precio * porcentaje_descuento / Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            total_esperado = precio - descuento_esperado

            if (
                subtotal != precio
                or descuento != descuento_esperado
                or total != total_esperado
            ):
                raise RuntimeError(
                    "Los importes del comprobante no coinciden."
                )

            # 7. Comprobar el stock después de registrar la venta.
            cursor.execute("""
                SELECT cantidad
                FROM stock_sala
                WHERE id_sala = %s AND cod_vino = %s
            """, (id_sala, cod_vino))

            stock_final = cursor.fetchone()[0]

            print(f"\nComprobante de prueba: {nro_comprobante}")
            print(f"Cliente: {id_cliente}")
            print(f"Sala: {id_sala}")
            print(f"Vino: {cod_vino}")
            print(f"Subtotal: ${subtotal}")
            print(f"Descuento: ${descuento}")
            print(f"Total: ${total}")
            print("Cálculo de importes: correcto")
            print(f"Stock inicial: {stock_inicial}")
            print(f"Stock después de insertar la venta: {stock_final}")

    finally:
        # La prueba nunca debe conservar datos.
        conn.rollback()
        print("Prueba de venta revertida.")

def planificar_ventas(conn, cantidad=10):
    """
    Genera un plan de ventas en memoria.

    No inserta comprobantes.
    No modifica el stock de PostgreSQL.
    """

    rng = random.Random(2026)

    with conn.cursor() as cursor:

        # 1. Obtener la fecha de la última transferencia.
        cursor.execute("""
            SELECT MAX(fecha_confeccion)
            FROM transferencia
            WHERE estado = 'procesado'
        """)

        ultima_fecha = cursor.fetchone()[0]

        if ultima_fecha is None:
            raise RuntimeError("No existen transferencias procesadas.")

        fecha_venta = ultima_fecha + timedelta(days=1)

        if fecha_venta > date.today():
            raise RuntimeError("La fecha de venta estaría en el futuro.")

        # 2. Obtener clientes existentes en esa fecha.
        cursor.execute("""
            SELECT id_cliente
            FROM cliente
            WHERE fecha_alta <= %s
            ORDER BY id_cliente
        """, (fecha_venta,))

        clientes = [fila[0] for fila in cursor.fetchall()]

        if not clientes:
            raise RuntimeError("No hay clientes válidos.")

        # 3. Consultar existencias en las salas.
        cursor.execute("""
            SELECT id_sala, cod_vino, cantidad
            FROM stock_sala
            WHERE cantidad > 0
            ORDER BY id_sala, cod_vino
        """)

        inventario = {}

        for id_sala, cod_vino, stock in cursor.fetchall():
            inventario.setdefault(id_sala, {})[cod_vino] = stock

    # 4. Generar ventas utilizando una copia en memoria.
    ventas = []

    for _ in range(cantidad):

        salas_disponibles = [
            sala
            for sala, vinos in inventario.items()
            if any(stock > 0 for stock in vinos.values())
        ]

        if not salas_disponibles:
            raise RuntimeError("Se agotó el stock disponible.")

        id_sala = rng.choice(salas_disponibles)
        id_cliente = rng.choice(clientes)

        vinos_disponibles = [
            cod_vino
            for cod_vino, stock in inventario[id_sala].items()
            if stock > 0
        ]

        cantidad_renglones = rng.randint(
            1, min(2, len(vinos_disponibles))
        )

        vinos_elegidos = rng.sample(
            vinos_disponibles,
            cantidad_renglones
        )

        renglones = []

        for cod_vino in vinos_elegidos:

            stock_actual = inventario[id_sala][cod_vino]

            botellas = rng.randint(
                1, min(3, stock_actual)
            )

            # Descontar únicamente del inventario en memoria.
            inventario[id_sala][cod_vino] -= botellas

            renglones.append((cod_vino, botellas))

        ventas.append({
            "fecha": fecha_venta,
            "cliente": id_cliente,
            "sala": id_sala,
            "renglones": renglones
        })

    print(f"\nVentas planificadas: {len(ventas)}")

    for numero, venta in enumerate(ventas, start=1):
        print(
            f"Venta {numero}: "
            f"fecha={venta['fecha']}, "
            f"cliente={venta['cliente']}, "
            f"sala={venta['sala']}, "
            f"renglones={venta['renglones']}"
        )

    print("\nNo se modificó ningún registro de PostgreSQL.")

    return ventas

def validar_plan_ventas(conn, ventas):
    """
    Comprueba la integridad del plan de ventas
    sin modificar PostgreSQL.
    """

    with conn.cursor() as cursor:

        # Obtener el inventario original de las salas.
        cursor.execute("""
            SELECT id_sala, cod_vino, cantidad
            FROM stock_sala
        """)

        inventario = {
            (id_sala, cod_vino): cantidad
            for id_sala, cod_vino, cantidad in cursor.fetchall()
        }

        # Obtener clientes y sus fechas de alta.
        cursor.execute("""
            SELECT id_cliente, fecha_alta
            FROM cliente
        """)

        clientes = dict(cursor.fetchall())

    total_renglones = 0
    total_botellas = 0

    for numero, venta in enumerate(ventas, start=1):

        id_cliente = venta["cliente"]
        id_sala = venta["sala"]
        fecha = venta["fecha"]

        # Validar existencia del cliente.
        if id_cliente not in clientes:
            raise RuntimeError(
                f"Venta {numero}: el cliente no existe."
            )

        # Validar que el cliente ya estuviera registrado.
        if clientes[id_cliente] > fecha:
            raise RuntimeError(
                f"Venta {numero}: cliente registrado después de la venta."
            )

        # Validar que la venta tenga renglones.
        if not venta["renglones"]:
            raise RuntimeError(
                f"Venta {numero}: no tiene renglones."
            )

        vinos_utilizados = set()

        for cod_vino, cantidad in venta["renglones"]:

            # Evitar vinos repetidos en un mismo comprobante.
            if cod_vino in vinos_utilizados:
                raise RuntimeError(
                    f"Venta {numero}: vino duplicado."
                )

            vinos_utilizados.add(cod_vino)

            if cantidad <= 0:
                raise RuntimeError(
                    f"Venta {numero}: cantidad inválida."
                )

            clave = (id_sala, cod_vino)

            stock_disponible = inventario.get(clave, 0)

            if cantidad > stock_disponible:
                raise RuntimeError(
                    f"Venta {numero}: stock insuficiente."
                )

            # Actualizar el inventario simulado.
            inventario[clave] -= cantidad

            total_renglones += 1
            total_botellas += cantidad

    print("\n--- VALIDACIÓN DEL PLAN ---")
    print(f"Ventas verificadas: {len(ventas)}")
    print(f"Renglones verificados: {total_renglones}")
    print(f"Botellas vendidas: {total_botellas}")
    print("Integridad del plan: correcta.")

# 4. Función principal
def main():
    print("Iniciando generador transaccional de Bando...")

    with conectar() as conn:
        print("Conexión establecida correctamente.")

        consultar_datos_maestros(conn)

        # Planificar diez ventas.
        ventas = planificar_ventas(conn, cantidad=10)

        # Validar las ventas antes de insertarlas.
        validar_plan_ventas(conn, ventas)


if __name__ == "__main__":
    main()