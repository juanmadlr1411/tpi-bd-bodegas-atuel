from datetime import date
from typing import Optional
from api.database import get_db_connection


def crear_ingreso(cuit_bodega: str, cod_transporte: int, fecha: Optional[date] = None) -> dict:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if fecha is not None:
                cur.execute(
                    """
                    INSERT INTO ingreso (fecha, estado, cod_transporte, cuit_bodega)
                    VALUES (%s, 'en_confeccion', %s, %s)
                    RETURNING cod_ingreso, fecha, estado::text AS estado, cod_transporte, cuit_bodega;
                    """,
                    (fecha, cod_transporte, cuit_bodega),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO ingreso (estado, cod_transporte, cuit_bodega)
                    VALUES ('en_confeccion', %s, %s)
                    RETURNING cod_ingreso, fecha, estado::text AS estado, cod_transporte, cuit_bodega;
                    """,
                    (cod_transporte, cuit_bodega),
                )
            row = cur.fetchone()
            row["renglones"] = []
            return row


def agregar_renglon_ingreso(cod_ingreso: int, cod_vino: int, cantidad: int) -> dict:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO renglon_ingreso (cod_ingreso, cod_vino, cantidad)
                VALUES (%s, %s, %s)
                RETURNING cod_ingreso, cod_vino, cantidad;
                """,
                (cod_ingreso, cod_vino, cantidad),
            )
            return cur.fetchone()


def terminar_ingreso(cod_ingreso: int) -> Optional[dict]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingreso
                SET estado = 'terminado'
                WHERE cod_ingreso = %s
                RETURNING cod_ingreso, fecha, estado::text AS estado, cod_transporte, cuit_bodega;
                """,
                (cod_ingreso,),
            )
            return cur.fetchone()


def procesar_ingreso(cod_ingreso: int) -> Optional[dict]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CALL sp_procesar_ingreso(%s);", (cod_ingreso,))
            cur.execute(
                """
                SELECT cod_ingreso, fecha, estado::text AS estado, cod_transporte, cuit_bodega
                FROM ingreso
                WHERE cod_ingreso = %s;
                """,
                (cod_ingreso,),
            )
            return cur.fetchone()


def obtener_ingreso(cod_ingreso: int) -> Optional[dict]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cod_ingreso, fecha, estado::text AS estado, cod_transporte, cuit_bodega
                FROM ingreso
                WHERE cod_ingreso = %s;
                """,
                (cod_ingreso,),
            )
            cabecera = cur.fetchone()
            if not cabecera:
                return None

            cur.execute(
                """
                SELECT ri.cod_ingreso, ri.cod_vino, v.nombre AS nombre_vino, ri.cantidad
                FROM renglon_ingreso ri
                JOIN vino v ON v.cod_vino = ri.cod_vino
                WHERE ri.cod_ingreso = %s
                ORDER BY ri.cod_vino;
                """,
                (cod_ingreso,),
            )
            cabecera["renglones"] = cur.fetchall()
            return cabecera
