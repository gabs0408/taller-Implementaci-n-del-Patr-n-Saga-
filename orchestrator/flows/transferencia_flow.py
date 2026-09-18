"""Flow de Prefect — Saga Orquestada (Fase 2, Criterio 1 · 40%).

Un coordinador central llama explícitamente a cada servicio y, ante un
fallo, dispara las compensaciones en orden inverso. Compárese con
services/*/app/events_worker.py, que implementa la misma secuencia sin
coordinador central (Fase 3).
"""
import httpx
from prefect import flow, task
from prefect.context import TaskRunContext

from common.models import CONFIRMADO, DEBITADO, LIQUIDADO, RECHAZADO_FONDOS, RECHAZADO_RED, RECHAZADO_RIESGO, RIESGO_OK
from common.status_store import registrar_paso, set_estado

from . import clients

# Los @task envuelven las llamadas HTTP para que cada paso —éxito,
# fallo y compensación— quede registrado como una unidad en el
# Prefect UI (Fase 4).

# --- Fallo transitorio vs. fallo de negocio ------------------------------
#
# Un rechazo de NEGOCIO (fondos_insuficientes, fraude, timeout_pasarela)
# nunca lanza excepción: clients.py hace raise_for_status() pero el
# microservicio responde 200 con {"ok": false, "motivo": ...} — eso vuelve
# como valor normal y el flow lo maneja explícitamente más abajo (if not
# resultado["ok"]: ...). Prefect nunca ve esto como un fallo de task.
#
# Un fallo TRANSITORIO (red caída, timeout, 5xx inesperado) sí lanza
# excepción — ahí es donde entran retries y on_failure. retry_condition_fn
# además filtra un 4xx real (payload mal armado — un bug determinístico
# que reintentar no arregla) para no perder tiempo reintentando algo que
# va a fallar siempre igual.


def _vale_la_pena_reintentar(task, task_run, state) -> bool:
    try:
        state.result(raise_on_failure=True)
    except httpx.HTTPStatusError as exc:
        return exc.response.status_code >= 500
    except httpx.HTTPError:
        return True  # timeout, connect error, etc.
    except Exception:
        return False
    return False


def _log_fallo_transitorio(task, task_run, state) -> None:
    """on_failure de task — corre solo cuando se agotaron los reintentos de
    un fallo transitorio real. Un rechazo de negocio nunca llega acá.

    TaskRun no expone los argumentos con los que se llamó la task (no tiene
    atributo `parameters` en esta versión de Prefect) — hay que sacarlos del
    contexto de ejecución, que sigue activo mientras corre el hook."""
    ctx = TaskRunContext.get()
    params = ctx.parameters if ctx else {}
    transfer_id = params.get("transfer_id")
    if not transfer_id:
        return
    error = "error desconocido"
    try:
        state.result(raise_on_failure=True)
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
    registrar_paso(
        transfer_id,
        task.name,
        "error_transitorio",
        {"intentos": task_run.run_count, "error": error},
    )


REINTENTOS = dict(
    retries=2,
    retry_delay_seconds=2,
    retry_condition_fn=_vale_la_pena_reintentar,
    on_failure=[_log_fallo_transitorio],
)


@task(name="debitar", **REINTENTOS)
def debitar_task(transfer_id, cuenta_origen, monto, simulacion):
    return clients.debitar(transfer_id, cuenta_origen, monto, simulacion)


@task(name="validar_riesgo", **REINTENTOS)
def validar_riesgo_task(transfer_id, cuenta_origen, monto, simulacion):
    return clients.validar_riesgo(transfer_id, cuenta_origen, monto, simulacion)


@task(name="liquidar", **REINTENTOS)
def liquidar_task(transfer_id, cuenta_destino, monto, simulacion):
    return clients.liquidar(transfer_id, cuenta_destino, monto, simulacion)


@task(name="acreditar", **REINTENTOS)
def acreditar_task(transfer_id, cuenta_destino, monto):
    return clients.acreditar(transfer_id, cuenta_destino, monto)


# Las tasks de compensación también reintentan fallos transitorios — acá es
# más crítico todavía: si revertir_debito se cae por un timeout de red
# después de reintentar, el dinero queda debitado sin reversa aplicada,
# justo el escenario que la Saga tiene que evitar (Criterio 1).
@task(name="revertir_debito", **REINTENTOS)
def revertir_debito_task(transfer_id, cuenta_origen, monto):
    return clients.revertir_debito(transfer_id, cuenta_origen, monto)


@task(name="revertir_riesgo", **REINTENTOS)
def revertir_riesgo_task(transfer_id):
    return clients.revertir_riesgo(transfer_id)


def _log_flow_fallido(flow, flow_run, state) -> None:
    """on_failure de flow — corre si alguna task se quedó sin reintentos y
    el flow no pudo seguir. No inventamos un estado final nuevo fuera de
    los 4 de CLAUDE.md sección 4 (el `estado` queda en el último valor que
    sí alcanzó a escribirse, p.ej. DEBITADO); acá solo dejamos un paso
    explícito en la bitácora para que quede claro en el frontend/API que
    la Saga no llegó a un estado final de negocio — se cortó por un fallo
    transitorio, hay que revisar el Prefect UI."""
    transfer_id = flow_run.parameters.get("transfer_id")
    if transfer_id:
        registrar_paso(
            transfer_id,
            "flow",
            "error_transitorio",
            {"mensaje": "la Saga no pudo completarse — fallo transitorio agotó los reintentos, ver Prefect UI"},
        )


@flow(name="transferencia-saga-orquestada", on_failure=[_log_flow_fallido])
def transferencia_saga(transfer_id: str, cuenta_origen: str, cuenta_destino: str, monto: float, simulacion: dict | None = None) -> str:
    simulacion = simulacion or {}
    # No hace falta set_estado(transfer_id, PENDIENTE) acá: gateway/app/dispatch.py
    # ya lo dejó en PENDIENTE de forma síncrona antes de siquiera llamar a este
    # flow (para los dos modos) — repetirlo acá solo generaba una fila
    # PENDIENTE -> PENDIENTE redundante en bitacora.transiciones, visible
    # recién ahora que existe el historial durable (antes, con Redis
    # guardando solo el valor actual, la redundancia no se notaba).

    debito = debitar_task(transfer_id, cuenta_origen, monto, simulacion)
    if not debito["ok"]:
        # CP-02: nada que compensar, nada se aplicó todavía.
        set_estado(transfer_id, RECHAZADO_FONDOS, motivo=debito.get("motivo"))
        return RECHAZADO_FONDOS
    set_estado(transfer_id, DEBITADO)

    riesgo = validar_riesgo_task(transfer_id, cuenta_origen, monto, simulacion)
    if not riesgo["ok"]:
        # CP-03: compensación en reversa -> solo el débito.
        revertir_debito_task(transfer_id, cuenta_origen, monto)
        set_estado(transfer_id, RECHAZADO_RIESGO, motivo=riesgo.get("motivo"))
        return RECHAZADO_RIESGO
    set_estado(transfer_id, RIESGO_OK)

    liquidacion = liquidar_task(transfer_id, cuenta_destino, monto, simulacion)
    if not liquidacion["ok"]:
        # CP-04: compensación en reversa -> riesgo, luego débito (orden inverso estricto).
        revertir_riesgo_task(transfer_id)
        revertir_debito_task(transfer_id, cuenta_origen, monto)
        set_estado(transfer_id, RECHAZADO_RED, motivo=liquidacion.get("motivo"))
        return RECHAZADO_RED
    set_estado(transfer_id, LIQUIDADO)

    acreditar_task(transfer_id, cuenta_destino, monto)
    set_estado(transfer_id, CONFIRMADO)
    return CONFIRMADO
