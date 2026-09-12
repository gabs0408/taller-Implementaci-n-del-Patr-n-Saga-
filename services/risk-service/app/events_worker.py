"""Consumidor de eventos — modo Coreografía (Fase 3).

  SaldoDebitado      -> validar()  -> publica RiesgoAprobado o RiesgoRechazado
  TransferenciaFallida -> revertir() -> publica CompensacionEjecutada
"""
from common.events import consumir, publicar

from . import core


def on_saldo_debitado(payload: dict) -> None:
    resultado = core.validar(payload["transfer_id"], payload["cuenta_origen"], payload["monto"], payload.get("simulacion"))
    if resultado["ok"]:
        publicar("RiesgoAprobado", {**payload})
    else:
        publicar("RiesgoRechazado", {**payload, "motivo": resultado["motivo"]})


def on_transferencia_fallida(payload: dict) -> None:
    core.revertir(payload["transfer_id"])
    publicar("CompensacionEjecutada", {**payload, "servicio": "riesgo"})


if __name__ == "__main__":
    consumir(
        group="risk-service",
        consumer_name="risk-worker-1",
        handlers={
            "SaldoDebitado": on_saldo_debitado,
            "TransferenciaFallida": on_transferencia_fallida,
        },
    )
