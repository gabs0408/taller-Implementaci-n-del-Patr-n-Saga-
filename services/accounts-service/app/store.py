"""Almacenamiento de saldos — Servicio Cuentas y Saldos (Ledger).

Placeholder en memoria para que el servicio arranque de una vez.

TODO (Fase 1, f1-1 / f1-4): reemplazar por Supabase (proyecto o
esquema propio de este servicio — no compartir tablas con
risk-service ni clearing-service, es lo que evalúa el Criterio 5).
"""
import threading

_lock = threading.Lock()

# Cuentas semilla para poder probar CP-01..CP-05 sin frontend todavía.
_saldos: dict[str, float] = {
    "ACC-001": 1_000_000.0,
    "ACC-002": 500_000.0,
}


def get_saldo(cuenta_id: str) -> float:
    with _lock:
        return _saldos.get(cuenta_id, 0.0)


def set_saldo(cuenta_id: str, nuevo_saldo: float) -> None:
    with _lock:
        _saldos[cuenta_id] = nuevo_saldo
