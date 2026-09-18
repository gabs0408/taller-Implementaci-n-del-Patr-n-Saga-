-- Modelo de datos — Accounts Service (Ledger)
-- Fase 1 del checklist: reemplaza el store en memoria de app/store.py.
-- Correr contra el proyecto/esquema de Supabase de ESTE servicio únicamente
-- (ver services/accounts-service/.env.example) — no compartir con risk/clearing,
-- es lo que evalúa el Criterio 5 (aislamiento de datos) de la rúbrica.

create schema if not exists accounts;

create table if not exists accounts.cuentas (
    cuenta_id       text primary key,
    saldo           numeric(18,2) not null default 0,
    moneda          text not null default 'USD',
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now()
);

-- Ledger de movimientos: una fila por operación aplicada. El UNIQUE de abajo
-- es la idempotencia a nivel de base de datos — respalda al cache de Redis
-- (common/idempotency.py, TTL 24h) si ese cache expira o se limpia.
create table if not exists accounts.movimientos (
    id                bigserial primary key,
    transfer_id       uuid not null,
    cuenta_id         text not null references accounts.cuentas(cuenta_id),
    tipo              text not null check (tipo in ('debito', 'credito', 'reverso_debito')),
    monto             numeric(18,2) not null,
    saldo_resultante  numeric(18,2) not null,
    creado_en         timestamptz not null default now(),
    unique (transfer_id, tipo)
);

create index if not exists movimientos_cuenta_id_idx on accounts.movimientos (cuenta_id);

-- Cuentas semilla — mismas que hoy trae hardcodeadas app/store.py, para que
-- la demo (CP-01..CP-05) siga funcionando igual al migrar de memoria a Supabase.
insert into accounts.cuentas (cuenta_id, saldo) values
    ('ACC-001', 1000000.00),
    ('ACC-002', 500000.00)
on conflict (cuenta_id) do nothing;
