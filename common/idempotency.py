"""Idempotencia a nivel de cada microservicio (Fase 1, tarea f1-7 —
Criterio 5 de la rúbrica, distinto de la idempotencia del Gateway).

Antes de aplicar un débito/crédito/liquidación, cada servicio marca
`(transfer_id, operacion)` como procesado. Si el mismo par llega de
nuevo (reintento, CP-05), se devuelve el resultado ya guardado en vez
de aplicar la operación dos veces.
"""
import json
from typing import Optional

from .redis_client import get_redis

TTL_SECONDS = 60 * 60 * 24  # 24h es más que suficiente para el taller


def ya_procesado(transfer_id: str, operacion: str) -> Optional[dict]:
    raw = get_redis().get(f"idemp:{transfer_id}:{operacion}")
    return json.loads(raw) if raw else None


def marcar_procesado(transfer_id: str, operacion: str, resultado: dict) -> None:
    get_redis().set(
        f"idemp:{transfer_id}:{operacion}",
        json.dumps(resultado),
        ex=TTL_SECONDS,
    )
