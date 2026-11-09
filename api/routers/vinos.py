from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from api.dal import vinos as vinos_dal
from api.schemas.vinos import (
    PaginatedVinosResponse,
    TipoVinoEnum,
    VinoCreate,
    VinoDetalleResponse,
    VinoUpdate,
)

router = APIRouter(prefix="/vinos", tags=["Vinos"])


@router.get(
    "",
    response_model=PaginatedVinosResponse,
    summary="Listado de Vinos Paginado y Filtrable",
    description="Retorna el catálogo de vinos paginado con filtros combinables por tipo, cepa, bodega o añada.",
)
def listar_vinos(
    limit: int = Query(20, ge=1, le=100, description="Cantidad máxima de resultados por página"),
    offset: int = Query(0, ge=0, description="Desplazamiento / salto de registros"),
    tipo: Optional[TipoVinoEnum] = Query(None, description="Filtrar por tipo (tinto, blanco, rosado, espumante)"),
    cepa: Optional[str] = Query(None, description="Filtrar por nombre o ID de cepa"),
    bodega: Optional[str] = Query(None, description="Filtrar por razón social o CUIT de la bodega"),
    anada: Optional[int] = Query(None, ge=1990, le=2100, description="Filtrar por año de cosecha"),
):
    total, items = vinos_dal.listar_vinos(
        limit=limit,
        offset=offset,
        tipo=tipo,
        cepa=cepa,
        bodega=bodega,
        anada=anada,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get(
    "/{cod_vino}",
    response_model=VinoDetalleResponse,
    summary="Detalle Completo de un Vino",
    description="Retorna todos los datos de un vino junto a su corte varietal (cepas y porcentajes) y maridajes recomendados.",
)
def obtener_vino(cod_vino: int):
    vino = vinos_dal.obtener_vino_por_codigo(cod_vino)
    if not vino:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vino con código {cod_vino} no encontrado.",
        )
    return vino


@router.post(
    "",
    response_model=VinoDetalleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Alta de Nuevo Vino con Composición Varietal",
    description=(
        "Registra un nuevo vino y su corte varietal en una transacción atómica. "
        "La base de datos verifica que los porcentajes sumen exactamente 100% (RN-05)."
    ),
)
def crear_vino(payload: VinoCreate):
    vino_data = {
        "nombre": payload.nombre,
        "tipo": payload.tipo,
        "anada": payload.anada,
        "volumen_ml": payload.volumen_ml,
        "graduacion": payload.graduacion,
        "precio": payload.precio,
        "cuit_bodega": payload.cuit_bodega,
    }
    composicion = [item.model_dump() for item in payload.composicion]
    vino = vinos_dal.crear_vino(vino_data, composicion, payload.maridajes)
    return vino


@router.put(
    "/{cod_vino}",
    response_model=VinoDetalleResponse,
    summary="Modificación de Vino",
    description=(
        "Actualiza los datos de un vino. Si se modifica el precio, la base de datos "
        "audita automáticamente el cambio en la tabla auditoria_precio (RN-13)."
    ),
)
def actualizar_vino(cod_vino: int, payload: VinoUpdate):
    update_data = payload.model_dump(exclude_unset=True)
    vino = vinos_dal.actualizar_vino(cod_vino, update_data)
    if not vino:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vino con código {cod_vino} no encontrado.",
        )
    return vino


@router.delete(
    "/{cod_vino}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Baja de Vino",
    description=(
        "Elimina un vino. Si el vino posee comprobantes, transferencias o ingresos históricos, "
        "la base de datos rechaza la eliminación con código 409 Conflict (RN-14)."
    ),
)
def eliminar_vino(cod_vino: int):
    vino_existente = vinos_dal.obtener_vino_por_codigo(cod_vino)
    if not vino_existente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vino con código {cod_vino} no encontrado.",
        )
    vinos_dal.eliminar_vino(cod_vino)
    return None

