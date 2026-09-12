"""Lógica de negocio del servicio de Cuentas y Saldos.

Único lugar donde vive esta lógica (regla 3 de CONTEXT.md): tanto
app/routes.py (modo orquestado) como app/events_worker.py (modo
coreografía) llaman estas mismas funciones. No dupliques la lógica en
el listener de eventos.
"""
from common.idempotency import marcar_procesado, ya_procesado
from common.status_store import registrar_paso, simulate_delay

from . import store


def debitar(transfer_id: str, cuenta_id: str, monto: float, simulacion: dict | None = None) -> dict:
    op = "debitar"
    cached = ya_procesado(transfer_id, op)
    if cached is not None:
        return cached

    simulate_delay()
    simulacion = simulacion or {}
    saldo = store.get_saldo(cuenta_id)

    # CP-02: fondos insuficientes -> rechazo inmediato, sin reversas
    # (todavía no se aplicó nada, así que no hay nada que compensar).
    if simulacion.get("fondos_insuficientes") or monto > saldo:
        resultado = {"ok": False, "motivo": "fondos_insuficientes"}
        registrar_paso(transfer_id, op, "rechazado", resultado)
        marcar_procesado(transfer_id, op, resultado)
        return resultado

    store.set_saldo(cuenta_id, saldo - monto)
    resultado = {"ok": True, "saldo_restante": saldo - monto}
    registrar_paso(transfer_id, op, "ok", resultado)
    marcar_procesado(transfer_id, op, resultado)
    return resultado


def acreditar(transfer_id: str, cuenta_id: str, monto: float) -> dict:
    op = "acreditar"
    cached = ya_procesado(transfer_id, op)
    if cached is not None:
        return cached

    simulate_delay()
    saldo = store.get_saldo(cuenta_id)
    store.set_saldo(cuenta_id, saldo + monto)
    resultado = {"ok": True, "saldo_restante": saldo + monto}
    registrar_paso(transfer_id, op, "ok", resultado)
    marcar_procesado(transfer_id, op, resultado)
    return resultado


def revertir_debito(transfer_id: str, cuenta_id: str, monto: float) -> dict:
    """Transacción de compensación: reintegra el 100% del débito
    (CP-03, CP-04)."""
    op = "revertir_debito"
    cached = ya_procesado(transfer_id, op)
    if cached is not None:
        return cached

    simulate_delay()
    saldo = store.get_saldo(cuenta_id)
    store.set_saldo(cuenta_id, saldo + monto)
    resultado = {"ok": True, "saldo_restante": saldo + monto}
    registrar_paso(transfer_id, op, "compensado", resultado)
    marcar_procesado(transfer_id, op, resultado)
    return resultado
