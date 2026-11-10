from api.database import get_db_cursor


def obtener_top_vinos():
    """S1: Los 10 vinos más vendidos de toda la red."""
    query = """
        SELECT
            v.cod_vino,
            v.nombre,
            SUM(rc.cantidad) AS total_botellas
        FROM vino v
        JOIN renglon_comprobante rc
            ON rc.cod_vino = v.cod_vino
        GROUP BY v.cod_vino, v.nombre
        ORDER BY total_botellas DESC, v.cod_vino
        LIMIT 10;
    """

    with get_db_cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def obtener_ventas_por_sala():
    """S8: Facturación por sala durante los últimos tres meses."""
    query = """
        SELECT
            s.id_sala,
            s.calle,
            s.numero,
            s.cod_postal,
            SUM(c.total) AS monto_total_trimestre
        FROM sala_venta s
        JOIN comprobante c
            ON c.id_sala = s.id_sala
        WHERE c.fecha >= CURRENT_DATE - INTERVAL '3 months'
        GROUP BY
            s.id_sala,
            s.calle,
            s.numero,
            s.cod_postal
        ORDER BY monto_total_trimestre DESC;
    """

    with get_db_cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def obtener_vinos_sin_stock(id_sala: int):
    """S6: Vinos sin stock en una sala, disponibles en depósito."""
    query = """
        SELECT
            v.cod_vino,
            v.nombre,
            sd.cantidad AS stock_deposito
        FROM stock_deposito sd
        JOIN vino v
            ON v.cod_vino = sd.cod_vino
        LEFT JOIN stock_sala ss
            ON ss.cod_vino = sd.cod_vino
            AND ss.id_sala = %s
        WHERE COALESCE(ss.cantidad, 0) = 0
            AND sd.cantidad > 0
        ORDER BY v.cod_vino;
    """

    with get_db_cursor() as cur:
        cur.execute(query, (id_sala,))
        return cur.fetchall()