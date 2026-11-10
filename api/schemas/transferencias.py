from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class TransferenciaCreate(BaseModel):
    id_sala: int = Field(..., gt=0, description="ID de la sala de venta destino")
    id_transportista: Optional[int] = Field(None, gt=0, description="Opcional: ID del transportista")


class RenglonTransferenciaCreate(BaseModel):
    cod_vino: int = Field(..., gt=0, description="Código del vino a transferir")
    cantidad: int = Field(..., gt=0, description="Cantidad de botellas (mayor a 0)")


class RenglonTransferenciaOut(BaseModel):
    nro_transferencia: int
    cod_vino: int
    nombre_vino: Optional[str] = None
    cantidad: int


class TransferenciaOut(BaseModel):
    nro_transferencia: int
    id_sala: int
    fecha_confeccion: date
    estado: str
    renglones: list[RenglonTransferenciaOut] = []
