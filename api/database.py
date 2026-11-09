import logging
from contextlib import contextmanager
from typing import Generator
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from api.config import settings

logger = logging.getLogger(__name__)

pool: ConnectionPool | None = None


def init_pool() -> ConnectionPool:
    """
    Inicializa el pool de conexiones de psycopg3.
    """
    global pool
    if pool is None:
        logger.info(
            f"Inicializando pool de conexiones a {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME} "
            f"con usuario '{settings.DB_USER}'..."
        )
        pool = ConnectionPool(
            conninfo=settings.conninfo,
            min_size=settings.DB_POOL_MIN_SIZE,
            max_size=settings.DB_POOL_MAX_SIZE,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return pool


def close_pool() -> None:
    """
    Cierra todas las conexiones del pool.
    """
    global pool
    if pool is not None:
        logger.info("Cerrando pool de conexiones PostgreSQL...")
        pool.close()
        pool = None


@contextmanager
def get_db_connection() -> Generator[psycopg.Connection, None, None]:
    """
    Context manager para obtener una conexión del pool y retornarla al finalizar.
    """
    if pool is None:
        raise RuntimeError("El pool de conexiones a la base de datos no está inicializado.")
    with pool.connection() as conn:
        yield conn


@contextmanager
def get_db_cursor() -> Generator[psycopg.Cursor, None, None]:
    """
    Context manager conveniente que entrega directamente un cursor con row_factory=dict_row.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            yield cur
