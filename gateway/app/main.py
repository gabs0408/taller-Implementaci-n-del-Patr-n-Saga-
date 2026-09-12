"""API Gateway — punto único de entrada (Fase 1).

- Genera el transfer_id (UUID) e idempotency-key.
- Despacha hacia el orquestador o el bus de eventos según `modo`.
- Expone el estado/bitácora para que el frontend lo consuma en tiempo
  real (Fase 5, f5-3).
"""
import uuid

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from common.idempotency import marcar_procesado, ya_procesado
from common.models import TransferRequest, TransferResponse
from common.status_store import get_estado, get_pasos

from .dispatch import dispatch

app = FastAPI(title="NovaBank Saga — API Gateway")

# TODO (Fase 1): restringir origins al dominio real del frontend antes de entregar.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/transferencias", response_model=TransferResponse)
def crear_transferencia(req: TransferRequest, x_idempotency_key: str | None = Header(default=None)):
    idem_key = x_idempotency_key or str(uuid.uuid4())

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


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
