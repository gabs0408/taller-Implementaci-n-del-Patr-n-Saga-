"""Persistencia de la Pasarela Interbancaria (Clearing Gateway) — Fase 1.

Habla contra el esquema `clearing` de Supabase (ver ../schema.sql, que hay
que correr una vez contra ese proyecto antes de levantar el servicio).

`liquidar()` es la única operación de este servicio y no tiene reversa
propia — la compensación de CP-04 corre aguas arriba, en risk y accounts
(ver app/core.py) — así que basta con UNIQUE(transfer_id) en
`clearing.liquidaciones` para la idempotencia, sin necesitar una columna
`operacion` como en los otros dos servicios.
"""
import os

import psycopg

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def _conn() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def liquidar(transfer_id: str, cuenta_destino: str, monto: float, ok: bool, motivo: str | None) -> dict:
    """Registra el resultado ya decidido por core.py (ok/motivo según el
    switch de timeout). Si ya existe una fila para este transfer_id, es
    idempotencia real a nivel de base — respaldo durable del cache de Redis
    (common/idempotency.py, TTL 24h) — y se devuelve lo ya guardado en vez
    de insertar de nuevo."""
    with _conn() as conn:
        row = conn.execute(
            "select estado, cuenta_destino, monto, motivo from clearing.liquidaciones where transfer_id = %s",
            (transfer_id,),
        ).fetchone()
        if row is not None:
            estado_db, cuenta_destino_db, monto_db, motivo_db = row
            if estado_db == "confirmada":
                return {"ok": True, "cuenta_destino": cuenta_destino_db, "monto": float(monto_db)}
            return {"ok": False, "motivo": motivo_db}

        conn.execute(
            """insert into clearing.liquidaciones
               (transfer_id, cuenta_destino, monto, estado, motivo)
               values (%s, %s, %s, %s, %s)""",
            (transfer_id, cuenta_destino, monto, "confirmada" if ok else "fallida", motivo),
        )
        if ok:
            return {"ok": True, "cuenta_destino": cuenta_destino, "monto": monto}
        return {"ok": False, "motivo": motivo}
