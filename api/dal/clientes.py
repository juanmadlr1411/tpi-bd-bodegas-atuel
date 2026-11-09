from typing import Optional, Any
from api.database import get_db_connection, get_db_cursor


def listar_clientes(
    limit: int = 20,
    offset: int = 0,
    tipo_cliente: Optional[str] = None,
) -> tuple[int, list[dict[str, Any]]]:
    """
    Lista clientes con paginación y filtro opcional por tipo de cliente.
    """
    where_clauses = ["1=1"]
    params: list[Any] = []
    count_params: list[Any] = []

    if tipo_cliente:
        where_clauses.append("c.tipo_cliente = %s")
        params.append(tipo_cliente)
        count_params.append(tipo_cliente)

    where_sql = " AND ".join(where_clauses)

    count_query = f"""
        SELECT COUNT(*) AS total
        FROM cliente c
        WHERE {where_sql};
    """

    data_query = f"""
        SELECT 
            c.id_cliente,
            c.nombre_razon_social,
            c.tipo_documento,
            c.nro_documento,
            c.direccion,
            c.cod_postal,
            l.nombre AS localidad_nombre,
            c.fecha_alta,
            c.tipo_cliente::text AS tipo_cliente,
            c.porcentaje_descuento,
            cd.zona_cobertura,
            cd.nro_habilitacion,
            ce.pais_destino
        FROM cliente c
        JOIN localidad l ON c.cod_postal = l.cod_postal
        LEFT JOIN cliente_distribuidor cd ON c.id_cliente = cd.id_cliente
        LEFT JOIN cliente_exportador ce ON c.id_cliente = ce.id_cliente
        WHERE {where_sql}
        ORDER BY c.nombre_razon_social ASC
        LIMIT %s OFFSET %s;
    """
    params.extend([limit, offset])

    with get_db_cursor() as cur:
        cur.execute(count_query, count_params)
        total = cur.fetchone()["total"]

        cur.execute(data_query, params)
        items = cur.fetchall()

    return total, items


def obtener_cliente_por_id(id_cliente: int) -> Optional[dict[str, Any]]:
    """
    Obtiene los datos completos de un cliente con su subtipo correspondiente.
    """
    query = """
        SELECT 
            c.id_cliente,
            c.nombre_razon_social,
            c.tipo_documento,
            c.nro_documento,
            c.direccion,
            c.cod_postal,
            l.nombre AS localidad_nombre,
            c.fecha_alta,
            c.tipo_cliente::text AS tipo_cliente,
            c.porcentaje_descuento,
            cd.zona_cobertura,
            cd.nro_habilitacion,
            ce.pais_destino
        FROM cliente c
        JOIN localidad l ON c.cod_postal = l.cod_postal
        LEFT JOIN cliente_distribuidor cd ON c.id_cliente = cd.id_cliente
        LEFT JOIN cliente_exportador ce ON c.id_cliente = ce.id_cliente
        WHERE c.id_cliente = %s;
    """
    with get_db_cursor() as cur:
        cur.execute(query, (id_cliente,))
        return cur.fetchone()


def crear_cliente(cliente_data: dict[str, Any], subtipo_data: dict[str, Any]) -> dict[str, Any]:
    """
    Crea un cliente base y su correspondiente registro de subtipo en una sola transacción.
    El trigger trg_asignar_descuento_cliente calcula y asigna el descuento normativo (RN-06).
    """
    query_insert_cliente = """
        INSERT INTO cliente (nombre_razon_social, tipo_documento, nro_documento, direccion, cod_postal, tipo_cliente)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id_cliente;
    """

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    query_insert_cliente,
                    (
                        cliente_data["nombre_razon_social"],
                        cliente_data["tipo_documento"],
                        cliente_data["nro_documento"],
                        cliente_data["direccion"],
                        cliente_data["cod_postal"],
                        cliente_data["tipo_cliente"],
                    ),
                )
                id_cliente = cur.fetchone()["id_cliente"]

                tipo = cliente_data["tipo_cliente"]
                if tipo == "socio":
                    cur.execute(
                        "INSERT INTO cliente_socio (id_cliente) VALUES (%s);",
                        (id_cliente,),
                    )
                elif tipo == "distribuidor":
                    cur.execute(
                        """
                        INSERT INTO cliente_distribuidor (id_cliente, zona_cobertura, nro_habilitacion)
                        VALUES (%s, %s, %s);
                        """,
                        (id_cliente, subtipo_data["zona_cobertura"], subtipo_data["nro_habilitacion"]),
                    )
                elif tipo == "exportador":
                    cur.execute(
                        """
                        INSERT INTO cliente_exportador (id_cliente, pais_destino)
                        VALUES (%s, %s);
                        """,
                        (id_cliente, subtipo_data["pais_destino"]),
                    )

    return obtener_cliente_por_id(id_cliente)


def actualizar_cliente(
    id_cliente: int,
    base_data: dict[str, Any],
    subtipo_data: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """
    Actualiza datos de cliente base y subtipo si corresponden.
    """
    cliente = obtener_cliente_por_id(id_cliente)
    if not cliente:
        return None

    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                if base_data:
                    set_clauses = [f"{k} = %s" for k in base_data.keys()]
                    params = list(base_data.values()) + [id_cliente]
                    cur.execute(
                        f"UPDATE cliente SET {', '.join(set_clauses)} WHERE id_cliente = %s;",
                        params,
                    )

                tipo = cliente["tipo_cliente"]
                if tipo == "distribuidor" and subtipo_data:
                    dist_fields = {k: v for k, v in subtipo_data.items() if k in {"zona_cobertura", "nro_habilitacion"}}
                    if dist_fields:
                        clauses = [f"{k} = %s" for k in dist_fields.keys()]
                        p = list(dist_fields.values()) + [id_cliente]
                        cur.execute(
                            f"UPDATE cliente_distribuidor SET {', '.join(clauses)} WHERE id_cliente = %s;",
                            p,
                        )
                elif tipo == "exportador" and subtipo_data:
                    exp_fields = {k: v for k, v in subtipo_data.items() if k in {"pais_destino"}}
                    if exp_fields:
                        clauses = [f"{k} = %s" for k in exp_fields.keys()]
                        p = list(exp_fields.values()) + [id_cliente]
                        cur.execute(
                            f"UPDATE cliente_exportador SET {', '.join(clauses)} WHERE id_cliente = %s;",
                            p,
                        )

    return obtener_cliente_por_id(id_cliente)


def eliminar_cliente(id_cliente: int) -> bool:
    """
    Elimina un cliente. Si tiene ventas históricas asociadas (comprobantes),
    la FK RESTRICT abortará la transacción con error 23503 (RN-14).
    """
    query = "DELETE FROM cliente WHERE id_cliente = %s RETURNING id_cliente;"
    with get_db_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(query, (id_cliente,))
                res = cur.fetchone()
                return res is not None

