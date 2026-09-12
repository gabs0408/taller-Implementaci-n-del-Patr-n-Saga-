"""Consumidor de eventos — modo Coreografía (Fase 3).

  RiesgoAprobado -> liquidar() -> publica LiquidacionConfirmada
                                  o TransferenciaFallida{fase: "pasarela"}
"""
from common.events import consumir, publicar

from . import core


def on_riesgo_aprobado(payload: dict) -> None:
    resultado = core.liquidar(payload["transfer_id"], payload["cuenta_destino"], payload["monto"], payload.get("simulacion"))
    if resultado["ok"]:
        publicar("LiquidacionConfirmada", {**payload})
    else:
        publicar("TransferenciaFallida", {**payload, "fase": "pasarela", "motivo": resultado["motivo"]})


if __name__ == "__main__":
    consumir(
        group="clearing-service",
        consumer_name="clearing-worker-1",
        handlers={"RiesgoAprobado": on_riesgo_aprobado},
    )
