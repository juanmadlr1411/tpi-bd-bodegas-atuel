from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class TransferenciaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_sala: int = Field(
        ...,
        gt=0,
        description="ID de la sala de venta destino"
    )

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
