"""Lógica de negocio del servicio de Riesgo y Antifraude. Compartida
entre app/routes.py (orquestado) y app/events_worker.py (coreografía)."""
from common.idempotency import marcar_procesado, ya_procesado
from common.status_store import registrar_paso, simulate_delay

from . import rules


def validar(transfer_id: str, cuenta_origen: str, monto: float, simulacion: dict | None = None) -> dict:
    op = "validar"
    cached = ya_procesado(transfer_id, op)
    if cached is not None:
        return cached

    simulate_delay()
    aprobado, motivo = rules.evaluar(monto, simulacion)
    resultado = {"ok": aprobado, "motivo": motivo}
    registrar_paso(transfer_id, op, "ok" if aprobado else "rechazado", resultado)
    marcar_procesado(transfer_id, op, resultado)
    return resultado


def revertir(transfer_id: str) -> dict:
    """Anula la aprobación de riesgo (CP-04). No hay estado persistente
    que revertir —la aprobación no bloqueaba fondos—, pero se registra
    igual en la bitácora: la rúbrica exige evidenciar el paso."""
    op = "revertir"
    cached = ya_procesado(transfer_id, op)
    if cached is not None:
        return cached

    simulate_delay()
    resultado = {"ok": True}
    registrar_paso(transfer_id, op, "compensado", resultado)
    marcar_procesado(transfer_id, op, resultado)
    return resultado
