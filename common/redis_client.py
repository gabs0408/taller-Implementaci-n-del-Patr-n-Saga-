"""Cliente Redis compartido.

Redis cumple dos roles en este proyecto (ver CONTEXT.md):
1. Bus de eventos para la Saga Coreografiada (Redis Streams).
2. Almacén del estado/bitácora de cada transferencia, que el Gateway
   expone al frontend vía GET /transferencias/{id} (Fase 5).

No es la base de datos de negocio: los saldos, reglas de riesgo, etc.
van en Supabase (Fase 1) — cada servicio los maneja en su propio
store.py.
"""
import os
import redis

_client: "redis.Redis | None" = None


def get_redis() -> "redis.Redis":
    global _client
    if _client is None:
        url = os.environ.get("REDIS_URL", "redis://event-bus:6379/0")
        _client = redis.from_url(url, decode_responses=True)
    return _client
