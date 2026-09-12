"""Despacho según el modo elegido (Fase 1, tarea f1-6).

Según `modo`, el Gateway llama al orquestador (Prefect) o publica el
evento inicial en el bus — nunca ambos. Ver CONTEXT.md sección 3.
"""
import os

import httpx

from common.events import publicar
from common.models import TransferRequest
from common.status_store import registrar_paso, set_estado

# Puente propio hacia el contenedor `orchestrator` — NO es la API de
# Prefect (esa es PREFECT_API_URL, que usa el propio `orchestrator` para
# reportar los flow/task runs al servidor de Prefect; ver docker-compose.yml).
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:8010")
# TODO (Fase 2 / Persona A): reemplazar por `prefect deployment run ...`
# contra la API de Prefect, una vez tengan un work pool configurado.
ORCHESTRATOR_TRIGGER_PATH = "/run-transferencia"


def dispatch(transfer_id: str, req: TransferRequest) -> None:
    set_estado(transfer_id, "PENDIENTE")
    registrar_paso(transfer_id, "recibido", "ok", {"modo": req.modo})

    payload = {
        "transfer_id": transfer_id,
        "cuenta_origen": req.cuenta_origen,
        "cuenta_destino": req.cuenta_destino,
        "monto": req.monto,
        "simulacion": req.simulacion.model_dump() if req.simulacion else {},
    }

    if req.modo == "orquestacion":
        # TODO (Fase 2): hoy llama a un endpoint HTTP simple expuesto
        # por el orquestador (ver orchestrator/flows/api.py). Cuando el
        # flow corra como Prefect deployment, cambiar por una llamada a
        # la API de Prefect (`PREFECT_API_URL`).
        try:
            httpx.post(f"{ORCHESTRATOR_URL}{ORCHESTRATOR_TRIGGER_PATH}", json=payload, timeout=5)
        except httpx.HTTPError as exc:
            registrar_paso(transfer_id, "dispatch_orquestador", "error", {"error": str(exc)})
    else:
        publicar("TransferenciaSolicitada", payload)
