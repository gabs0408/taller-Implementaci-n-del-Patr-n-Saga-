"""Clientes HTTP hacia los 3 microservicios de dominio, usados por el
flow de Prefect (modo Orquestación)."""
import os

import httpx

ACCOUNTS_URL = os.environ.get("ACCOUNTS_URL", "http://accounts-service:8000")
RISK_URL = os.environ.get("RISK_URL", "http://risk-service:8000")
CLEARING_URL = os.environ.get("CLEARING_URL", "http://clearing-service:8000")

TIMEOUT = 15.0  # cada paso incluye su propio delay simulado (2-4s)


def debitar(transfer_id: str, cuenta_origen: str, monto: float, simulacion: dict) -> dict:
    r = httpx.post(
        f"{ACCOUNTS_URL}/cuentas/{cuenta_origen}/debitar",
        json={"transfer_id": transfer_id, "monto": monto, "simulacion": simulacion},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def acreditar(transfer_id: str, cuenta_destino: str, monto: float) -> dict:
    r = httpx.post(
        f"{ACCOUNTS_URL}/cuentas/{cuenta_destino}/acreditar",
        json={"transfer_id": transfer_id, "monto": monto},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def revertir_debito(transfer_id: str, cuenta_origen: str, monto: float) -> dict:
    r = httpx.post(
        f"{ACCOUNTS_URL}/cuentas/{cuenta_origen}/revertir-debito",
        json={"transfer_id": transfer_id, "monto": monto},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def validar_riesgo(transfer_id: str, cuenta_origen: str, monto: float, simulacion: dict) -> dict:
    r = httpx.post(
        f"{RISK_URL}/riesgo/validar",
        json={"transfer_id": transfer_id, "cuenta_origen": cuenta_origen, "monto": monto, "simulacion": simulacion},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def revertir_riesgo(transfer_id: str) -> dict:
    r = httpx.post(f"{RISK_URL}/riesgo/revertir", json={"transfer_id": transfer_id}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def liquidar(transfer_id: str, cuenta_destino: str, monto: float, simulacion: dict) -> dict:
    r = httpx.post(
        f"{CLEARING_URL}/pasarela/liquidar",
        json={"transfer_id": transfer_id, "cuenta_destino": cuenta_destino, "monto": monto, "simulacion": simulacion},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()
