-- Bitácora de auditoría de transiciones de estado — cross-cutting, no es
-- de ningún microservicio en particular (por eso vive en common/, no en
-- services/*). La escriben las 8 piezas que llaman a
-- common/status_store.set_estado(): gateway, orchestrator, y los 3
-- microservicios + sus 3 workers de eventos.
--
-- A diferencia de `transferencia:{id}:estado` en Redis (que solo guarda el
-- valor ACTUAL y se pierde si el contenedor de Redis se reinicia — no hay
-- volumen de persistencia configurado para `event-bus` en
-- docker-compose.yml), esta tabla es el registro durable: una fila por
-- cada transición, con estado anterior, estado nuevo y cuándo pasó.
--
-- Correr una sola vez contra el proyecto de Supabase que se use para la
-- bitácora (puede ser el mismo que accounts/risk, en su propio esquema —
-- aislado igual que los demás).

create schema if not exists bitacora;

create table if not exists bitacora.transiciones (
    id               bigserial primary key,
    transfer_id      uuid not null,
    estado_anterior  text,
    estado_nuevo     text not null,
    -- Causa del fallo cuando estado_nuevo es un rechazo (fondos_insuficientes,
    -- fraude_simulado, timeout_pasarela) — null en transiciones de éxito
    -- (DEBITADO, RIESGO_OK, LIQUIDADO, CONFIRMADO).
    motivo           text,
    creado_en        timestamptz not null default now()
);

-- Si la tabla ya existía de una sesión anterior sin esta columna:
-- alter table bitacora.transiciones add column if not exists motivo text;

create index if not exists transiciones_transfer_id_idx
    on bitacora.transiciones (transfer_id, creado_en);

-- Rol dedicado, solo INSERT + SELECT — nunca UPDATE ni DELETE. Un log de
-- auditoría que se puede editar o borrar no sirve como auditoría; la
-- inmutabilidad queda impuesta por permisos de base, no solo por
-- convención de código.
-- (Correr manualmente reemplazando la contraseña, o pedirle a la IA que
-- lo haga con el mismo patrón que accounts_role/risk_role/clearing_role.)
-- create role bitacora_role with login password '...';
-- grant usage on schema bitacora to bitacora_role;
-- grant select, insert on bitacora.transiciones to bitacora_role;
-- grant usage, select on all sequences in schema bitacora to bitacora_role;
