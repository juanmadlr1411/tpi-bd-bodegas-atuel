from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
import psycopg

from api.database import get_db_cursor

router = APIRouter(tags=["Salud"])


@router.get(
    "/salud",
    summary="Verificación de Salud y Conectividad a la Base de Datos",
    description="Ejecuta una consulta liviana contra PostgreSQL a través del pool para verificar conectividad.",
)
def verificar_salud():
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT 1 AS alive, current_user AS usuario, current_database() AS db;")
            row = cur.fetchone()
            return {
                "status": "ok",
                "db": "connected",
                "usuario": row["usuario"],
                "database": row["db"],
            }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "db": "disconnected",
                "detail": str(e),
            },
        )
