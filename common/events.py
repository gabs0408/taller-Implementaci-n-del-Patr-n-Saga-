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

import redis as redis_lib

from .redis_client import get_redis

STREAM = "novabank:transferencias"


def publicar(tipo: str, payload: dict) -> None:
    data = {"tipo": tipo, "payload": json.dumps(payload), "ts": str(time.time())}
    get_redis().xadd(STREAM, data)


def leer_eventos(transfer_id: str, count: int = 5000) -> list[dict]:
    """Trazabilidad para Coreografía — el equivalente al Prefect UI, pero
    leyendo el bus en vez de un orquestador: no hay flow run que preguntar
    (nadie coordina), así que la traza de una transferencia es literalmente
    la secuencia de eventos que pasaron por el stream con su transfer_id.

    XRANGE no filtra por campo de payload (Redis Streams no lo soporta),
    así que se trae el stream entero y se filtra acá — aceptable para el
    volumen de este taller, no para un stream de producción con millones
    de entradas."""
    entradas = get_redis().xrange(STREAM, count=count)
    eventos = []
    for msg_id, fields in entradas:
        payload = json.loads(fields["payload"])
        if payload.get("transfer_id") == transfer_id:
            eventos.append({
                "id": msg_id,
                "tipo": fields["tipo"],
                "payload": payload,
                "ts": float(fields["ts"]),
            })
    return eventos


def consumir(group: str, consumer_name: str, handlers: dict[str, Callable[[dict], None]]) -> None:
    """Bucle bloqueante: crea el consumer group si no existe y despacha
    cada evento al handler registrado en `handlers` por tipo. Cada
    servicio corre esto en su propio proceso —ver app/events_worker.py
    de cada microservicio— para no bloquear su API REST.

    handlers: {"TransferenciaSolicitada": funcion, ...}
    """
    r = get_redis()

    def _asegurar_grupo() -> None:
        try:
            r.xgroup_create(STREAM, group, id="0", mkstream=True)
        except Exception:
            pass  # el grupo ya existe

    def _procesar(resp) -> None:
        """Solo hace XACK si el handler terminó sin lanzar excepción. Antes
        se confirmaba siempre, pasara lo que pasara — así, un handler que
        fallaba justo cuando Redis se estaba reconectando perdía el evento
        para siempre (confirmado en vivo: pasó exactamente eso al matar
        event-bus a mitad de una Saga). Ahora el mensaje se queda pendiente
        y se reintenta solo en la próxima vuelta del loop (ver `_procesar(
        r.xreadgroup(..., {STREAM: "0"}, ...))` más abajo, que pide los
        propios pendientes de este consumer antes de pedir mensajes nuevos).
        No hay cola de dead-letter — un mensaje que falla siempre se
        reintenta para siempre; suficiente para este taller, no para
        producción real."""
        if not resp:
            return
        for _stream, messages in resp:
            for msg_id, fields in messages:
                tipo = fields.get("tipo")
                handler = handlers.get(tipo)
                if handler:
                    try:
                        handler(json.loads(fields["payload"]))
                    except Exception as exc:  # noqa: BLE001
                        print(f"[events] error procesando {tipo} ({msg_id}): {exc} — no se confirma, se reintenta")
                        continue
                r.xack(STREAM, group, msg_id)

    _asegurar_grupo()
    print(f"[events] {consumer_name} escuchando '{STREAM}' (grupo={group})")

    while True:
        # Todo el cuerpo del loop —los dos xreadgroup y el xack de
        # _procesar— va dentro del mismo try: un ConnectionError puede
        # saltar en cualquiera de los tres (confirmado en vivo: envolver
        # solo el primer xreadgroup no alcanzaba, el corte también pasaba
        # en el xack de después de procesar). Sin este catch, la excepción
        # tumbaba el proceso entero.
        try:
            # Primero, lo que este consumer ya se había llevado pero nunca
            # confirmó (handler falló, o la conexión se cortó justo antes
            # del ack) — "0" pide sus propios pendientes, sin bloquear.
            _procesar(r.xreadgroup(group, consumer_name, {STREAM: "0"}, count=10))
            # Después, mensajes nuevos — esto sí bloquea hasta 5s.
            _procesar(r.xreadgroup(group, consumer_name, {STREAM: ">"}, count=10, block=5000))
        except redis_lib.exceptions.ConnectionError as exc:
            # event-bus se reinició o hubo un corte de red. redis-py
            # reconecta solo en el siguiente comando; acá solo hay que no
            # dejar que la excepción se propague, y volver a crear el
            # consumer group por si el Redis nuevo no tiene el anterior
            # (sin persistencia, o volumen nuevo).
            print(f"[events] {consumer_name} perdió la conexión con Redis ({exc}) — reintentando en 2s...")
            time.sleep(2)
            _asegurar_grupo()
