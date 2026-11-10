from fastapi import APIRouter, HTTPException, status
from api.schemas.ingresos import (
    IngresoCreate,
    RenglonIngresoCreate,
    RenglonIngresoOut,
    IngresoOut,
)
from api.dal import ingresos as dal_ingresos

router = APIRouter(prefix="/ingresos", tags=["Ingresos"])


@router.post("", response_model=IngresoOut, status_code=status.HTTP_201_CREATED)
def crear_ingreso_endpoint(payload: IngresoCreate):
    return dal_ingresos.crear_ingreso(
        cuit_bodega=payload.cuit_bodega,
        cod_transporte=payload.cod_transporte,
        fecha=payload.fecha,
    )


@router.post("/{cod}/renglones", response_model=RenglonIngresoOut, status_code=status.HTTP_201_CREATED)
def agregar_renglon_ingreso_endpoint(cod: int, payload: RenglonIngresoCreate):
    return dal_ingresos.agregar_renglon_ingreso(
        cod_ingreso=cod,
        cod_vino=payload.cod_vino,
        cantidad=payload.cantidad,
    )


@router.post("/{cod}/terminar", response_model=IngresoOut)
def terminar_ingreso_endpoint(cod: int):
    actualizado = dal_ingresos.terminar_ingreso(cod)
    if not actualizado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El ingreso {cod} no existe.",
        )
    return dal_ingresos.obtener_ingreso(cod)


@router.post("/{cod}/procesar", response_model=IngresoOut)
def procesar_ingreso_endpoint(cod: int):
    dal_ingresos.procesar_ingreso(cod)
    return dal_ingresos.obtener_ingreso(cod)


@router.get("/{cod}", response_model=IngresoOut)
def obtener_ingreso_endpoint(cod: int):
    ingreso = dal_ingresos.obtener_ingreso(cod)
    if not ingreso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El ingreso {cod} no existe.",
        )
    return ingreso
