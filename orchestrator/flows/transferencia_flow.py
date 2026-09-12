"""Flow de Prefect — Saga Orquestada (Fase 2, Criterio 1 · 40%).

Un coordinador central llama explícitamente a cada servicio y, ante un
fallo, dispara las compensaciones en orden inverso. Compárese con
services/*/app/events_worker.py, que implementa la misma secuencia sin
coordinador central (Fase 3).
"""
from prefect import flow, task

from common.models import CONFIRMADO, DEBITADO, LIQUIDADO, PENDIENTE, RECHAZADO_FONDOS, RECHAZADO_RED, RECHAZADO_RIESGO, RIESGO_OK
from common.status_store import set_estado

from . import clients

# Los @task envuelven las llamadas HTTP para que cada paso —éxito,
# fallo y compensación— quede registrado como una unidad en el
# Prefect UI (Fase 4).


@task(name="debitar")
def debitar_task(transfer_id, cuenta_origen, monto, simulacion):
    return clients.debitar(transfer_id, cuenta_origen, monto, simulacion)


@task(name="validar_riesgo")
def validar_riesgo_task(transfer_id, cuenta_origen, monto, simulacion):
    return clients.validar_riesgo(transfer_id, cuenta_origen, monto, simulacion)


@task(name="liquidar")
def liquidar_task(transfer_id, cuenta_destino, monto, simulacion):
    return clients.liquidar(transfer_id, cuenta_destino, monto, simulacion)


@task(name="acreditar")
def acreditar_task(transfer_id, cuenta_destino, monto):
    return clients.acreditar(transfer_id, cuenta_destino, monto)


@task(name="revertir_debito")
def revertir_debito_task(transfer_id, cuenta_origen, monto):
    return clients.revertir_debito(transfer_id, cuenta_origen, monto)


@task(name="revertir_riesgo")
def revertir_riesgo_task(transfer_id):
    return clients.revertir_riesgo(transfer_id)


@flow(name="transferencia-saga-orquestada")
def transferencia_saga(transfer_id: str, cuenta_origen: str, cuenta_destino: str, monto: float, simulacion: dict | None = None) -> str:
    simulacion = simulacion or {}
    set_estado(transfer_id, PENDIENTE)

    debito = debitar_task(transfer_id, cuenta_origen, monto, simulacion)
    if not debito["ok"]:
        # CP-02: nada que compensar, nada se aplicó todavía.
        set_estado(transfer_id, RECHAZADO_FONDOS)
        return RECHAZADO_FONDOS
    set_estado(transfer_id, DEBITADO)

    riesgo = validar_riesgo_task(transfer_id, cuenta_origen, monto, simulacion)
    if not riesgo["ok"]:
        # CP-03: compensación en reversa -> solo el débito.
        revertir_debito_task(transfer_id, cuenta_origen, monto)
        set_estado(transfer_id, RECHAZADO_RIESGO)
        return RECHAZADO_RIESGO
    set_estado(transfer_id, RIESGO_OK)

    liquidacion = liquidar_task(transfer_id, cuenta_destino, monto, simulacion)
    if not liquidacion["ok"]:
        # CP-04: compensación en reversa -> riesgo, luego débito (orden inverso estricto).
        revertir_riesgo_task(transfer_id)
        revertir_debito_task(transfer_id, cuenta_origen, monto)
        set_estado(transfer_id, RECHAZADO_RED)
        return RECHAZADO_RED
    set_estado(transfer_id, LIQUIDADO)

    acreditar_task(transfer_id, cuenta_destino, monto)
    set_estado(transfer_id, CONFIRMADO)
    return CONFIRMADO
