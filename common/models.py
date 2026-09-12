"""Modelos compartidos entre el Gateway y los 3 microservicios.

Reflejan el contrato definido en CONTEXT.md (sección 3). Si cambias un
campo aquí, actualiza CONTEXT.md en el mismo commit — ver regla 2 de
ese archivo.
"""
from typing import Literal, Optional
from pydantic import BaseModel


class Simulacion(BaseModel):
    """Switches de caos que el frontend activa (Fase 5) y que viajan
    hasta el servicio que debe fallar."""
    fondos_insuficientes: bool = False
    fraude: bool = False
    timeout_pasarela: bool = False
    reintento_duplicado: bool = False


class TransferRequest(BaseModel):
    cuenta_origen: str
    cuenta_destino: str
    monto: float
    modo: Literal["orquestacion", "coreografia"] = "orquestacion"
    simulacion: Optional[Simulacion] = None


class TransferResponse(BaseModel):
    transfer_id: str
    modo: str
    estado: str


# Estados finales válidos (CONTEXT.md, sección 4)
CONFIRMADO = "CONFIRMADO"
RECHAZADO_FONDOS = "RECHAZADO_FONDOS"
RECHAZADO_RIESGO = "RECHAZADO_RIESGO"
RECHAZADO_RED = "RECHAZADO_RED"

# Estados intermedios (máquina de estados, CONTEXT.md sección 3)
PENDIENTE = "PENDIENTE"
DEBITADO = "DEBITADO"
RIESGO_OK = "RIESGO_OK"
LIQUIDADO = "LIQUIDADO"
