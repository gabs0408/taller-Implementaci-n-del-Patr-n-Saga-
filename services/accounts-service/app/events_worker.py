"""Consumidor de eventos — modo Coreografía (Fase 3).

Reacciona de forma autónoma: nadie le llama directamente. Reutiliza
las mismas funciones de core.py que usan los endpoints REST (regla 3
de CONTEXT.md).

Corre como proceso aparte: `python -m app.events_worker`
(ver docker-compose.yml, servicio `accounts-service-worker`).

Secuencia que este worker implementa (ver CONTEXT.md sección 3):
  TransferenciaSolicitada -> debitar()       -> publica SaldoDebitado
                                               (o corta en RECHAZADO_FONDOS)
  RiesgoRechazado         -> revertir_debito -> estado RECHAZADO_RIESGO
  TransferenciaFallida    -> revertir_debito -> estado RECHAZADO_RED
  LiquidacionConfirmada   -> acreditar(destino) -> estado CONFIRMADO
"""
from common.events import consumir, publicar
from common.models import CONFIRMADO, RECHAZADO_FONDOS, RECHAZADO_RIESGO, RECHAZADO_RED
from common.status_store import set_estado

from . import core


def on_transferencia_solicitada(payload: dict) -> None:
    transfer_id = payload["transfer_id"]
    resultado = core.debitar(transfer_id, payload["cuenta_origen"], payload["monto"], payload.get("simulacion"))
    if resultado["ok"]:
        publicar("SaldoDebitado", {**payload})
    else:
        # CP-02: nada que compensar todavía.
        set_estado(transfer_id, RECHAZADO_FONDOS)


def on_riesgo_rechazado(payload: dict) -> None:
    transfer_id = payload["transfer_id"]
    core.revertir_debito(transfer_id, payload["cuenta_origen"], payload["monto"])
    set_estado(transfer_id, RECHAZADO_RIESGO)
    publicar("CompensacionEjecutada", {**payload, "servicio": "cuentas"})


def on_transferencia_fallida(payload: dict) -> None:
    # CP-04: la pasarela falló -> revertir el débito es la última
    # compensación (orden inverso: liquidar, riesgo, débito).
    transfer_id = payload["transfer_id"]
    core.revertir_debito(transfer_id, payload["cuenta_origen"], payload["monto"])
    set_estado(transfer_id, RECHAZADO_RED)
    publicar("CompensacionEjecutada", {**payload, "servicio": "cuentas"})


def on_liquidacion_confirmada(payload: dict) -> None:
    transfer_id = payload["transfer_id"]
    core.acreditar(transfer_id, payload["cuenta_destino"], payload["monto"])
    set_estado(transfer_id, CONFIRMADO)


if __name__ == "__main__":
    consumir(
        group="accounts-service",
        consumer_name="accounts-worker-1",
        handlers={
            "TransferenciaSolicitada": on_transferencia_solicitada,
            "RiesgoRechazado": on_riesgo_rechazado,
            "TransferenciaFallida": on_transferencia_fallida,
            "LiquidacionConfirmada": on_liquidacion_confirmada,
        },
    )
