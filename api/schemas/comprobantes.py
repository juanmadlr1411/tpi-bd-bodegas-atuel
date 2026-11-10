from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class RenglonComprobanteCreate(BaseModel):
    cod_vino: int = Field(..., gt=0, description="Código del vino vendido")
    cantidad: int = Field(..., gt=0, description="Cantidad de botellas vendidas (RN-15)")


class ComprobanteCreate(BaseModel):
    id_cliente: int = Field(..., gt=0, description="Cliente comprador")
    id_sala: int = Field(..., gt=0, description="Sala de venta donde se emite el comprobante")
    renglones: list[RenglonComprobanteCreate] = Field(
        ...,
        min_length=1,
        description="Renglones de la venta (un vino no puede repetirse dentro del mismo comprobante)",
    )

    @model_validator(mode="after")
    def validar_vinos_unicos(self) -> "ComprobanteCreate":
        codigos = [r.cod_vino for r in self.renglones]
        if len(codigos) != len(set(codigos)):
            raise ValueError("Un mismo vino no puede aparecer en más de un renglón del comprobante.")
        return self


class RenglonComprobanteResponse(BaseModel):
    cod_vino: int
    nombre_vino: Optional[str] = None
    cantidad: int
    precio_unitario: float
    descuento: float
    subtotal: float


class ComprobanteResponse(BaseModel):
    nro_comprobante: int
    fecha: date
    id_cliente: int
    cliente_nombre: Optional[str] = None
    id_sala: int
    subtotal: float
    descuento: float
    total: float
    renglones: list[RenglonComprobanteResponse] = []
