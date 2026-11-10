from typing import Optional, Any
from api.database import get_db_connection, get_db_cursor


def crear_venta(
    id_cliente: int,
    id_sala: int,
    renglones: list[dict[str, Any]],
) -> int:
    """
    Registra una venta completa (cabecera y renglones) en una única transacción.

    El precio unitario y el porcentaje de descuento se obtienen de la base de datos
    para preservar las condiciones históricas de la operación. Los subtotales, los
    totales de la cabecera y el descuento de stock son calculados exclusivamente
    por los triggers de la base de datos (RN-08 y RN-09).
    """
    query_insert_cabecera = """
        INSERT INTO comprobante (id_cliente, id_sala)
        VALUES (%s, %s)
        RETURNING nro_comprobante;
    """

    query_precio_vino = "SELECT precio FROM vino WHERE cod_vino = %s;"
    query_descuento_cliente = "SELECT porcentaje_descuento FROM cliente WHERE id_cliente = %s;"

    query_insert_renglon = """
        INSERT INTO renglon_comprobante (
            nro_comprobante, cod_vino, cantidad, precio_unitario, descuento, subtotal
        )
        VALUES (%s, %s, %s, %s, %s, 0);
    """

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(query_descuento_cliente, (id_cliente,))
                cliente = cur.fetchone()
                if not cliente:
                    raise LookupError(f"Cliente con ID {id_cliente} no encontrado.")
                descuento = cliente["porcentaje_descuento"]

                cur.execute(query_insert_cabecera, (id_cliente, id_sala))
                nro_comprobante = cur.fetchone()["nro_comprobante"]

                for renglon in renglones:
                    cod_vino = renglon["cod_vino"]

                    cur.execute(query_precio_vino, (cod_vino,))
                    vino = cur.fetchone()
                    if not vino:
                        raise LookupError(f"Vino con código {cod_vino} no encontrado.")

                    cur.execute(
                        query_insert_renglon,
                        (
                            nro_comprobante,
                            cod_vino,
                            renglon["cantidad"],
                            vino["precio"],
                            descuento,
                        ),
                    )

    return nro_comprobante


def obtener_comprobante(nro_comprobante: int) -> Optional[dict[str, Any]]:
    """
    Obtiene la cabecera de un comprobante con sus totales calculados por la base
    de datos y el listado completo de renglones.
    """
    query_cabecera = """
        SELECT
            c.nro_comprobante,
            c.fecha,
            c.id_cliente,
            cl.nombre_razon_social AS cliente_nombre,
            c.id_sala,
            c.subtotal,
            c.descuento,
            c.total
        FROM comprobante c
        JOIN cliente cl ON c.id_cliente = cl.id_cliente
        WHERE c.nro_comprobante = %s;
    """

    query_renglones = """
        SELECT
            rc.cod_vino,
            v.nombre AS nombre_vino,
            rc.cantidad,
            rc.precio_unitario,
            rc.descuento,
            rc.subtotal
        FROM renglon_comprobante rc
        JOIN vino v ON rc.cod_vino = v.cod_vino
        WHERE rc.nro_comprobante = %s
        ORDER BY v.nombre ASC;
    """

    with get_db_cursor() as cur:
        cur.execute(query_cabecera, (nro_comprobante,))
        comprobante = cur.fetchone()
        if not comprobante:
            return None

        cur.execute(query_renglones, (nro_comprobante,))
        comprobante["renglones"] = cur.fetchall()

    return comprobante
