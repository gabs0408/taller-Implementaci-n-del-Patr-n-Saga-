-- Modelo de datos — Clearing Service (Pasarela Interbancaria)
-- Fase 1 del checklist: hoy app/core.py no persiste nada, solo pasa por el
-- cache de idempotencia de Redis. Correr contra el proyecto/esquema de
-- Supabase de ESTE servicio únicamente (ver services/clearing-service/.env.example)
-- — no compartir con accounts/risk (Criterio 5 de la rúbrica).

create schema if not exists clearing;

-- liquidar() es la única operación de este servicio y no tiene reversa propia
-- (la compensación de CP-04 corre aguas arriba, en risk y accounts) — por eso
-- basta con UNIQUE(transfer_id) para la idempotencia, sin columna `operacion`.
create table if not exists clearing.liquidaciones (
    id               bigserial primary key,
    transfer_id      uuid not null unique,
    cuenta_destino   text not null,
    monto            numeric(18,2) not null,
    estado           text not null check (estado in ('confirmada', 'fallida')),
    motivo           text,
    creado_en        timestamptz not null default now()
);
