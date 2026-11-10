import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
import psycopg

logger = logging.getLogger(__name__)

# Mapeo oficial de códigos SQLSTATE de PostgreSQL a estados HTTP según rúbrica Etapa 6
SQLSTATE_HTTP_MAP: dict[str, tuple[int, str]] = {
    "23505": (409, "Conflicto: Ya existe un registro con la misma clave única o primaria."),
    "23503": (409, "Conflicto de clave foránea: Registro relacionado inexistente o con dependencias activas."),
    "23514": (422, "Violación de restricción CHECK en los datos ingresados."),
    "23502": (422, "Violación de valor requerido NOT NULL."),
    "P0001": (409, "Regla de negocio rechazada por la base de datos."),
    "22P02": (400, "Formato de datos o tipo de dato inválido para PostgreSQL."),
    "40001": (503, "Fallo de serialización en transacción concurrente. Reintente la operación."),
    "40P01": (503, "Deadlock detectado. Reintente la operación."),
}


async def postgres_exception_handler(request: Request, exc: psycopg.Error) -> JSONResponse:
    """
    Manejador global de excepciones para errores de PostgreSQL / psycopg.
    Traduce el código SQLSTATE a un código HTTP semántico.
    """
    sqlstate = exc.sqlstate or "UNKNOWN"
    logger.error(f"Error de base de datos interceptado [SQLSTATE={sqlstate}]: {exc}")

    # Extraer mensaje detallado si está disponible en diag
    message = str(exc).strip()
    if exc.diag and exc.diag.message_primary:
        message = exc.diag.message_primary

    detail = exc.diag.message_detail if exc.diag and exc.diag.message_detail else None

    # Determinar código HTTP y descripción por defecto
    http_status, default_desc = SQLSTATE_HTTP_MAP.get(
        sqlstate,
        (status.HTTP_500_INTERNAL_SERVER_ERROR, "Error interno en el motor de base de datos.")
    )

    return JSONResponse(
        status_code=http_status,
        content={
            "error": default_desc,
            "sqlstate": sqlstate,
            "message": message,
            "detail": detail,
        },
    )
