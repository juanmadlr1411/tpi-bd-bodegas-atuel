import pytest
import psycopg

from api.config import settings


BASE_PERMITIDA = "bodegas_atuel_h6_tests"
USUARIO_PERMITIDO = "operador_h6_qa"


@pytest.fixture(scope="session", autouse=True)
def proteger_base_datos_tests():
    """
    Impide ejecutar los tests sobre una base de datos
    distinta de la autorizada para integración.
    """

    # Primera protección: configuración de FastAPI.
    if (
        settings.DB_NAME != BASE_PERMITIDA
        or settings.DB_USER != USUARIO_PERMITIDO
    ):
        pytest.fail(
            "Ejecución bloqueada: los tests requieren "
            f"DB_NAME={BASE_PERMITIDA} y "
            f"DB_USER={USUARIO_PERMITIDO}.",
            pytrace=False,
        )

    # Segunda protección: conexión real a PostgreSQL.
    with psycopg.connect(settings.conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_database(), current_user;"
            )
            base_real, usuario_real = cur.fetchone()

    if (
        base_real != BASE_PERMITIDA
        or usuario_real != USUARIO_PERMITIDO
    ):
        pytest.fail(
            "Ejecución bloqueada: PostgreSQL devolvió "
            f"base={base_real}, usuario={usuario_real}.",
            pytrace=False,
        )