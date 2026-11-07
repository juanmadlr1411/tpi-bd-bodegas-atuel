from datetime import date

from conexion import conectar


def obtener_datos_maestros(conn):
    """
    Obtiene datos maestros desde PostgreSQL.
    No modifica ningún registro.
    """

    with conn.cursor() as cursor:

        # Clientes y sus fechas de alta.
        cursor.execute("""
            SELECT id_cliente, fecha_alta
            FROM cliente
            ORDER BY id_cliente
        """)
        clientes = cursor.fetchall()
        cursor.execute("""
            SELECT id_cliente, porcentaje_descuento
            FROM cliente ORDER BY id_cliente
        """)
        descuentos_clientes = dict(cursor.fetchall())

        # Vinos, bodegas, añadas y precios.
        cursor.execute("""
            SELECT cod_vino, cuit_bodega, anada, precio
            FROM vino
            ORDER BY cod_vino
        """)
        vinos = cursor.fetchall()

        # Salas de venta.
        cursor.execute("""
            SELECT id_sala
            FROM sala_venta
            ORDER BY id_sala
        """)
        salas = [fila[0] for fila in cursor.fetchall()]

        # Transportistas.
        cursor.execute("""
            SELECT cod_transporte
            FROM transportista
            ORDER BY cod_transporte
        """)
        transportistas = [
            fila[0] for fila in cursor.fetchall()
        ]

    return {
        "clientes": clientes,
        "descuentos_clientes": descuentos_clientes,
        "vinos": vinos,
        "salas": salas,
        "transportistas": transportistas
    }


def obtener_disponibles(datos, fecha):
    """
    Filtra clientes y vinos disponibles para una fecha.
    """

    clientes = [
        id_cliente
        for id_cliente, fecha_alta in datos["clientes"]
        if fecha_alta <= fecha
    ]

    vinos_por_bodega = {}

    for cod_vino, cuit_bodega, anada, precio in datos["vinos"]:

        if anada <= fecha.year:
            vinos_por_bodega.setdefault(
                cuit_bodega, []
            ).append((cod_vino, precio))

    return clientes, vinos_por_bodega


def main():

    with conectar() as conn:
        datos = obtener_datos_maestros(conn)

    print("DATOS MAESTROS DISPONIBLES")
    print("-" * 45)

    fechas = [
        date(2022, 1, 20),
        date(2024, 6, 20),
        date(2026, 10, 31)
    ]

    for fecha in fechas:

        clientes, vinos_por_bodega = obtener_disponibles(
            datos, fecha
        )

        total_vinos = sum(
            len(vinos)
            for vinos in vinos_por_bodega.values()
        )

        print(f"\nFecha: {fecha}")
        print(f"Clientes disponibles: {len(clientes)}")
        print(f"Vinos disponibles: {total_vinos}")
        print(f"Bodegas con vinos: {len(vinos_por_bodega)}")

    print(f"\nSalas de venta: {len(datos['salas'])}")
    print(f"Transportistas: {len(datos['transportistas'])}")


if __name__ == "__main__":
    main()