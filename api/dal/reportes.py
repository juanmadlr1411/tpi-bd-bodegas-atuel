from typing import Any, Optional
from api.database import get_db_cursor


def top_vinos_vendidos(limit: int = 10) -> list[dict[str, Any]]:
    """
    Consulta S1: Ranking de vinos con mayor cantidad de botellas vendidas
    en toda la red de salas.
    """
    query = """
        SELECT
            v.cod_vino,
            v.nombre,
            COALESCE(SUM(rc.cantidad), 0)::int AS total_botellas
        FROM vino v
        JOIN renglon_comprobante rc
            ON rc.cod_vino = v.cod_vino
        GROUP BY v.cod_vino, v.nombre
        ORDER BY total_botellas DESC, v.cod_vino ASC
        LIMIT %s;
    """
    with get_db_cursor() as cur:
        cur.execute(query, (limit,))
        return cur.fetchall()


def ventas_por_sala() -> list[dict[str, Any]]:
    """
    Consulta S8: Monto total de ventas por sala en el último trimestre,
    en orden descendente.
    """
    query = """
        SELECT
            s.id_sala,
            s.calle,
            s.numero,
            s.cod_postal,
            l.nombre AS localidad,
            COALESCE(SUM(c.total), 0)::float AS monto_total_trimestre
        FROM sala_venta s
        JOIN localidad l ON s.cod_postal = l.cod_postal
        LEFT JOIN comprobante c
            ON s.id_sala = c.id_sala
           AND c.fecha >= CURRENT_DATE - INTERVAL '3 months'
        GROUP BY s.id_sala, s.calle, s.numero, s.cod_postal, l.nombre
        ORDER BY monto_total_trimestre DESC, s.id_sala ASC;
    """
    with get_db_cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def vinos_sin_stock_sala(id_sala: int) -> list[dict[str, Any]]:
    """
    Consulta S6: Para una sala determinada, vinos sin stock en la sala
    pero con existencias en el depósito central.
    """
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
        ORDER BY v.cod_vino ASC;
    """
    with get_db_cursor() as cur:
        cur.execute(query, (id_sala,))
        return cur.fetchall()


def transportista_mas_activo() -> Optional[dict[str, Any]]:
    """
    Consulta S7: Empresa de transporte con mayor actividad de traslados
    en el último mes.
    """
    query = """
        SELECT
            t.cod_transporte,
            t.razon_social,
            COUNT(i.cod_ingreso)::int AS cantidad_traslados
        FROM transportista t
        JOIN ingreso i ON t.cod_transporte = i.cod_transporte
        WHERE i.fecha >= CURRENT_DATE - INTERVAL '1 month'
        GROUP BY t.cod_transporte, t.razon_social
        ORDER BY cantidad_traslados DESC, t.cod_transporte ASC
        LIMIT 1;
    """
    with get_db_cursor() as cur:
        cur.execute(query)
        return cur.fetchone()


def trazabilidad_vino(cod_vino: int) -> Optional[dict[str, Any]]:
    """
    Consulta S9: Ficha integral de trazabilidad de un vino (cepas con %,
    bodega, maridajes y stock total consolidado).
    """
    query = """
        WITH CepasVino AS (
            SELECT cv.cod_vino, STRING_AGG(c.nombre || ' (' || cv.porcentaje || '%%)', ', ' ORDER BY cv.porcentaje DESC) AS composicion
            FROM composicion_vino cv
            JOIN cepa c ON cv.id_cepa = c.id_cepa
            WHERE cv.cod_vino = %s
            GROUP BY cv.cod_vino
        ),
        MaridajesVino AS (
            SELECT vm.cod_vino, STRING_AGG(m.nombre, ', ' ORDER BY m.nombre ASC) AS maridajes
            FROM vino_maridaje vm
            JOIN maridaje m ON vm.id_maridaje = m.id_maridaje
            WHERE vm.cod_vino = %s
            GROUP BY vm.cod_vino
        )
        SELECT 
            v.cod_vino, 
            v.nombre AS vino, 
            b.razon_social AS bodega, 
            COALESCE(cv.composicion, 'Sin composición informada') AS composicion, 
            COALESCE(mv.maridajes, 'Sin maridajes informados') AS maridajes, 
            COALESCE(vw.stock_total, 0)::int AS stock_total
        FROM vino v
        JOIN bodega b ON v.cuit_bodega = b.cuit
        LEFT JOIN CepasVino cv ON v.cod_vino = cv.cod_vino
        LEFT JOIN MaridajesVino mv ON v.cod_vino = mv.cod_vino
        LEFT JOIN vw_stock_total_vino vw ON v.cod_vino = vw.cod_vino
        WHERE v.cod_vino = %s;
    """
    with get_db_cursor() as cur:
        cur.execute(query, (cod_vino, cod_vino, cod_vino))
        return cur.fetchone()
