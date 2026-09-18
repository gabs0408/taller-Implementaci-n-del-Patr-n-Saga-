"""Lógica de negocio del servicio de Riesgo y Antifraude. Compartida
entre app/routes.py (orquestado) y app/events_worker.py (coreografía)."""
from common.idempotency import marcar_procesado, ya_procesado
from common.status_store import registrar_paso, simulate_delay

from . import store


def validar(transfer_id: str, cuenta_origen: str, monto: float, simulacion: dict | None = None) -> dict:
    op = "validar"
    cached = ya_procesado(transfer_id, op)
    if cached is not None:
        return cached

    simulate_delay()
    simulacion = simulacion or {}

    # CP-03: fraude forzado -> rechazo inmediato. No se evaluó ninguna regla
    # real (límite diario / monto máximo viven en store.validar), así que no
    # hay nada que persistir — mismo criterio que fondos_insuficientes en
    # accounts-service.
    if simulacion.get("fraude"):
        resultado = {"ok": False, "motivo": "fraude_simulado"}
        registrar_paso(transfer_id, op, "rechazado", resultado)
        marcar_procesado(transfer_id, op, resultado)
        return resultado

    resultado = store.validar(transfer_id, cuenta_origen, monto)
    registrar_paso(transfer_id, op, "ok" if resultado["ok"] else "rechazado", resultado)
    marcar_procesado(transfer_id, op, resultado)
    return resultado


def revertir(transfer_id: str) -> dict:
    """Anula la aprobación de riesgo (CP-04): resta del acumulado diario de
    la cuenta lo que había sumado la validación aprobada de esta
    transferencia (ver store.revertir)."""
    op = "revertir"
    cached = ya_procesado(transfer_id, op)
    if cached is not None:
        return cached

    simulate_delay()
    store.revertir(transfer_id)
    resultado = {"ok": True}
    registrar_paso(transfer_id, op, "compensado", resultado)
    marcar_procesado(transfer_id, op, resultado)
    return resultado
