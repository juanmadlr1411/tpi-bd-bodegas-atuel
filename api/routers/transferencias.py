from fastapi import APIRouter, HTTPException, status
from api.schemas.transferencias import (
    TransferenciaCreate,
    RenglonTransferenciaCreate,
    RenglonTransferenciaOut,
    TransferenciaOut,
)
from api.dal import transferencias as dal_transferencias

router = APIRouter(prefix="/transferencias", tags=["Transferencias"])


@router.post("", response_model=TransferenciaOut, status_code=status.HTTP_201_CREATED)
def crear_transferencia_endpoint(payload: TransferenciaCreate):
    return dal_transferencias.crear_transferencia(id_sala=payload.id_sala)


@router.post("/{nro}/renglones", response_model=RenglonTransferenciaOut, status_code=status.HTTP_201_CREATED)
def agregar_renglon_endpoint(nro: int, payload: RenglonTransferenciaCreate):
    return dal_transferencias.agregar_renglon_transferencia(
        nro_transferencia=nro,
        cod_vino=payload.cod_vino,
        cantidad=payload.cantidad,
    )


@router.post("/{nro}/terminar", response_model=TransferenciaOut)
def terminar_transferencia_endpoint(nro: int):
    actualizado = dal_transferencias.terminar_transferencia(nro)
    if not actualizado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La transferencia {nro} no existe.",
        )
    return dal_transferencias.obtener_transferencia(nro)


@router.post("/{nro}/procesar", response_model=TransferenciaOut)
def procesar_transferencia_endpoint(nro: int):
    dal_transferencias.procesar_transferencia(nro)
    return dal_transferencias.obtener_transferencia(nro)


@router.get("/{nro}", response_model=TransferenciaOut)
def obtener_transferencia_endpoint(nro: int):
    transf = dal_transferencias.obtener_transferencia(nro)
    if not transf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La transferencia {nro} no existe.",
        )
    return transf
