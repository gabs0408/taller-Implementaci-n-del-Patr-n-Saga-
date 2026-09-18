"""Bitácora de auditoría compartida (Fase 2 f2-8, Fase 4 f4-4).

Cada paso de la Saga —en cualquiera de los dos modos— se registra
aquí para que el frontend (Fase 5) y el Prefect UI / dashboard
(Fase 4) puedan mostrar el avance en tiempo real y las
compensaciones. Estructura en Redis (rápida, para polling):

  transferencia:{transfer_id}:estado   -> string (PENDIENTE, DEBITADO, ...)
  transferencia:{transfer_id}:pasos    -> lista JSON de {paso, resultado, ts}

Cada `set_estado()` además inserta una fila en `bitacora.transiciones`
(Postgres — ver common/schema_bitacora.sql), que es el registro DURABLE de
auditoría: a diferencia del `estado` en Redis (que solo guarda el valor
actual y se pierde si ese contenedor se reinicia, sin volumen configurado),
esta tabla conserva cada transición con estado anterior, estado nuevo y
timestamp, consultable con SQL directo aunque Redis se haya vaciado.

Si `AUDIT_DATABASE_URL` no está configurada, `set_estado`/`get_transiciones`
degradan con gracia (no rompen el resto del sistema) — igual que el patrón
de DATABASE_URL en cada microservicio.
"""
import json
import os
import time
from typing import Optional

import psycopg

from .redis_client import get_redis

STEP_DELAY_MS = int(os.environ.get("STEP_DELAY_MS", "3000"))
AUDIT_DATABASE_URL = os.environ.get("AUDIT_DATABASE_URL", "")


def simulate_delay() -> None:
    """Delay configurable (2-4s) pedido explícitamente por la Fase 4 /
    Criterio 3 de la rúbrica, para poder *ver* cada paso y su
    compensación en vez de una caja negra."""
    time.sleep(STEP_DELAY_MS / 1000)


def _registrar_transicion(transfer_id: str, estado_anterior: Optional[str], estado_nuevo: str, motivo: Optional[str]) -> None:
    if not AUDIT_DATABASE_URL:
        return
    try:
        with psycopg.connect(AUDIT_DATABASE_URL) as conn:
            conn.execute(
                """insert into bitacora.transiciones
                   (transfer_id, estado_anterior, estado_nuevo, motivo)
                   values (%s, %s, %s, %s)""",
                (transfer_id, estado_anterior, estado_nuevo, motivo),
            )
    except Exception as exc:  # noqa: BLE001
        # La auditoría durable no debe tumbar la Saga si Postgres no
        # responde — Redis (la ruta rápida) ya quedó actualizado arriba.
        print(f"[status_store] no se pudo persistir la transición de {transfer_id}: {exc}")


def set_estado(transfer_id: str, estado: str, motivo: Optional[str] = None) -> None:
    """`motivo` es la causa del fallo (p.ej. "fraude_simulado",
    "timeout_pasarela") cuando `estado` es un rechazo — quien llama a esta
    función ya tiene ese dato a mano (viene del resultado del microservicio
    o del payload del evento), así que no hace falta que la bitácora lo
    adivine después."""
    anterior = get_estado(transfer_id)
    get_redis().set(f"transferencia:{transfer_id}:estado", estado)
    _registrar_transicion(transfer_id, anterior, estado, motivo)


def get_estado(transfer_id: str) -> Optional[str]:
    return get_redis().get(f"transferencia:{transfer_id}:estado")


def get_transiciones(transfer_id: str) -> list[dict]:
    """Historial durable de transiciones desde Postgres — distinto de
    get_pasos() (Redis, operación por operación); esto es específicamente
    la máquina de estados (estado_anterior -> estado_nuevo) con timestamp."""
    if not AUDIT_DATABASE_URL:
        return []
    with psycopg.connect(AUDIT_DATABASE_URL) as conn:
        rows = conn.execute(
            """select estado_anterior, estado_nuevo, motivo, creado_en
               from bitacora.transiciones
               where transfer_id = %s
               order by creado_en asc""",
            (transfer_id,),
        ).fetchall()
    return [
        {"estado_anterior": r[0], "estado_nuevo": r[1], "motivo": r[2], "ts": r[3].isoformat()}
        for r in rows
    ]


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
