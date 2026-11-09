from datetime import date
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator

TipoClienteEnum = Literal["socio", "distribuidor", "exportador"]


class ClienteBase(BaseModel):
    nombre_razon_social: str = Field(..., max_length=120, description="Nombre o razón social del cliente")
    tipo_documento: str = Field(..., max_length=10, description="Tipo de documento (DNI, CUIT, PAS)")
    nro_documento: str = Field(..., max_length=20, description="Número de documento sin puntos ni guiones")
    direccion: str = Field(..., max_length=150, description="Dirección fiscal o de entrega")
    cod_postal: str = Field(..., max_length=10, description="Código postal asociado a una localidad existente")
    tipo_cliente: TipoClienteEnum = Field(..., description="Tipo de cliente (socio, distribuidor, exportador)")


class ClienteCreate(ClienteBase):
    # Campos específicos según subtipo
    zona_cobertura: Optional[str] = Field(None, max_length=100, description="Obligatorio para distribuidor")
    nro_habilitacion: Optional[str] = Field(None, max_length=40, description="Obligatorio para distribuidor")
    pais_destino: Optional[str] = Field(None, max_length=80, description="Obligatorio para exportador")

    @model_validator(mode="after")
    def validar_subtipo(self) -> "ClienteCreate":
        if self.tipo_cliente == "distribuidor":
            if not self.zona_cobertura or not self.nro_habilitacion:
                raise ValueError("Para cliente 'distribuidor' debe proveer 'zona_cobertura' y 'nro_habilitacion'")
        elif self.tipo_cliente == "exportador":
            if not self.pais_destino:
                raise ValueError("Para cliente 'exportador' debe proveer 'pais_destino'")
        return self


class ClienteUpdate(BaseModel):
    nombre_razon_social: Optional[str] = Field(None, max_length=120)
    direccion: Optional[str] = Field(None, max_length=150)
    cod_postal: Optional[str] = Field(None, max_length=10)
    # Campos específicos
    zona_cobertura: Optional[str] = Field(None, max_length=100)
    nro_habilitacion: Optional[str] = Field(None, max_length=40)
    pais_destino: Optional[str] = Field(None, max_length=80)


class ClienteResponse(BaseModel):
    id_cliente: int
    nombre_razon_social: str
    tipo_documento: str
    nro_documento: str
    direccion: str
    cod_postal: str
    localidad_nombre: Optional[str] = None
    fecha_alta: date
    tipo_cliente: str
    porcentaje_descuento: float
    # Subtipo
    zona_cobertura: Optional[str] = None
    nro_habilitacion: Optional[str] = None
    pais_destino: Optional[str] = None


class PaginatedClientesResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ClienteResponse]
