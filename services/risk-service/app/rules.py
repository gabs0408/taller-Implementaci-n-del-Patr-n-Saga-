"""Reglas de validación operativa (Fase 1, f1-2).

TODO (Fase 1): mover el límite diario a Supabase (por cuenta, con
acumulado del día) en vez de una constante — esto es un placeholder
para que el servicio arranque ya.
"""

LIMITE_DIARIO = 50_000_000.0


def evaluar(monto: float, simulacion: dict | None = None) -> tuple[bool, str | None]:
    """Devuelve (aprobado, motivo_rechazo)."""
    simulacion = simulacion or {}

    if simulacion.get("fraude"):
        return False, "fraude_simulado"

    if monto > LIMITE_DIARIO:
        return False, "excede_limite_diario"

    return True, None
