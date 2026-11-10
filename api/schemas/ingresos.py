from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class IngresoCreate(BaseModel):
    cuit_bodega: str = Field(..., min_length=11, max_length=11, pattern=r"^[0-9]{11}$")
    cod_transporte: Optional[int] = Field(None, gt=0)
    id_transportista: Optional[int] = Field(None, gt=0)
    fecha: Optional[date] = None

    @model_validator(mode="after")
    def validar_transportista(self):
        if self.cod_transporte is None and self.id_transportista is not None:
            self.cod_transporte = self.id_transportista
        if self.cod_transporte is None:
            raise ValueError("Se debe especificar 'cod_transporte' (o 'id_transportista').")
        return self


class RenglonIngresoCreate(BaseModel):
    cod_vino: int = Field(..., gt=0, description="Código del vino ingresado")
    cantidad: int = Field(..., gt=0, description="Cantidad de botellas (mayor a 0)")


class RenglonIngresoOut(BaseModel):
    cod_ingreso: int
    cod_vino: int
    nombre_vino: Optional[str] = None
    cantidad: int


class IngresoOut(BaseModel):
    cod_ingreso: int
    fecha: date
    estado: str
    cod_transporte: int
    cuit_bodega: str
    renglones: list[RenglonIngresoOut] = []
