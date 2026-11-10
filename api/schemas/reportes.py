from typing import Optional
from pydantic import BaseModel


class TopVinoResponse(BaseModel):
    cod_vino: int
    nombre: str
    total_botellas: int


class VentasPorSalaResponse(BaseModel):
    id_sala: int
    calle: str
    numero: int
    cod_postal: str
    localidad: str
    monto_total_trimestre: float


class VinoSinStockResponse(BaseModel):
    cod_vino: int
    nombre: str
    stock_deposito: int


class TransportistaActivoResponse(BaseModel):
    cod_transporte: int
    razon_social: str
    cantidad_traslados: int


class TrazabilidadVinoResponse(BaseModel):
    cod_vino: int
    vino: str
    bodega: str
    composicion: str
    maridajes: str
    stock_total: int
