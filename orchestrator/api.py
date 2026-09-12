"""Puente HTTP simple entre el Gateway y el flow de Prefect.

TODO (Fase 2, cuando ya tengan un work pool / deployment de Prefect
configurado): reemplazar este endpoint por `prefect deployment run`
vía la API de Prefect, así el flow corre en un worker administrado
por Prefect en vez de en un hilo de este proceso.
"""
import threading

from fastapi import FastAPI

from flows.transferencia_flow import transferencia_saga

app = FastAPI(title="NovaBank Saga — Orchestrator")


@app.post("/run-transferencia")
def run_transferencia(payload: dict):
    # Se corre en background para que el Gateway responda de inmediato
    # y el frontend siga el avance por polling (GET /transferencias/{id}).
    thread = threading.Thread(
        target=transferencia_saga,
        kwargs={
            "transfer_id": payload["transfer_id"],
            "cuenta_origen": payload["cuenta_origen"],
            "cuenta_destino": payload["cuenta_destino"],
            "monto": payload["monto"],
            "simulacion": payload.get("simulacion"),
        },
        daemon=True,
    )
    thread.start()
    return {"status": "iniciado", "transfer_id": payload["transfer_id"]}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
