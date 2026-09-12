"""Bus de eventos para la Saga Coreografiada (Fase 3), sobre Redis
Streams. Un único stream (`novabank:transferencias`) con el nombre
del evento en el campo `tipo` — simplifica el scaffold; si el equipo
prefiere un stream por tipo de evento, ajusten esto y actualicen
CONTEXT.md.

Eventos válidos (CONTEXT.md sección 3):
TransferenciaSolicitada, SaldoDebitado, RiesgoAprobado, RiesgoRechazado,
LiquidacionConfirmada, TransferenciaFallida, CompensacionEjecutada.
"""
import json
import time
from typing import Callable

from .redis_client import get_redis

STREAM = "novabank:transferencias"


def publicar(tipo: str, payload: dict) -> None:
    data = {"tipo": tipo, "payload": json.dumps(payload), "ts": str(time.time())}
    get_redis().xadd(STREAM, data)


def consumir(group: str, consumer_name: str, handlers: dict[str, Callable[[dict], None]]) -> None:
    """Bucle bloqueante: crea el consumer group si no existe y despacha
    cada evento al handler registrado en `handlers` por tipo. Cada
    servicio corre esto en su propio proceso —ver app/events_worker.py
    de cada microservicio— para no bloquear su API REST.

    handlers: {"TransferenciaSolicitada": funcion, ...}
    """
    r = get_redis()
    try:
        r.xgroup_create(STREAM, group, id="0", mkstream=True)
    except Exception:
        pass  # el grupo ya existe

    print(f"[events] {consumer_name} escuchando '{STREAM}' (grupo={group})")
    while True:
        resp = r.xreadgroup(group, consumer_name, {STREAM: ">"}, count=10, block=5000)
        if not resp:
            continue
        for _stream, messages in resp:
            for msg_id, fields in messages:
                tipo = fields.get("tipo")
                handler = handlers.get(tipo)
                if handler:
                    try:
                        handler(json.loads(fields["payload"]))
                    except Exception as exc:  # noqa: BLE001
                        print(f"[events] error procesando {tipo} ({msg_id}): {exc}")
                r.xack(STREAM, group, msg_id)
