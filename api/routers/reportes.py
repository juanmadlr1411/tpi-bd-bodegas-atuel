from fastapi import APIRouter, Query

from api.dal import reportes as reportes_dal


router = APIRouter(
    prefix="/reportes",
    tags=["Reportes"]
)


@router.get("/top-vinos")
def top_vinos():
    """Ranking de los 10 vinos más vendidos."""
    return reportes_dal.obtener_top_vinos()


@router.get("/ventas-por-sala")
def ventas_por_sala():
    """Ventas por sala en los últimos tres meses."""
    return reportes_dal.obtener_ventas_por_sala()


@router.get("/vinos-sin-stock")
def vinos_sin_stock(
    id_sala: int = Query(..., ge=1)
):
    """Vinos sin existencias en la sala seleccionada."""
    return reportes_dal.obtener_vinos_sin_stock(id_sala)