# NovaBank Saga

Taller de Arquitectura de Software Distribuida: patrón Saga bancario
(Orquestación con Prefect vs. Coreografía basada en eventos), con
observabilidad y compensaciones en reversa. Ver **[CLAUDE.md](./CLAUDE.md)**
para el contrato completo entre servicios, la máquina de estados y la
bitácora de decisiones del equipo — léanlo antes de tocar código.

Checklist interactivo por fases (progreso compartido del equipo):
https://claude.ai/code/artifact/f39c5f39-84d8-4202-b241-17c1c58b7316

## Qué hay aquí

Esto es un **esqueleto funcional**, no la solución. Arranca con
`docker-compose up`, hace CP-01 (camino feliz) de punta a punta en los
dos modos, y deja marcados con `TODO` los puntos que corresponden a
cada fase del checklist (persistencia real en Supabase, work pool de
Prefect, endpoint de reintento con el mismo idempotency-key, etc.).

```
novabank-saga/
├── CLAUDE.md               # fuente de verdad: contratos, estados, bitácora
├── docker-compose.yml
├── common/                 # librería compartida (Redis, eventos, idempotencia, modelos)
├── gateway/                # API Gateway — genera idempotency-key, despacha por modo
├── services/
│   ├── accounts-service/   # Cuentas y Saldos (Ledger)
│   ├── risk-service/       # Riesgo y Antifraude
│   └── clearing-service/   # Pasarela Interbancaria
├── orchestrator/           # Flow de Prefect — Saga Orquestada
├── frontend/               # React + Vite — formulario, switches de caos, timeline
├── contracts/              # openapi.yaml + events.asyncapi.yaml — el contrato formal (Fase 0)
├── docs/                   # comparación Orquestación vs Coreografía, diagramas
└── tests/                  # matriz CP-01..CP-05 (Fase 6)
```

Cada microservicio expone su lógica de negocio como funciones puras en
`app/core.py`. La ruta REST (`app/routes.py`, modo Orquestación) y el
listener de eventos (`app/events_worker.py`, modo Coreografía) llaman
**a las mismas funciones** — nunca dupliquen la lógica entre los dos
modos (regla 3 de CLAUDE.md).

## Cómo correrlo

```bash
docker compose up --build
```

Esto levanta: `event-bus` (Redis), `gateway` (:8000), los 3
microservicios (:8001-8003) + su worker de eventos cada uno,
`prefect-server` — **Prefect UI en http://localhost:4200** —,
`orchestrator` (bridge propio, :8010, no confundir con el puerto de
Prefect) y `frontend` (:5173).

Probar el camino feliz sin el frontend (Fase 0, primer caso exitoso):

```bash
docker compose exec orchestrator python run_demo.py               # CP-01
docker compose exec orchestrator python run_demo.py --fraude      # CP-03
docker compose exec orchestrator python run_demo.py --sin-fondos  # CP-02
docker compose exec orchestrator python run_demo.py --timeout     # CP-04
```

O contra el Gateway directamente:

```bash
curl -X POST http://localhost:8000/transferencias \
  -H "Content-Type: application/json" \
  -d '{"cuenta_origen":"ACC-001","cuenta_destino":"ACC-002","monto":10000,"modo":"orquestacion"}'

curl http://localhost:8000/transferencias/<transfer_id>                # estado + pasos (Redis, rápido)
curl http://localhost:8000/transferencias/<transfer_id>/auditoria      # transiciones durables (Postgres), con causa del fallo
curl http://localhost:8000/transferencias/<transfer_id>/eventos        # trazabilidad de Coreografía (lee el bus directo)
```

Frontend: http://localhost:5173

## Bases de datos (Supabase)

Los 3 microservicios ya están conectados a Postgres — correr primero el
`schema.sql` de cada uno contra su proyecto de Supabase, copiar su
`.env.example` → `.env` y, para `docker-compose up`, completar
`ACCOUNTS_DATABASE_URL`, `RISK_DATABASE_URL` y `CLEARING_DATABASE_URL` en un
`.env` en la raíz del repo (ver `.env.example`). Sin esas variables, los
servicios arrancan igual pero sus endpoints devuelven error de conexión al
primer uso.

- `accounts-service`: `app/store.py`, tablas `accounts.cuentas` y `accounts.movimientos`.
- `risk-service`: `app/store.py`, tablas `risk.limites` (límite diario y monto
  máximo configurables por cuenta), `risk.evaluaciones` y `risk.acumulado_diario`.
- `clearing-service`: `app/store.py`, tabla `clearing.liquidaciones` (confirmada/fallida,
  con el motivo cuando el switch de timeout la fuerza a fallar).

Además, **`common/status_store.py`** persiste cada transición de estado
(`estado_anterior` → `estado_nuevo`, con timestamp) en `bitacora.transiciones`
— correr `common/schema_bitacora.sql` una vez y completar `AUDIT_DATABASE_URL`
en el `.env` de la raíz. Es la bitácora de auditoría DURABLE (sobrevive un
reinicio de Redis), consultable vía `GET /transferencias/{id}/auditoria` o
con SQL directo. El rol recomendado solo tiene `INSERT`+`SELECT` — ni
siquiera el propio backend puede editar o borrar una fila ya escrita.

## Qué falta (por fase — ver el checklist para el detalle completo)

- **Fase 1:** los 3 microservicios ya están conectados a Supabase — falta que cada quien cree su proyecto real y complete las connection strings (hoy solo hay `.env.example`).
- **Fase 2:** mover el orquestador a un deployment real de Prefect
  (hoy corre el flow en un hilo dentro de `orchestrator/api.py`).
- **Fase 4:** el Prefect UI ya está expuesto (http://localhost:4200,
  ahí van a ver los delays y las compensaciones de la Orquestación paso
  a paso). Falta un equivalente para Coreografía — hoy solo tienen
  `GET /transferencias/{id}` en crudo; un dashboard propio que lo lea
  y lo muestre igual de bien está en la Fase 4.
- **Fase 5:** botón de reintento en el frontend que reuse el mismo
  `X-Idempotency-Key` (para demostrar CP-05 desde la UI).
- **Fase 6:** completar `tests/test_cp_matrix.py` (están con `skip`
  hasta que haya una forma de resetear cuentas entre corridas).
- **Fase 7:** llenar `docs/orquestacion-vs-coreografia.md`, agregar el
  diagrama C4 y grabar el video.
