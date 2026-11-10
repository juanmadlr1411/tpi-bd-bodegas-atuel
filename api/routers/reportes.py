from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from api.dal import reportes as reportes_dal
from api.schemas.reportes import (
    TopVinoResponse,
    VentasPorSalaResponse,
    VinoSinStockResponse,
    TransportistaActivoResponse,
    TrazabilidadVinoResponse,
)

router = APIRouter(prefix="/reportes", tags=["Reportes"])


@router.get(
    "/top-vinos",
    response_model=list[TopVinoResponse],
    summary="Top Vinos Más Vendidos",
    description="Ranking de los vinos con mayor cantidad de botellas vendidas en la red (Consulta S1 de Sección 8).",
)
def obtener_top_vinos(limit: int = Query(10, ge=1, le=50, description="Cantidad máxima de vinos a listar")):
    return reportes_dal.top_vinos_vendidos(limit=limit)


@router.get(
    "/ventas-por-sala",
    response_model=list[VentasPorSalaResponse],
    summary="Ventas por Sala en el Último Trimestre",
    description="Facturación total acumulada por sala en los últimos 3 meses (Consulta S8 de Sección 8).",
)
def obtener_ventas_por_sala():
    return reportes_dal.ventas_por_sala()


@router.get(
    "/vinos-sin-stock",
    response_model=list[VinoSinStockResponse],
    summary="Vinos sin Stock en Sala pero con Stock en Depósito",
    description="Identifica quiebres de stock en una sala específica que pueden abastecerse desde el depósito central (Consulta S6 de Sección 8).",
)
def obtener_vinos_sin_stock(id_sala: int = Query(..., gt=0, description="ID de la sala a consultar")):
    return reportes_dal.vinos_sin_stock_sala(id_sala=id_sala)


@router.get(
    "/transportista-activo",
    response_model=Optional[TransportistaActivoResponse],
    summary="Transportista Más Activo del Último Mes",
    description="Empresa de transporte con mayor cantidad de traslados/ingresos en el último mes (Consulta S7 de Sección 8).",
)
def obtener_transportista_activo():
    res = reportes_dal.transportista_mas_activo()
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se registraron movimientos de transporte en el último mes.",
        )
    return res


@router.get(
    "/trazabilidad/{cod_vino}",
    response_model=TrazabilidadVinoResponse,
    summary="Ficha Técnica y Trazabilidad de un Vino",
    description="Ficha integral de un vino con corte de cepas, bodega productora, maridajes sugeridos y stock total consolidado (Consulta S9 de Sección 8).",
)
def obtener_trazabilidad(cod_vino: int):
    res = reportes_dal.trazabilidad_vino(cod_vino)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vino con código {cod_vino} no encontrado.",
        )
    return res
