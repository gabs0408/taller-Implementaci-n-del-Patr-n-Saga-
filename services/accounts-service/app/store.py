"""Persistencia del servicio de Cuentas y Saldos (Ledger) — Fase 1.

Habla contra el esquema `accounts` de Supabase (ver ../schema.sql, que hay
que correr una vez contra ese proyecto antes de levantar el servicio). Las
tablas se referencian siempre calificadas (`accounts.cuentas`,
`accounts.movimientos`) en vez de depender de `search_path`, así que no hace
falta ningún parámetro especial en `DATABASE_URL`.

Cada operación (debitar/acreditar/revertir_debito) corre en una única
transacción:
  1. Si ya existe una fila en `movimientos` para (transfer_id, tipo), es un
     reintento (CP-05) — se devuelve el saldo ya aplicado sin tocar nada de
     nuevo. Esto es un respaldo *durable* del chequeo de idempotencia que ya
     hace common/idempotency.py sobre Redis (TTL 24h): si ese cache expira o
     se limpia, esta restricción UNIQUE sigue evitando el doble cobro.
  2. Si no existe, bloquea la fila de `cuentas` con SELECT ... FOR UPDATE
     (evita que dos operaciones concurrentes sobre la misma cuenta lean el
     mismo saldo viejo) y aplica el movimiento.

Nota: se abre una conexión nueva por operación en vez de usar un pool —
cada paso de la Saga ya tiene un STEP_DELAY_MS de 2-4s de por medio, así que
el costo de abrir conexión es insignificante para la escala de este taller.
"""
import os

import psycopg

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def _conn() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def get_saldo(cuenta_id: str) -> float:
    with _conn() as conn:
        row = conn.execute(
            "select saldo from accounts.cuentas where cuenta_id = %s", (cuenta_id,)
        ).fetchone()
        return float(row[0]) if row else 0.0


def _movimiento_existente(conn: psycopg.Connection, transfer_id: str, tipo: str) -> float | None:
    row = conn.execute(
        "select saldo_resultante from accounts.movimientos where transfer_id = %s and tipo = %s",
        (transfer_id, tipo),
    ).fetchone()
    return float(row[0]) if row else None


def debitar(transfer_id: str, cuenta_id: str, monto: float) -> tuple[bool, float]:
    """Devuelve (aplicado, saldo_resultante_o_saldo_actual).
    aplicado=False si no había fondos suficientes — en ese caso no se toca
    nada (CP-02: rechazo inmediato, sin nada que compensar)."""
    with _conn() as conn:
        existente = _movimiento_existente(conn, transfer_id, "debito")
        if existente is not None:
            return True, existente

        row = conn.execute(
            "select saldo from accounts.cuentas where cuenta_id = %s for update",
            (cuenta_id,),
        ).fetchone()
        saldo = float(row[0]) if row else 0.0

        if monto > saldo:
            return False, saldo

        nuevo_saldo = saldo - monto
        conn.execute(
            "update accounts.cuentas set saldo = %s, actualizado_en = now() where cuenta_id = %s",
            (nuevo_saldo, cuenta_id),
        )
        conn.execute(
            """insert into accounts.movimientos
               (transfer_id, cuenta_id, tipo, monto, saldo_resultante)
               values (%s, %s, 'debito', %s, %s)""",
            (transfer_id, cuenta_id, monto, nuevo_saldo),
        )
        return True, nuevo_saldo


def _sumar(transfer_id: str, cuenta_id: str, monto: float, tipo: str) -> float:
    with _conn() as conn:
        existente = _movimiento_existente(conn, transfer_id, tipo)
        if existente is not None:
            return existente

        row = conn.execute(
            "select saldo from accounts.cuentas where cuenta_id = %s for update",
            (cuenta_id,),
        ).fetchone()
        saldo = float(row[0]) if row else 0.0
        nuevo_saldo = saldo + monto

        conn.execute(
            "update accounts.cuentas set saldo = %s, actualizado_en = now() where cuenta_id = %s",
            (nuevo_saldo, cuenta_id),
        )
        conn.execute(
            """insert into accounts.movimientos
               (transfer_id, cuenta_id, tipo, monto, saldo_resultante)
               values (%s, %s, %s, %s, %s)""",
            (transfer_id, cuenta_id, tipo, monto, nuevo_saldo),
        )
        return nuevo_saldo


def acreditar(transfer_id: str, cuenta_id: str, monto: float) -> float:
    return _sumar(transfer_id, cuenta_id, monto, "credito")


def revertir_debito(transfer_id: str, cuenta_id: str, monto: float) -> float:
    return _sumar(transfer_id, cuenta_id, monto, "reverso_debito")
