from typing import Optional, Any
from api.database import get_db_connection, get_db_cursor


def listar_vinos(
    limit: int = 20,
    offset: int = 0,
    tipo: Optional[str] = None,
    cepa: Optional[str] = None,
    bodega: Optional[str] = None,
    anada: Optional[int] = None,
) -> tuple[int, list[dict[str, Any]]]:
    """
    Lista vinos con paginación y filtros dinámicos 100% parametrizados.
    Protege contra inyección SQL al usar placeholders %s.
    """
    where_clauses: list[str] = ["1=1"]
    params: list[Any] = []
    count_params: list[Any] = []

    if tipo:
        where_clauses.append("v.tipo = %s")
        params.append(tipo)
        count_params.append(tipo)

    if anada is not None:
        where_clauses.append("v.anada = %s")
        params.append(anada)
        count_params.append(anada)

    if bodega:
        where_clauses.append("(b.razon_social ILIKE %s OR v.cuit_bodega = %s)")
        bodega_pattern = f"%{bodega}%"
        params.extend([bodega_pattern, bodega])
        count_params.extend([bodega_pattern, bodega])

    if cepa:
        where_clauses.append("""
            EXISTS (
                SELECT 1
                FROM composicion_vino cv
                JOIN cepa c ON cv.id_cepa = c.id_cepa
                WHERE cv.cod_vino = v.cod_vino
                  AND (c.nombre ILIKE %s OR c.id_cepa::text = %s)
            )
        """)
        cepa_pattern = f"%{cepa}%"
        params.extend([cepa_pattern, cepa])
        count_params.extend([cepa_pattern, cepa])

    where_sql = " AND ".join(where_clauses)

    count_query = f"""
        SELECT COUNT(DISTINCT v.cod_vino) AS total
        FROM vino v
        JOIN bodega b ON v.cuit_bodega = b.cuit
        WHERE {where_sql};
    """

    data_query = f"""
        SELECT 
            v.cod_vino,
            v.nombre,
            v.tipo,
            v.anada,
            v.volumen_ml,
            v.graduacion,
            v.precio,
            v.cuit_bodega,
            b.razon_social AS bodega_razon_social
        FROM vino v
        JOIN bodega b ON v.cuit_bodega = b.cuit
        WHERE {where_sql}
        ORDER BY v.nombre ASC, v.anada DESC
        LIMIT %s OFFSET %s;
    """
    params.extend([limit, offset])

    with get_db_cursor() as cur:
        cur.execute(count_query, count_params)
        total = cur.fetchone()["total"]

        cur.execute(data_query, params)
        items = cur.fetchall()

    return total, items


def obtener_vino_por_codigo(cod_vino: int) -> Optional[dict[str, Any]]:
    """
    Obtiene el detalle completo de un vino, incluyendo sus cortes de cepa y maridajes.
    """
    query_vino = """
        SELECT 
            v.cod_vino,
            v.nombre,
            v.tipo,
            v.anada,
            v.volumen_ml,
            v.graduacion,
            v.precio,
            v.cuit_bodega,
            b.razon_social AS bodega_razon_social
        FROM vino v
        JOIN bodega b ON v.cuit_bodega = b.cuit
        WHERE v.cod_vino = %s;
    """

    query_comp = """
        SELECT 
            cv.id_cepa,
            c.nombre AS nombre_cepa,
            c.tipo::text AS tipo_cepa,
            cv.porcentaje
        FROM composicion_vino cv
        JOIN cepa c ON cv.id_cepa = c.id_cepa
        WHERE cv.cod_vino = %s
        ORDER BY cv.porcentaje DESC;
    """

    query_maridajes = """
        SELECT 
            vm.id_maridaje,
            m.nombre,
            m.temperatura_servicio
        FROM vino_maridaje vm
        JOIN maridaje m ON vm.id_maridaje = m.id_maridaje
        WHERE vm.cod_vino = %s
        ORDER BY m.nombre ASC;
    """

    with get_db_cursor() as cur:
        cur.execute(query_vino, (cod_vino,))
        vino = cur.fetchone()
        if not vino:
            return None

        cur.execute(query_comp, (cod_vino,))
        vino["composicion"] = cur.fetchall()

        cur.execute(query_maridajes, (cod_vino,))
        vino["maridajes"] = cur.fetchall()

    return vino


def crear_vino(vino_data: dict[str, Any], composicion: list[dict[str, Any]], maridajes: list[int]) -> dict[str, Any]:
    """
    Inserta un vino y su composición atómicamente.
    La BD valida al hacer commit que la suma de porcentajes sea 100% (RN-05).
    """
    query_insert_vino = """
        INSERT INTO vino (nombre, tipo, anada, volumen_ml, graduacion, precio, cuit_bodega)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING cod_vino;
    """

    query_insert_comp = """
        INSERT INTO composicion_vino (cod_vino, id_cepa, porcentaje)
        VALUES (%s, %s, %s);
    """

    query_insert_maridaje = """
        INSERT INTO vino_maridaje (cod_vino, id_maridaje)
        VALUES (%s, %s);
    """

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    query_insert_vino,
                    (
                        vino_data["nombre"],
                        vino_data["tipo"],
                        vino_data["anada"],
                        vino_data["volumen_ml"],
                        vino_data["graduacion"],
                        vino_data["precio"],
                        vino_data["cuit_bodega"],
                    ),
                )
                cod_vino = cur.fetchone()["cod_vino"]

                for item in composicion:
                    cur.execute(query_insert_comp, (cod_vino, item["id_cepa"], item["porcentaje"]))

                for id_maridaje in maridajes:
                    cur.execute(query_insert_maridaje, (cod_vino, id_maridaje))

    # Retornar el objeto recién creado
    return obtener_vino_por_codigo(cod_vino)


def actualizar_vino(cod_vino: int, update_data: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Actualiza atributos de un vino. Si se modifica el precio, el trigger de auditoría
    trg_auditar_cambio_precio registra el cambio automáticamente en auditoria_precio (RN-13).
    """
    if not update_data:
        return obtener_vino_por_codigo(cod_vino)

    set_clauses = []
    params = []

    for field, value in update_data.items():
        set_clauses.append(f"{field} = %s")
        params.append(value)

    params.append(cod_vino)
    set_sql = ", ".join(set_clauses)

    query = f"""
        UPDATE vino
        SET {set_sql}
        WHERE cod_vino = %s
        RETURNING cod_vino;
    """

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(query, params)
                res = cur.fetchone()
                if not res:
                    return None

    return obtener_vino_por_codigo(cod_vino)


def eliminar_vino(cod_vino: int) -> bool:
    """
    Elimina un vino. Si tiene movimientos históricos (ventas, transferencias, stock),
    la foreign key con ON DELETE RESTRICT rechazará la operación con código SQLSTATE 23503 (RN-14).
    """
    query = "DELETE FROM vino WHERE cod_vino = %s RETURNING cod_vino;"

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(query, (cod_vino,))
                res = cur.fetchone()
                return res is not None
