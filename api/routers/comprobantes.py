from fastapi import APIRouter, HTTPException, status

from api.dal import comprobantes as comprobantes_dal
from api.schemas.comprobantes import ComprobanteCreate, ComprobanteResponse

router = APIRouter(prefix="/comprobantes", tags=["Comprobantes"])


@router.post(
    "",
    response_model=ComprobanteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Emisión de Comprobante de Venta",
    description=(
        "Registra la venta completa (cabecera y renglones) en una única transacción. "
        "La base de datos valida el stock de la sala (RN-09), lo descuenta y calcula "
        "los subtotales y el total neto (RN-08). Si el stock es insuficiente se "
        "rechaza la operación con 409 Conflict y se revierte toda la transacción."
    ),
)
def crear_comprobante(payload: ComprobanteCreate):
    renglones = [item.model_dump() for item in payload.renglones]

    try:
        nro_comprobante = comprobantes_dal.crear_venta(
            id_cliente=payload.id_cliente,
            id_sala=payload.id_sala,
            renglones=renglones,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return comprobantes_dal.obtener_comprobante(nro_comprobante)


@router.get(
    "/{nro_comprobante}",
    response_model=ComprobanteResponse,
    summary="Detalle de un Comprobante de Venta",
    description=(
        "Retorna la cabecera del comprobante con los totales calculados por la base "
        "de datos y el listado de renglones con precios y descuentos históricos."
    ),
)
def obtener_comprobante(nro_comprobante: int):
    comprobante = comprobantes_dal.obtener_comprobante(nro_comprobante)
    if not comprobante:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comprobante {nro_comprobante} no encontrado.",
        )
    return comprobante
