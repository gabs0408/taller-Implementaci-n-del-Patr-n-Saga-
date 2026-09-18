"""Reglas de validación de riesgo — puras, sin acceso a datos.

Los valores (límite diario acumulado, monto máximo por transferencia) son
configurables por cuenta en risk.limites (ver app/store.py); esta función
solo aplica la lógica una vez que esos números ya se resolvieron, así que se
puede probar sin base de datos.

El switch de fraude (simulacion.fraude) no pasa por acá — se resuelve en
app/core.py antes de llegar a este módulo, igual que fondos_insuficientes en
accounts-service: un rechazo forzado no evalúa ninguna regla real.
"""


def evaluar(monto: float, monto_maximo: float, limite_diario: float, acumulado_hoy: float) -> tuple[bool, str | None]:
    """Devuelve (aprobado, motivo_rechazo)."""
    if monto > monto_maximo:
        return False, "excede_monto_maximo"

    if acumulado_hoy + monto > limite_diario:
        return False, "excede_limite_diario"

    return True, None
