from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


TipoVinoEnum = Literal["tinto", "blanco", "rosado", "espumante"]


class ComposicionItemCreate(BaseModel):
    id_cepa: int = Field(..., description="ID de la cepa")
    porcentaje: float = Field(..., gt=0, le=100, description="Porcentaje de corte de la cepa (1 a 100)")


class ComposicionItemResponse(BaseModel):
    id_cepa: int
    nombre_cepa: str
    tipo_cepa: Optional[str] = None
    porcentaje: float


class MaridajeItemResponse(BaseModel):
    id_maridaje: int
    nombre: str
    temperatura_servicio: int


class VinoBase(BaseModel):
    nombre: str = Field(..., max_length=80, description="Nombre comercial del vino")
    tipo: TipoVinoEnum = Field(..., description="Tipo de vino (tinto, blanco, rosado, espumante)")
    anada: int = Field(..., ge=1990, le=2100, description="Año de cosecha/añada")
    volumen_ml: int = Field(..., description="Volumen en mililitros (187, 375, 750, 1500, 3000)")
    graduacion: float = Field(..., ge=5.0, le=20.0, description="Graduación alcohólica en grados (5.0 a 20.0)")
    precio: float = Field(..., gt=0, description="Precio unitario (RN-01: precio > 0)")
    cuit_bodega: str = Field(..., min_length=11, max_length=11, description="CUIT de la bodega productora")

    @field_validator("volumen_ml")
    @classmethod
    def validar_volumen(cls, v: int) -> int:
        volumenes_validos = {187, 375, 750, 1500, 3000}
        if v not in volumenes_validos:
            raise ValueError(f"Volumen inválido. Debe ser uno de {volumenes_validos}")
        return v


class VinoCreate(VinoBase):
    composicion: list[ComposicionItemCreate] = Field(
        ...,
        min_length=1,
        description="Composición varietal del vino (la suma debe ser 100% en BD)",
    )
    maridajes: list[int] = Field(
        default=[],
        description="Lista opcional de IDs de maridaje recomendados",
    )


class VinoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=80)
    tipo: Optional[TipoVinoEnum] = None
    anada: Optional[int] = Field(None, ge=1990, le=2100)
    volumen_ml: Optional[int] = None
    graduacion: Optional[float] = Field(None, ge=5.0, le=20.0)
    precio: Optional[float] = Field(None, gt=0)
    cuit_bodega: Optional[str] = Field(None, min_length=11, max_length=11)

    @field_validator("volumen_ml")
    @classmethod
    def validar_volumen(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in {187, 375, 750, 1500, 3000}:
            raise ValueError("Volumen inválido. Debe ser uno de {187, 375, 750, 1500, 3000}")
        return v


class VinoListItem(BaseModel):
    cod_vino: int
    nombre: str
    tipo: str
    anada: int
    volumen_ml: int
    graduacion: float
    precio: float
    cuit_bodega: str
    bodega_razon_social: Optional[str] = None


class VinoDetalleResponse(VinoListItem):
    composicion: list[ComposicionItemResponse] = []
    maridajes: list[MaridajeItemResponse] = []


class PaginatedVinosResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[VinoListItem]

