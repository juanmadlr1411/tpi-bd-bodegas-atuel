import pytest
import psycopg

from api.config import settings


@pytest.fixture(scope="session", autouse=True)
def verificar_rol_no_propietario():
    """
    Verifica que la suite de integración de la API se ejecute con el rol sin privilegios
    de propietario (operador_atuel), cumpliendo con el Criterio de Aceptación
    obligatorio de la Etapa 6.
    """
    if settings.DB_USER in ("admin_atuel", "postgres"):
        pytest.fail(
            "Ejecución bloqueada: Los tests de la API deben ejecutarse con el "
            "rol de operador sin privilegios de propietario (operador_atuel).",
            pytrace=False,
        )

    with psycopg.connect(settings.conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user;")
            usuario_real = cur.fetchone()[0]

    if usuario_real in ("admin_atuel", "postgres"):
        pytest.fail(
            f"Ejecución bloqueada: La conexión activa en PostgreSQL pertenece a '{usuario_real}' "
            "(debe ser un rol restringido como 'operador_atuel').",
            pytrace=False,
        )
