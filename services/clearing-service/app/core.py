"""Lógica de negocio de la Pasarela Interbancaria (Clearing Gateway).
Simula la liquidación externa de fondos — no tiene reversa propia: si
falla, la compensación corre aguas arriba (riesgo y cuentas)."""
from common.idempotency import marcar_procesado, ya_procesado
from common.status_store import registrar_paso, simulate_delay


def liquidar(transfer_id: str, cuenta_destino: str, monto: float, simulacion: dict | None = None) -> dict:
    op = "liquidar"
    cached = ya_procesado(transfer_id, op)
    if cached is not None:
        return cached

    simulate_delay()
    simulacion = simulacion or {}

    # CP-04: switch de timeout / caída de red en la pasarela externa.
    if simulacion.get("timeout_pasarela"):
        resultado = {"ok": False, "motivo": "timeout_pasarela"}
        registrar_paso(transfer_id, op, "fallido", resultado)
        marcar_procesado(transfer_id, op, resultado)
        return resultado

    resultado = {"ok": True, "cuenta_destino": cuenta_destino, "monto": monto}
    registrar_paso(transfer_id, op, "ok", resultado)
    marcar_procesado(transfer_id, op, resultado)
    return resultado
