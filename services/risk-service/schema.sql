-- Modelo de datos — Risk Service (Riesgo y Antifraude)
-- Fase 1 del checklist: reemplaza el LIMITE_DIARIO hardcodeado de app/rules.py
-- (TODO ya marcado ahí). Correr contra el proyecto/esquema de Supabase de
-- ESTE servicio únicamente (ver services/risk-service/.env.example) — no
-- compartir con accounts/clearing (Criterio 5 de la rúbrica).

create schema if not exists risk;

-- Reglas configurables por cuenta. Si una cuenta no tiene fila propia acá,
-- app/store.py usa los defaults de código (DEFAULT_LIMITE_DIARIO /
-- DEFAULT_MONTO_MAXIMO) — así no hace falta sembrar todas las cuentas para
-- que el servicio funcione, pero se puede afinar por cuenta cuando haga falta.
create table if not exists risk.limites (
    cuenta_id       text primary key,
    limite_diario   numeric(18,2) not null default 50000000,
    monto_maximo    numeric(18,2) not null default 20000000,
    actualizado_en  timestamptz not null default now()
);

-- Bitácora de cada validar()/revertir() — antes no se persistía nada, solo
-- se registraba en Redis (common/status_store.py). El UNIQUE es la
-- idempotencia a nivel de base, mismo criterio que accounts.movimientos.
-- También es de acá de donde revertir() recupera cuenta_origen/monto: el
-- contrato de POST /riesgo/revertir solo manda transfer_id.
create table if not exists risk.evaluaciones (
    id              bigserial primary key,
    transfer_id     uuid not null,
    operacion       text not null check (operacion in ('validar', 'revertir')),
    cuenta_origen   text,
    monto           numeric(18,2),
    aprobado        boolean,
    motivo          text,
    creado_en       timestamptz not null default now(),
    unique (transfer_id, operacion)
);

-- Acumulado de riesgo aprobado por cuenta y día.
--   - validar() que aprueba -> suma `monto` al acumulado de (cuenta_origen, hoy)
--   - revertir() (CP-04)    -> resta ese mismo `monto`
-- Sin el paso de revertir, el límite diario quedaría "consumido" para
-- siempre aunque la transferencia se haya compensado.
create table if not exists risk.acumulado_diario (
    cuenta_id        text not null,
    fecha            date not null,
    monto_acumulado  numeric(18,2) not null default 0,
    primary key (cuenta_id, fecha)
);

-- Mismas cuentas semilla que accounts-service, con los límites por defecto,
-- para que la demo (CP-01..CP-05) tenga reglas explícitas desde el día uno.
insert into risk.limites (cuenta_id, limite_diario, monto_maximo) values
    ('ACC-001', 50000000.00, 20000000.00),
    ('ACC-002', 50000000.00, 20000000.00)
on conflict (cuenta_id) do nothing;
