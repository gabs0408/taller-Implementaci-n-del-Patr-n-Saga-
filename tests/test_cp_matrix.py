"""Matriz de pruebas de consistencia — Fase 6 del checklist.

Corre los 5 casos de prueba (CP-01 a CP-05) contra el Gateway, en los
dos modos. Requiere el stack levantado: `docker-compose up`.

    pip install pytest httpx
    GATEWAY_URL=http://localhost:8000 pytest tests/test_cp_matrix.py -v

Están marcados @pytest.mark.skip porque el store en memoria de
accounts-service se reinicia en cada `docker-compose up` (dos cuentas
sembradas con saldo fijo — ver services/accounts-service/app/store.py)
y las pruebas necesitan cuentas frescas o un reset entre casos. Cuando
tengan Supabase conectado (Fase 1), reemplacen el fixture `cuentas` por
una que cree/limpie cuentas reales y quiten el skip.
"""
import os
import time

import httpx
import pytest

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8000")
MODOS = ["orquestacion", "coreografia"]


def _esperar_estado_final(transfer_id: str, timeout: float = 20.0) -> str:
    finales = {"CONFIRMADO", "RECHAZADO_FONDOS", "RECHAZADO_RIESGO", "RECHAZADO_RED"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = httpx.get(f"{GATEWAY_URL}/transferencias/{transfer_id}")
        r.raise_for_status()
        estado = r.json()["estado"]
        if estado in finales:
            return estado
        time.sleep(0.5)
    raise TimeoutError(f"transferencia {transfer_id} no llegó a un estado final en {timeout}s")


def _transferir(modo: str, monto: float = 10_000.0, **simulacion) -> str:
    body = {
        "cuenta_origen": "ACC-001",
        "cuenta_destino": "ACC-002",
        "monto": monto,
        "modo": modo,
        "simulacion": simulacion,
    }
    r = httpx.post(f"{GATEWAY_URL}/transferencias", json=body)
    r.raise_for_status()
    return r.json()["transfer_id"]


@pytest.mark.skip(reason="ver docstring del módulo: necesita cuentas frescas por corrida")
@pytest.mark.parametrize("modo", MODOS)
def test_cp01_camino_feliz(modo):
    tid = _transferir(modo)
    assert _esperar_estado_final(tid) == "CONFIRMADO"


@pytest.mark.skip(reason="ver docstring del módulo")
@pytest.mark.parametrize("modo", MODOS)
def test_cp02_fondos_insuficientes(modo):
    tid = _transferir(modo, monto=999_999_999, fondos_insuficientes=True)
    assert _esperar_estado_final(tid) == "RECHAZADO_FONDOS"


@pytest.mark.skip(reason="ver docstring del módulo")
@pytest.mark.parametrize("modo", MODOS)
def test_cp03_fraude(modo):
    tid = _transferir(modo, fraude=True)
    assert _esperar_estado_final(tid) == "RECHAZADO_RIESGO"
    # TODO: además, verificar que el saldo de ACC-001 volvió a su valor original.


@pytest.mark.skip(reason="ver docstring del módulo")
@pytest.mark.parametrize("modo", MODOS)
def test_cp04_caida_pasarela(modo):
    tid = _transferir(modo, timeout_pasarela=True)
    assert _esperar_estado_final(tid) == "RECHAZADO_RED"
    # TODO: verificar que se registraron AMBAS compensaciones (riesgo y débito)
    # en /transferencias/{id} -> pasos.


@pytest.mark.skip(reason="ver docstring del módulo")
@pytest.mark.parametrize("modo", MODOS)
def test_cp05_idempotencia(modo):
    # TODO: enviar la misma X-Idempotency-Key dos veces y verificar que
    # el segundo POST devuelve el mismo transfer_id sin duplicar el débito.
    pass
