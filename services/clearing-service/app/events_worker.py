"""Consumidor de eventos — modo Coreografía (Fase 3).

  RiesgoAprobado -> liquidar() -> publica LiquidacionConfirmada
                                  o TransferenciaFallida{fase: "pasarela"}
"""
from common.events import consumir, publicar
from common.models import LIQUIDADO
from common.status_store import set_estado

from . import core


def on_riesgo_aprobado(payload: dict) -> None:
    resultado = core.liquidar(payload["transfer_id"], payload["cuenta_destino"], payload["monto"], payload.get("simulacion"))
    if resultado["ok"]:
        # Diagrama: RIESGO_OK -> LIQUIDADO.
        set_estado(payload["transfer_id"], LIQUIDADO)
        publicar("LiquidacionConfirmada", {**payload})
    else:
        publicar("TransferenciaFallida", {**payload, "fase": "pasarela", "motivo": resultado["motivo"]})


if __name__ == "__main__":
    consumir(
        group="clearing-service",
        consumer_name="clearing-worker-1",
        handlers={"RiesgoAprobado": on_riesgo_aprobado},
    )
