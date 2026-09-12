from fastapi import APIRouter
from pydantic import BaseModel

from . import core

router = APIRouter(prefix="/pasarela")


class LiquidarBody(BaseModel):
    transfer_id: str
    cuenta_destino: str
    monto: float
    simulacion: dict | None = None


@router.post("/liquidar")
def liquidar(body: LiquidarBody):
    return core.liquidar(body.transfer_id, body.cuenta_destino, body.monto, body.simulacion)
