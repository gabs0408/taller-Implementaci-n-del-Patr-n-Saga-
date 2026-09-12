from fastapi import APIRouter
from pydantic import BaseModel

from . import core

router = APIRouter(prefix="/riesgo")


class ValidarBody(BaseModel):
    transfer_id: str
    cuenta_origen: str
    monto: float
    simulacion: dict | None = None


class RevertirBody(BaseModel):
    transfer_id: str


@router.post("/validar")
def validar(body: ValidarBody):
    return core.validar(body.transfer_id, body.cuenta_origen, body.monto, body.simulacion)


@router.post("/revertir")
def revertir(body: RevertirBody):
    return core.revertir(body.transfer_id)
