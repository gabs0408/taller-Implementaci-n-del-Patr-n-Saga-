"""Endpoints REST — llamados por el orquestador en modo Orquestación.
Ver CONTEXT.md sección 3 para el contrato completo."""
from fastapi import APIRouter
from pydantic import BaseModel

from . import core

router = APIRouter(prefix="/cuentas")


class DebitarBody(BaseModel):
    transfer_id: str
    monto: float
    simulacion: dict | None = None


class MontoBody(BaseModel):
    transfer_id: str
    monto: float


@router.post("/{cuenta_id}/debitar")
def debitar(cuenta_id: str, body: DebitarBody):
    return core.debitar(body.transfer_id, cuenta_id, body.monto, body.simulacion)


@router.post("/{cuenta_id}/acreditar")
def acreditar(cuenta_id: str, body: MontoBody):
    return core.acreditar(body.transfer_id, cuenta_id, body.monto)


@router.post("/{cuenta_id}/revertir-debito")
def revertir_debito(cuenta_id: str, body: MontoBody):
    return core.revertir_debito(body.transfer_id, cuenta_id, body.monto)


@router.get("/{cuenta_id}/saldo")
def saldo(cuenta_id: str):
    from . import store
    return {"cuenta_id": cuenta_id, "saldo": store.get_saldo(cuenta_id)}
