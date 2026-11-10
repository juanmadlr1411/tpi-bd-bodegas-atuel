from typing import Optional
from api.database import get_db_connection


def crear_transferencia(id_sala: int) -> dict:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO transferencia (id_sala, estado)
                VALUES (%s, 'en_confeccion')
                RETURNING nro_transferencia, id_sala, fecha_confeccion, estado::text AS estado;
                """,
                (id_sala,),
            )
            row = cur.fetchone()
            row["renglones"] = []
            return row


def agregar_renglon_transferencia(nro_transferencia: int, cod_vino: int, cantidad: int) -> dict:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO renglon_transferencia (nro_transferencia, cod_vino, cantidad)
                VALUES (%s, %s, %s)
                RETURNING nro_transferencia, cod_vino, cantidad;
                """,
                (nro_transferencia, cod_vino, cantidad),
            )
            return cur.fetchone()


def terminar_transferencia(nro_transferencia: int) -> Optional[dict]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE transferencia
                SET estado = 'terminado'
                WHERE nro_transferencia = %s
                RETURNING nro_transferencia, id_sala, fecha_confeccion, estado::text AS estado;
                """,
                (nro_transferencia,),
            )
            return cur.fetchone()


def procesar_transferencia(nro_transferencia: int) -> Optional[dict]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CALL sp_procesar_transferencia(%s);", (nro_transferencia,))
            cur.execute(
                """
                SELECT nro_transferencia, id_sala, fecha_confeccion, estado::text AS estado
                FROM transferencia
                WHERE nro_transferencia = %s;
                """,
                (nro_transferencia,),
            )
            return cur.fetchone()


def obtener_transferencia(nro_transferencia: int) -> Optional[dict]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT nro_transferencia, id_sala, fecha_confeccion, estado::text AS estado
                FROM transferencia
                WHERE nro_transferencia = %s;
                """,
                (nro_transferencia,),
            )
            cabecera = cur.fetchone()
            if not cabecera:
                return None

            cur.execute(
                """
                SELECT rt.nro_transferencia, rt.cod_vino, v.nombre AS nombre_vino, rt.cantidad
                FROM renglon_transferencia rt
                JOIN vino v ON v.cod_vino = rt.cod_vino
                WHERE rt.nro_transferencia = %s
                ORDER BY rt.cod_vino;
                """,
                (nro_transferencia,),
            )
            cabecera["renglones"] = cur.fetchall()
            return cabecera
