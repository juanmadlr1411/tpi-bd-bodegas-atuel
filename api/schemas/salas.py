from pydantic import BaseModel


class SalaResponse(BaseModel):
    id_sala: int
    calle: str
    numero: int
    dia_cierre: str
    cod_postal: str
    localidad_nombre: str
