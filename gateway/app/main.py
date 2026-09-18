"""API Gateway — punto único de entrada (Fase 1).

- Genera el transfer_id (UUID) e idempotency-key.
- Despacha hacia el orquestador o el bus de eventos según `modo`.
- Expone el estado/bitácora para que el frontend lo consuma en tiempo
  real (Fase 5, f5-3).
"""
import uuid

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from common.events import leer_eventos
from common.idempotency import marcar_procesado, ya_procesado
from common.models import TransferRequest, TransferResponse
from common.status_store import get_estado, get_pasos, get_transiciones

from .dispatch import dispatch

app = FastAPI(title="NovaBank Saga — API Gateway")

# TODO (Fase 1): restringir origins al dominio real del frontend antes de entregar.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    # Sin esto, el navegador bloquea que el JS del frontend lea
    # X-Idempotency-Key de la respuesta — X-* no está en la lista de headers
    # "safelisted" que expone por default, aunque curl/servidor sí lo vean.
    # Sin expose_headers, CP-05 no se puede reintentar desde la UI aunque el
    # Gateway ya lo esté devolviendo bien.
    expose_headers=["X-Idempotency-Key"],
)


@app.post("/transferencias", response_model=TransferResponse)
def crear_transferencia(req: TransferRequest, response: Response, x_idempotency_key: str | None = Header(default=None)):
    idem_key = x_idempotency_key or str(uuid.uuid4())
    # Se devuelve siempre en la respuesta (generado o el que mandó el
    # cliente) — si no, un cliente que no manda su propio header nunca
    # puede reintentar con el mismo idem_key (el Gateway generaría uno
    # nuevo en cada request y CP-05 sería imposible de disparar).
    response.headers["X-Idempotency-Key"] = idem_key

    cached = ya_procesado(idem_key, "crear_transferencia")
    if cached:
        # CP-05: mismo idempotency-key -> se devuelve el resultado ya emitido,
        # sin volver a despachar la transferencia.
        return TransferResponse(**cached)

    transfer_id = str(uuid.uuid4())
    dispatch(transfer_id, req)

    resp = TransferResponse(transfer_id=transfer_id, modo=req.modo, estado="PENDIENTE")
    marcar_procesado(idem_key, "crear_transferencia", resp.model_dump())
    return resp


@app.get("/transferencias/{transfer_id}")
def estado_transferencia(transfer_id: str):
    estado = get_estado(transfer_id)
    if estado is None:
        raise HTTPException(status_code=404, detail="transferencia no encontrada")
    return {"transfer_id": transfer_id, "estado": estado, "pasos": get_pasos(transfer_id)}


@app.get("/transferencias/{transfer_id}/auditoria")
def auditoria_transferencia(transfer_id: str):
    """Bitácora DURABLE de transiciones de estado (Postgres —
    bitacora.transiciones), distinta de `pasos` en GET /transferencias/{id}
    (Redis, operación por operación). Esta sobrevive un reinicio de Redis;
    esa es la ruta rápida que usa el frontend para el polling."""
    transiciones = get_transiciones(transfer_id)
    if not transiciones:
        raise HTTPException(status_code=404, detail="sin transiciones registradas para esta transferencia")
    return {"transfer_id": transfer_id, "transiciones": transiciones}


@app.get("/transferencias/{transfer_id}/eventos")
def eventos_transferencia(transfer_id: str):
    """Trazabilidad de Coreografía — el equivalente al Prefect UI, pero
    para el modo sin coordinador: no hay flow run que consultar, así que
    esto lee directo el bus (Redis Streams) y devuelve, en orden, los
    eventos de dominio que pasaron por esta transferencia — quién publicó
    cada uno se ve en `contracts/events.asyncapi.yaml`. Sirve tanto si la
    transferencia corrió en Coreografía (varios eventos) como en
    Orquestación (normalmente solo `TransferenciaSolicitada`, porque ese
    modo no pasa por el bus)."""
    eventos = leer_eventos(transfer_id)
    if not eventos:
        raise HTTPException(status_code=404, detail="sin eventos en el bus para esta transferencia")
    return {"transfer_id": transfer_id, "eventos": eventos}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
