from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from api.dal import clientes as clientes_dal
from api.schemas.clientes import (
    ClienteCreate,
    ClienteResponse,
    ClienteUpdate,
    PaginatedClientesResponse,
    TipoClienteEnum,
)

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.get(
    "",
    response_model=PaginatedClientesResponse,
    summary="Listado de Clientes Paginado",
    description="Retorna el listado de clientes paginado con filtro opcional por tipo (socio, distribuidor, exportador).",
)
def listar_clientes(
    limit: int = Query(20, ge=1, le=100, description="Cantidad de registros por página"),
    offset: int = Query(0, ge=0, description="Desplazamiento inicial"),
    tipo_cliente: Optional[TipoClienteEnum] = Query(None, description="Filtrar por subtipo de cliente"),
):
    total, items = clientes_dal.listar_clientes(
        limit=limit,
        offset=offset,
        tipo_cliente=tipo_cliente,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get(
    "/{id_cliente}",
    response_model=ClienteResponse,
    summary="Detalle de un Cliente",
    description="Obtiene los datos del cliente junto a sus campos específicos de subtipo.",
)
def obtener_cliente(id_cliente: int):
    cliente = clientes_dal.obtener_cliente_por_id(id_cliente)
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente con ID {id_cliente} no encontrado.",
        )
    return cliente


@router.post(
    "",
    response_model=ClienteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Alta de Cliente",
    description=(
        "Registra un nuevo cliente del tipo indicado (socio, distribuidor, exportador). "
        "El porcentaje de descuento es asignado automáticamente por la base de datos (RN-06)."
    ),
)
def crear_cliente(payload: ClienteCreate):
    cliente_data = {
        "nombre_razon_social": payload.nombre_razon_social,
        "tipo_documento": payload.tipo_documento,
        "nro_documento": payload.nro_documento,
        "direccion": payload.direccion,
        "cod_postal": payload.cod_postal,
        "tipo_cliente": payload.tipo_cliente,
    }
    subtipo_data = {
        "zona_cobertura": payload.zona_cobertura,
        "nro_habilitacion": payload.nro_habilitacion,
        "pais_destino": payload.pais_destino,
    }
    cliente = clientes_dal.crear_cliente(cliente_data, subtipo_data)
    return cliente


@router.put(
    "/{id_cliente}",
    response_model=ClienteResponse,
    summary="Modificación de Cliente",
    description="Actualiza la información de un cliente existente.",
)
def actualizar_cliente(id_cliente: int, payload: ClienteUpdate):
    cliente_existente = clientes_dal.obtener_cliente_por_id(id_cliente)
    if not cliente_existente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente con ID {id_cliente} no encontrado.",
        )

    base_fields = {"nombre_razon_social", "direccion", "cod_postal"}
    dumped = payload.model_dump(exclude_unset=True)

    base_data = {k: v for k, v in dumped.items() if k in base_fields}
    subtipo_data = {k: v for k, v in dumped.items() if k not in base_fields}

    cliente = clientes_dal.actualizar_cliente(id_cliente, base_data, subtipo_data)
    return cliente


@router.delete(
    "/{id_cliente}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Baja de Cliente",
    description=(
        "Elimina un cliente. Si tiene ventas históricas asociadas, la base de datos "
        "rechazará la eliminación con error 409 Conflict (RN-14)."
    ),
)
def eliminar_cliente(id_cliente: int):
    cliente_existente = clientes_dal.obtener_cliente_por_id(id_cliente)
    if not cliente_existente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente con ID {id_cliente} no encontrado.",
        )
    clientes_dal.eliminar_cliente(id_cliente)
    return None
