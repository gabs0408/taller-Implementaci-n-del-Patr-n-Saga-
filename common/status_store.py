"""Bitácora de auditoría compartida (Fase 2 f2-8, Fase 4 f4-4).

Cada paso de la Saga —en cualquiera de los dos modos— se registra
aquí para que el frontend (Fase 5) y el Prefect UI / dashboard
(Fase 4) puedan mostrar el avance en tiempo real y las
compensaciones. Estructura en Redis:

  transferencia:{transfer_id}:estado   -> string (PENDIENTE, DEBITADO, ...)
  transferencia:{transfer_id}:pasos    -> lista JSON de {paso, resultado, ts}
"""
import json
import time
from typing import Optional

from .redis_client import get_redis

STEP_DELAY_MS = int(__import__("os").environ.get("STEP_DELAY_MS", "3000"))


def simulate_delay() -> None:
    """Delay configurable (2-4s) pedido explícitamente por la Fase 4 /
    Criterio 3 de la rúbrica, para poder *ver* cada paso y su
    compensación en vez de una caja negra."""
    time.sleep(STEP_DELAY_MS / 1000)


def set_estado(transfer_id: str, estado: str) -> None:
    get_redis().set(f"transferencia:{transfer_id}:estado", estado)


def get_estado(transfer_id: str) -> Optional[str]:
    return get_redis().get(f"transferencia:{transfer_id}:estado")


def registrar_paso(transfer_id: str, paso: str, resultado: str, detalle: dict | None = None) -> None:
    """Agrega una línea a la bitácora: p.ej. ('debitar', 'ok', {...}) o
    ('debitar', 'compensado', {...})."""
    entry = {
        "paso": paso,
        "resultado": resultado,
        "detalle": detalle or {},
        "ts": time.time(),
    }
    get_redis().rpush(f"transferencia:{transfer_id}:pasos", json.dumps(entry))


def get_pasos(transfer_id: str) -> list[dict]:
    raw = get_redis().lrange(f"transferencia:{transfer_id}:pasos", 0, -1)
    return [json.loads(r) for r in raw]
