"""Lógica de negocio de la Pasarela Interbancaria (Clearing Gateway).
Simula la liquidación externa de fondos — no tiene reversa propia: si
falla, la compensación corre aguas arriba (riesgo y cuentas)."""
from common.idempotency import marcar_procesado, ya_procesado
from common.status_store import registrar_paso, simulate_delay

from . import store


def liquidar(transfer_id: str, cuenta_destino: str, monto: float, simulacion: dict | None = None) -> dict:
    op = "liquidar"
    cached = ya_procesado(transfer_id, op)
    if cached is not None:
        return cached

    simulate_delay()
    simulacion = simulacion or {}

    # CP-04: switch de timeout / caída de red en la pasarela externa. A
    # diferencia de fondos_insuficientes/fraude en accounts-service y
    # risk-service, acá sí se persiste el intento fallido en
    # clearing.liquidaciones — un timeout real de una pasarela externa es
    # un intento que de verdad ocurrió, no una validación previa que cortó
    # antes de hacer nada.
    ok = not simulacion.get("timeout_pasarela")
    motivo = None if ok else "timeout_pasarela"

    resultado = store.liquidar(transfer_id, cuenta_destino, monto, ok, motivo)
    registrar_paso(transfer_id, op, "ok" if resultado["ok"] else "fallido", resultado)
    marcar_procesado(transfer_id, op, resultado)
    return resultado
