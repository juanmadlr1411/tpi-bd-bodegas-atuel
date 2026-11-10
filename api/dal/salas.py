from typing import Any
from api.database import get_db_cursor


def listar_salas() -> list[dict[str, Any]]:
    """
    Retorna el listado de salas de venta con su localidad, ordenado por ID.
    """
    query = """
        SELECT
            s.id_sala,
            s.calle,
            s.numero,
            s.dia_cierre::text AS dia_cierre,
            s.cod_postal,
            l.nombre AS localidad_nombre
        FROM sala_venta s
        JOIN localidad l ON s.cod_postal = l.cod_postal
        ORDER BY s.id_sala ASC;
    """
    with get_db_cursor() as cur:
        cur.execute(query)
        return cur.fetchall()
