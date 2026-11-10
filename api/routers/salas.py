from fastapi import APIRouter

from api.dal import salas as salas_dal
from api.schemas.salas import SalaResponse

router = APIRouter(prefix="/salas", tags=["Salas"])


@router.get(
    "",
    response_model=list[SalaResponse],
    summary="Listado de Salas de Venta",
    description="Retorna las salas de venta disponibles con su ubicación y día de cierre.",
)
def listar_salas():
    return salas_dal.listar_salas()
