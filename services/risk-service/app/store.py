"""Persistencia del servicio de Riesgo y Antifraude — Fase 1.

Habla contra el esquema `risk` de Supabase (ver ../schema.sql, que hay que
correr una vez contra ese proyecto antes de levantar el servicio). Reglas
configurables por cuenta en `risk.limites` (límite diario acumulado y monto
máximo por transferencia) — si una cuenta no tiene fila propia ahí, se usan
los defaults de este módulo.

`risk.evaluaciones` cumple dos roles:
  1. Idempotencia durable a nivel de base (UNIQUE(transfer_id, operacion)) —
     respaldo del cache de Redis (common/idempotency.py, TTL 24h).
  2. El registro del que revertir() recupera cuenta_origen/monto: el
     contrato de POST /riesgo/revertir solo manda `transfer_id` (ver
     CLAUDE.md sección 3), así que esos datos no viajan de nuevo.

El switch de fraude (simulacion.fraude) se resuelve en app/core.py antes de
llegar acá — un rechazo forzado no aplica ninguna regla real, así que no hay
nada que persistir (mismo criterio que fondos_insuficientes en
accounts-service).
"""
import os

import psycopg

from . import rules

DATABASE_URL = os.environ.get("DATABASE_URL", "")

DEFAULT_LIMITE_DIARIO = 50_000_000.0
DEFAULT_MONTO_MAXIMO = 20_000_000.0


def _conn() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def _get_limites(conn: psycopg.Connection, cuenta_id: str) -> tuple[float, float]:
    row = conn.execute(
        "select limite_diario, monto_maximo from risk.limites where cuenta_id = %s",
        (cuenta_id,),
    ).fetchone()
    if row:
        return float(row[0]), float(row[1])
    return DEFAULT_LIMITE_DIARIO, DEFAULT_MONTO_MAXIMO


def validar(transfer_id: str, cuenta_id: str, monto: float) -> dict:
    with _conn() as conn:
        existente = conn.execute(
            "select aprobado, motivo from risk.evaluaciones where transfer_id = %s and operacion = 'validar'",
            (transfer_id,),
        ).fetchone()
        if existente is not None:
            aprobado, motivo = existente
            return {"ok": aprobado, "motivo": motivo}

        limite_diario, monto_maximo = _get_limites(conn, cuenta_id)

        # Asegura la fila del día y la bloquea antes de leerla, para que dos
        # validaciones concurrentes sobre la misma cuenta no lean el mismo
        # acumulado viejo y ambas aprueben por encima del límite.
        conn.execute(
            """insert into risk.acumulado_diario (cuenta_id, fecha, monto_acumulado)
               values (%s, current_date, 0)
               on conflict (cuenta_id, fecha) do nothing""",
            (cuenta_id,),
        )
        row = conn.execute(
            """select monto_acumulado from risk.acumulado_diario
               where cuenta_id = %s and fecha = current_date for update""",
            (cuenta_id,),
        ).fetchone()
        acumulado_hoy = float(row[0]) if row else 0.0

        aprobado, motivo = rules.evaluar(monto, monto_maximo, limite_diario, acumulado_hoy)

        conn.execute(
            """insert into risk.evaluaciones
               (transfer_id, operacion, cuenta_origen, monto, aprobado, motivo)
               values (%s, 'validar', %s, %s, %s, %s)""",
            (transfer_id, cuenta_id, monto, aprobado, motivo),
        )
        if aprobado:
            conn.execute(
                """update risk.acumulado_diario
                   set monto_acumulado = monto_acumulado + %s
                   where cuenta_id = %s and fecha = current_date""",
                (monto, cuenta_id),
            )
        return {"ok": aprobado, "motivo": motivo}


def revertir(transfer_id: str) -> None:
    with _conn() as conn:
        ya_revertido = conn.execute(
            "select 1 from risk.evaluaciones where transfer_id = %s and operacion = 'revertir'",
            (transfer_id,),
        ).fetchone()
        if ya_revertido is not None:
            return

        original = conn.execute(
            """select cuenta_origen, monto from risk.evaluaciones
               where transfer_id = %s and operacion = 'validar' and aprobado = true""",
            (transfer_id,),
        ).fetchone()

        conn.execute(
            "insert into risk.evaluaciones (transfer_id, operacion, aprobado) values (%s, 'revertir', true)",
            (transfer_id,),
        )

        if original is not None:
            cuenta_origen, monto = original
            conn.execute(
                """update risk.acumulado_diario
                   set monto_acumulado = monto_acumulado - %s
                   where cuenta_id = %s and fecha = current_date""",
                (monto, cuenta_origen),
            )
