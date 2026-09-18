# Contexto del Proyecto — NovaBank Saga

> **Léeme primero.** Este archivo es la fuente de verdad compartida entre Persona A, Persona B y cualquier asistente de IA que trabaje en este repo. Se actualiza en cada sesión de trabajo — no al final del taller. Su objetivo es evitar que las dos mitades del equipo (o dos sesiones de IA distintas) construyan sobre supuestos diferentes.

## 0. Reglas para cualquier IA que edite este repo

1. Lee este archivo completo antes de tocar contratos entre servicios o lógica de compensación.
2. No cambies nombres de eventos, endpoints o campos de estado sin actualizar la sección **3. Contratos** en el mismo cambio.
3. Los microservicios exponen su lógica de negocio (debitar, validar riesgo, liquidar, revertir) como funciones internas únicas. La ruta REST (modo orquestado) y el listener de eventos (modo coreografía) deben llamar a la **misma función interna** — nunca dupliques la lógica de negocio entre los dos modos.
4. Después de tocar lógica de Saga o de compensación, vuelve a revisar la matriz de la sección 5 en ambos modos antes de dar el cambio por cerrado.
5. Al terminar una sesión de trabajo, agrega una entrada a la **Bitácora de Cambios** (sección 6) — fecha, autor (Persona A / Persona B / IA), qué cambió y qué contrato quedó afectado.
6. Si algo en el código contradice este archivo, el código más reciente gana — pero corrige este archivo en el mismo commit para que no quede desactualizado.

## 1. Qué es esto

Taller de Arquitectura de Software Distribuida: **NovaBank International**, banco ficticio, necesita reemplazar el 2PC por el patrón Saga (modelo BASE) para transferencias interbancarias de alto valor. Hay que implementar y contrastar **Orquestación** (Prefect) y **Coreografía** (eventos), con compensaciones estrictas en reversa, idempotencia, y observabilidad de cada paso.

- **Equipo:** Persona A y Persona B.
- **Plazo:** 7 días calendario desde el kickoff (ver fecha real en la Bitácora, sección 6).
- **Entregables:** repo ejecutable con instrucciones, documento comparativo Orquestación vs. Coreografía, diagrama de arquitectura (C4) + diagrama de la máquina de estados de la Saga, video demostrativo (máx. 6 min).
- **Checklist interactivo del equipo (fases, progreso compartido):** https://claude.ai/code/artifact/f39c5f39-84d8-4202-b241-17c1c58b7316

### Reparto de trabajo

| Quién | Dueño de | Modo que valida |
|---|---|---|
| **Persona A** | 3 microservicios de dominio + API Gateway + flow completo en Prefect | Orquestación (CP-01 a CP-05) |
| **Persona B** | Bus de eventos + wrappers de eventos sobre los servicios de A + frontend/simulador de caos + delays y dashboard | Coreografía (CP-01 a CP-05) |
| **Juntos** | Kickoff, matriz de pruebas cruzada, documentación, video, autoevaluación final | — |

### Rúbrica (0.0–5.0), para priorizar esfuerzo

| Criterio | Peso | Fase relacionada |
|---|---|---|
| Lógica de Saga y compensaciones | 40% | Fase 2 |
| Orquestación vs. Coreografía | 20% | Fase 3 |
| Observabilidad, delays, trazabilidad | 15% | Fase 4 |
| Frontend y simulador de caos | 10% | Fase 5 |
| Microservicios y aislamiento de datos | 10% | Fase 1 |
| Documentación, video, despliegue | 5% | Fase 7 |

## 2. Stack (decisión vigente — actualizar si cambia)

| Capa | Tecnología | Nota |
|---|---|---|
| Frontend | React + Vite | — |
| API Gateway | FastAPI (Python) | genera `X-Idempotency-Key` (UUID v4) |
| Cuentas / Riesgo / Pasarela | FastAPI (Python) | mismo lenguaje que el gateway y el orquestador; alternativa: Spring Boot si el equipo lo prefiere |
| Orquestador | Prefect 2/3, self-hosted vía Docker | flows con tasks de compensación explícitas |
| Bus de eventos (coreografía) | Redis Streams | alternativa: RabbitMQ/Kafka |
| Base de datos | Supabase (Postgres administrado) | un proyecto o esquema por servicio, para mantener el aislamiento de datos sin levantar Postgres localmente |
| Infraestructura | Docker Compose | levanta gateway, microservicios, orquestador y bus con un solo comando |

## 3. Contratos entre servicios (fuente de verdad — no romper sin avisar)

> Versión formal y navegable en `contracts/openapi.yaml` (llamadas síncronas)
> y `contracts/events.asyncapi.yaml` (eventos) — lo de abajo es el resumen
> rápido. `contracts/README.md` explica cómo viajan `modo` y `simulacion`
> desde el frontend hasta cada servicio.

### Máquina de estados de la transferencia
```
PENDIENTE → DEBITADO → RIESGO_OK → LIQUIDADO → CONFIRMADO
                 ↘ RECHAZADO_FONDOS (falla antes de debitar)
                 ↘ RECHAZADO_RIESGO (se revierte el débito)
                 ↘ RECHAZADO_RED    (se revierte riesgo + débito, en ese orden)
```

### Endpoints REST (modo orquestado — los llama el flow de Prefect)
> Campos en **snake_case** (`transfer_id`, `cuenta_origen`, …) — así quedaron implementados en `common/models.py`, los tres `routes.py` y `contracts/openapi.yaml`. La propuesta de kickoff los tenía en camelCase; esta sección ya refleja lo realmente construido.
- `POST /cuentas/{cuentaId}/debitar` `{transfer_id, monto, simulacion?}`
- `POST /cuentas/{cuentaId}/acreditar` `{transfer_id, monto}`
- `POST /cuentas/{cuentaId}/revertir-debito` `{transfer_id, monto}`
- `POST /riesgo/validar` `{transfer_id, cuenta_origen, monto, simulacion?}`
- `POST /riesgo/revertir` `{transfer_id}`
- `POST /pasarela/liquidar` `{transfer_id, cuenta_destino, monto, simulacion?}`
- `POST /transferencias` (Gateway) `{cuenta_origen, cuenta_destino, monto, modo: "orquestacion"|"coreografia", simulacion?: {fondos_insuficientes, fraude, timeout_pasarela, reintento_duplicado}}` → asigna `transfer_id`, header `X-Idempotency-Key`. Según `modo`, el Gateway **llama al orquestador** (Prefect) o **publica `TransferenciaSolicitada`** en el bus — nunca ambos.
- `GET /transferencias/{transferId}` (Gateway) → estado actual + `pasos` (Redis, rápido — lo que usa el frontend para el polling).
- `GET /transferencias/{transferId}/auditoria` (Gateway) → historial DURABLE de transiciones de estado desde Postgres (`bitacora.transiciones` — ver `common/schema_bitacora.sql`), con `estado_anterior`, `estado_nuevo`, `motivo` (causa del rechazo, null si fue una transición de éxito) y timestamp por cada cambio. Sobrevive un reinicio de Redis; el 404 significa que `AUDIT_DATABASE_URL` no está configurada o la transferencia no tiene transiciones registradas todavía.
- `GET /transferencias/{transferId}/eventos` (Gateway) → trazabilidad de Coreografía: lee el bus de eventos directo (`common/events.leer_eventos`) y devuelve, en orden, los eventos de dominio publicados para esa transferencia. Es el equivalente al Prefect UI para el modo sin coordinador — en Orquestación normalmente solo va a aparecer `TransferenciaSolicitada`, porque el resto de los pasos no pasa por el bus.
- Idempotencia a nivel de cada microservicio: los endpoints de escritura (`debitar`, `acreditar`, `liquidar`, …) deben usar `transfer_id` como clave para no aplicar dos veces la misma operación si llega repetida — el Criterio 5 de la rúbrica la evalúa aparte de la idempotencia del Gateway.
- El frontend guarda los switches de caos en camelCase (`fondosInsuficientes`, `timeoutPasarela`, …) y los traduce a snake_case en `frontend/src/api.js` antes de enviarlos — si agregan un switch nuevo, hay que agregarlo también ahí o Pydantic lo descarta en silencio.

### Eventos de dominio (modo coreografía — mismo payload base: `EventoBase` = `transfer_id`, `cuenta_origen`, `cuenta_destino`, `monto`, `simulacion?`)
- `TransferenciaSolicitada` — `EventoBase`. Publica: gateway. Escucha: accounts-service.
- `SaldoDebitado` — `EventoBase`. Publica: accounts-service. Escucha: risk-service.
- `RiesgoAprobado` — `EventoBase`. Publica: risk-service. Escucha: clearing-service.
- `RiesgoRechazado` — `EventoBase + {motivo}`. Publica: risk-service. Escucha: accounts-service (revertir_debito).
- `LiquidacionConfirmada` — `EventoBase`. Publica: clearing-service. Escucha: accounts-service (acreditar destino).
- `TransferenciaFallida` — `EventoBase + {fase, motivo}`. Publica: clearing-service. Escuchan risk-service (revertir aprobación) **y** accounts-service (revertir débito) — ambos reaccionan al mismo evento sin orden garantizado entre sí; accounts-service deja el estado final porque su compensación es la última del orden inverso.
- `CompensacionEjecutada` — `EventoBase + {servicio: "cuentas"|"riesgo"}`. Publican accounts-service y risk-service, cada uno tras compensar. (No lleva campo `accion` — se quitó al implementar.)

> Contrato formal y navegable en `contracts/openapi.yaml` y `contracts/events.asyncapi.yaml` — ya implementado y verificado contra el código (no es solo la propuesta de kickoff). Si agregan o renombran un campo, actualicen los tres lugares (código, ambos YAML, esta sección) en el mismo commit.

## 4. Convenciones técnicas

- Idempotencia: header `X-Idempotency-Key` (UUID v4), generado por el Gateway, propagado a todos los servicios.
- Delay configurable por paso: variable de entorno `STEP_DELAY_MS` (rango 2000–4000).
- Nombres de servicio sugeridos en `docker-compose.yml`: `gateway`, `prefect-server` (UI en :4200), `orchestrator` (bridge propio en :8010 — no confundir con el puerto de Prefect), `accounts-service`, `risk-service`, `clearing-service`, `event-bus`, `frontend`. Las bases de datos viven en Supabase (no en el compose): un proyecto o esquema por servicio (`accounts`, `risk`, `clearing`), con su connection string propia en el `.env` de cada servicio.
- `PREFECT_API_URL` (en el contenedor `orchestrator`) apunta a `prefect-server`, y es lo que hace que cada `@flow`/`@task` reporte sus estados al Prefect UI. No confundirlo con `ORCHESTRATOR_URL` (en el `gateway`), que es el bridge HTTP propio hacia `orchestrator:8010` — dos cosas distintas con nombres parecidos.
- Estados finales válidos: `CONFIRMADO`, `RECHAZADO_FONDOS`, `RECHAZADO_RIESGO`, `RECHAZADO_RED`.

## 5. Matriz de casos de prueba (marcar al validar cada uno)

| Caso | Disparador | Compensación esperada | Estado final |
|---|---|---|---|
| CP-01 | Transferencia normal | Ninguna | CONFIRMADO |
| CP-02 | Monto > saldo disponible | Rechazo inmediato, sin reversas | RECHAZADO_FONDOS |
| CP-03 | Switch de fraude | Reembolso del débito | RECHAZADO_RIESGO |
| CP-04 | Switch de timeout en pasarela | Anula riesgo + reintegra débito, en ese orden | RECHAZADO_RED |
| CP-05 | Reenvío del mismo `transferId`/idempotency-key | Reconoce duplicado, no cobra dos veces | igual al original |

**Orquestación:**
- [x] CP-01 (2026-09-18, IA — POST /transferencias vía Gateway real, CONFIRMADO, bitácora completa debitar→validar→liquidar→acreditar)  - [x] CP-02 (2026-09-18, IA — RECHAZADO_FONDOS, bitácora solo con "debitar" rechazado, sin ninguna reversa, saldo de ACC-001 sin cambios)  - [x] CP-03 (2026-09-18, IA — POST /transferencias vía Gateway real, RECHAZADO_RIESGO, bitácora debitar→validar(rechazado)→revertir_debito, saldo de ACC-001 vuelve exacto al valor previo)  - [x] CP-04 (2026-09-18, IA — POST /transferencias vía Gateway real, RECHAZADO_RED, bitácora debitar→validar→liquidar(fallido)→revertir(riesgo)→revertir_debito en ese orden estricto por timestamp, saldo de ACC-001 vuelve exacto al valor previo)  - [x] CP-05 (2026-09-18, IA — reenvío inmediato del mismo X-Idempotency-Key mientras la saga original seguía PENDIENTE: mismo transfer_id, bitácora con un solo "debitar", saldo de ACC-001 bajó una sola vez)

**Coreografía:**
- [x] CP-01 (2026-09-18, IA — POST /transferencias modo=coreografia vía Gateway real, DEBITADO→RIESGO_OK→LIQUIDADO→CONFIRMADO)  - [x] CP-02 (2026-09-18, IA — RECHAZADO_FONDOS, bitácora solo con "debitar" rechazado, saldo sin cambios)  - [x] CP-03 (2026-09-18, IA — RECHAZADO_RIESGO, evento RiesgoRechazado con motivo=fraude_simulado + CompensacionEjecutada confirmados en el stream)  - [x] CP-04 (2026-09-18, IA — RECHAZADO_RED, evento TransferenciaFallida con fase=pasarela/motivo=timeout_pasarela + 2 CompensacionEjecutada confirmados en el stream)  - [x] CP-05 (2026-09-18, IA — reenvío inmediato del mismo X-Idempotency-Key, mismo transfer_id, un solo débito aplicado)

## 6. Bitácora de cambios (agregar una entrada por sesión de trabajo)

```
### 2026-09-12 — Kickoff
Autor: equipo
Definidos: reparto de trabajo (A: orquestación, B: coreografía + UI), stack sugerido,
máquina de estados, contratos iniciales de endpoints y eventos (sección 3, aún sin
implementar). Checklist interactivo de fases publicado. Sin código todavía.
```

```
### 2026-09-12 — Scaffold funcional de punta a punta
Autor: IA (revisión de código, sin cambios — entrada agregada para que la bitácora
refleje lo que ya existe en el repo, regla 5/6 de la sección 0)
Qué hay: gateway (idempotencia + dispatch por `modo`), los 3 microservicios con
lógica de negocio única en `app/core.py` compartida por `routes.py` (orquestación)
y `events_worker.py` (coreografía) — regla 3 respetada en los tres —, flow de
Prefect con compensación en orden inverso correcto para CP-04, bus de eventos
sobre Redis Streams, frontend con formulario + switches de caos + timeline por
polling, contratos formalizados (`contracts/openapi.yaml` y `events.asyncapi.yaml`),
docker-compose completo (incluye `prefect-server` real en :4200) y diagramas C4 /
estados iniciales en `docs/`. CP-01 corre de punta a punta en ambos modos
(`orchestrator/run_demo.py`).
Contrato afectado: ninguno — nombres de eventos/endpoints/campos siguen igual que
la sección 3.
Pendiente detectado (no bloqueante para seguir trabajando, sí para la entrega):
persistencia real en Supabase (hoy in-memory en los 3 servicios, TODO en cada
`store.py`/`.env.example`), `tests/test_cp_matrix.py` con los 5 casos en
`@pytest.mark.skip` (no hay reset de cuentas entre corridas todavía), el frontend
no reenvía el mismo `X-Idempotency-Key` así que CP-05 no se puede demostrar aún
desde la UI, y en coreografía el orden "riesgo antes que débito" de CP-04 no está
garantizado (risk-service y accounts-service reaccionan a `TransferenciaFallida`
de forma independiente) — vale la pena documentarlo como diferencia real frente a
orquestación en `docs/orquestacion-vs-coreografia.md` en vez de dejarlo implícito.
```

```
### 2026-09-17 — Fix: switches de caos no llegaban al backend + sección 3 corregida
Autor: IA
Qué cambió: `frontend/src/api.js` traduce ahora `simulacion` de camelCase (estado
de React) a snake_case (lo que espera `common/models.py`/Pydantic) antes de
enviarla al Gateway. Antes, `fondosInsuficientes` y `timeoutPasarela` no
coincidían con `fondos_insuficientes`/`timeout_pasarela`, Pydantic las
descartaba en silencio y quedaban en `False` — solo el switch "fraude"
funcionaba desde la UI (CP-02 y CP-04 eran imposibles de disparar desde el
frontend, aunque sí funcionaban por curl/run_demo.py). Además se revisaron
`contracts/openapi.yaml` y `contracts/events.asyncapi.yaml` campo por campo
contra el código real — ambos coinciden exactamente con la implementación.
Contrato afectado: sección 3 de este archivo, que seguía en camelCase (kickoff)
y listaba un campo `accion` en `CompensacionEjecutada` que nunca se implementó
— corregida para reflejar los nombres reales (snake_case) y el payload real de
cada evento, con quién publica/escucha cada uno.
```

```
### 2026-09-17 — accounts-service conectado a Postgres (Fase 1, parcial)
Autor: IA
Qué cambió: `services/accounts-service/app/store.py` reemplaza el dict en
memoria por Postgres (esquema `accounts`, tablas `cuentas` y `movimientos` —
ver `services/accounts-service/schema.sql`). Cada operación corre en una
transacción: revisa primero `movimientos` por (transfer_id, tipo) — si ya
existe, es idempotencia real a nivel de base (respaldo durable del cache de
Redis) — y si no, bloquea la fila de `cuentas` con `SELECT ... FOR UPDATE`
antes de actualizar el saldo, para que dos operaciones concurrentes sobre la
misma cuenta no lean el mismo saldo viejo. `app/core.py` se ajustó a la nueva
firma de `store.py` (recibe `transfer_id`) pero su lógica de negocio no
cambió — `routes.py` y `events_worker.py` siguen llamando las mismas
funciones sin tocar (regla 3 intacta). Se agregó `psycopg[binary]` a
`requirements.txt`, `DATABASE_URL` (vía `ACCOUNTS_DATABASE_URL`) a
`docker-compose.yml` y al `.env.example` raíz, y se corrigió el
`DATABASE_URL` de ejemplo del servicio (el `?schema=` que tenía antes no es
válido en Postgres; las tablas ya van calificadas en el código).
Contrato afectado: ninguno — mismos endpoints, mismos payloads de
`openapi.yaml`. Es un cambio de implementación interna, no de contrato.
Pendiente: risk-service y clearing-service siguen en memoria (sus
`schema.sql` ya existen, falta cablearlos igual).
```

```
### 2026-09-17 — CP-01 verificado de punta a punta en Orquestación + fix de dependencia
Autor: IA
Qué cambió: se levantó el stack real (Prefect server, gateway, los 3
microservicios) con un Postgres local desechable para accounts-service (no
Supabase — solo para esta verificación) y se corrió `orchestrator/run_demo.py`.
Encontrado y arreglado un bug real: `orchestrator/requirements.txt` no fijaba
`anyio`, pip resolvía la última (4.15.1), y aunque las 4 tasks de negocio
(debitar, validar_riesgo, liquidar, acreditar) terminaban bien contra los
servicios reales, el flow de Prefect crasheaba al cerrar con "Can't
instantiate abstract class GatherTaskGroup" — un incompatibilidad entre
prefect==2.20.7 y versiones de anyio 4.x más nuevas que las que ese release
probó. El flow run quedaba en Prefect como CRASHED en vez de COMPLETED,
rompiendo la Fase 4 (observabilidad) aunque el dinero se hubiera movido bien.
Fix: se fijó `anyio==4.4.0` (la mínima que prefect 2.20.7 declara soportar,
`>=4.4.0,<5.0.0`). Confirmado en Prefect UI (:4200): el flow run pasó de
CRASHED a COMPLETED, estado final CONFIRMADO, saldos y `movimientos` en
Postgres correctos (débito y crédito de 10.000 en ACC-001/ACC-002).
Contrato afectado: ninguno — es un pin de dependencia, no un cambio de
lógica ni de contrato. Matriz de la sección 5: CP-01 marcado en Orquestación.
Nota para Persona A: este mismo pin de `anyio` probablemente hace falta
también si en algún momento se corre Prefect fuera de Docker (entorno local).
```

```
### 2026-09-17 — risk-service conectado a Postgres con reglas configurables (Fase 1)
Autor: IA
Qué cambió: `services/risk-service/app/store.py` (nuevo) reemplaza el
`LIMITE_DIARIO` hardcodeado de `app/rules.py` por reglas reales en Postgres
(esquema `risk` — ver `services/risk-service/schema.sql`): `risk.limites`
(límite diario acumulado y monto máximo por transferencia, configurables por
cuenta, con defaults en código si una cuenta no tiene fila propia),
`risk.evaluaciones` (idempotencia durable + registro para que revertir()
sepa cuánto descontar) y `risk.acumulado_diario` (acumulado real por cuenta
y día). `app/rules.py` quedó como función pura `evaluar(monto, monto_maximo,
limite_diario, acumulado_hoy)`, testeable sin base de datos. `validar()`
bloquea la fila del acumulado del día con `SELECT ... FOR UPDATE` antes de
decidir, para que dos validaciones concurrentes sobre la misma cuenta no
lean el mismo acumulado viejo. El switch de fraude (`simulacion.fraude`)
se resolvió en `app/core.py`, sin tocar la base — mismo criterio que
`fondos_insuficientes` en accounts-service: un rechazo forzado no evaluó
ninguna regla real, así que no hay nada que persistir. `routes.py` y
`events_worker.py` no cambiaron (regla 3 intacta).
Contrato afectado: ninguno — mismos endpoints y payloads de `openapi.yaml`
(`POST /riesgo/validar` y `/riesgo/revertir` siguen igual; `revertir` sigue
recibiendo solo `transfer_id`, cuenta_origen/monto se recuperan de la
evaluación 'validar' original guardada en `risk.evaluaciones`).
Verificado en vivo contra el stack real: aprobado dentro de límites,
`excede_monto_maximo` (monto > 20M), `excede_limite_diario` (acumulado + monto
> 50M) con `risk.acumulado_diario` sumando correctamente, `revertir()`
restando exactamente lo aprobado (y no restando dos veces en un reintento),
y CP-01/CP-03 completos de punta a punta por el orquestador (CONFIRMADO /
RECHAZADO_RIESGO, saldo de ACC-001 consistente tras debitar + revertir).
Pendiente: clearing-service sigue en memoria (su `schema.sql` ya existe).
```

```
### 2026-09-18 — clearing-service conectado a Postgres (Fase 1 completa)
Autor: IA
Qué cambió: `services/clearing-service/app/store.py` (nuevo) reemplaza el
core sin persistencia por Postgres (esquema `clearing`, tabla
`clearing.liquidaciones` — ver `services/clearing-service/schema.sql`).
A diferencia de fondos_insuficientes en accounts-service y fraude en
risk-service, el switch de timeout de este servicio SÍ persiste el intento
fallido (estado `fallida` + motivo) — un timeout real de una pasarela
externa es un intento que de verdad ocurrió, no una validación previa que
corta antes de hacer nada. `UNIQUE(transfer_id)` basta para la idempotencia
acá (liquidar es la única operación, sin columna `operacion` como en los
otros dos). `routes.py` y `events_worker.py` no cambiaron (regla 3 intacta).
Contrato afectado: ninguno — mismos endpoints y payloads.
Con esto los 3 microservicios de dominio quedan conectados a Postgres —
Fase 1 completa en cuanto a persistencia (falta que el equipo cree los
proyectos reales de Supabase; hoy solo hay `.env.example` por servicio).
Verificado en vivo: liquidación exitosa, timeout forzado, reintento
idempotente sin duplicar fila, y CP-01/CP-04 completos de punta a punta por
el orquestador (CONFIRMADO / RECHAZADO_RED, con revertir_riesgo antes que
revertir_debito, orden correcto) — saldo de ACC-001 y acumulado diario de
riesgo consistentes al final, incluyendo el corte de día en
`risk.acumulado_diario` (current_date). Matriz de la sección 5: CP-03 y
CP-04 marcados en Orquestación (ya habían sido validados en sesiones
anteriores pero no se habían marcado).
```

```
### 2026-09-18 — Supabase real conectado (Fase 1 cerrada de verdad)
Autor: Persona A (proyectos y esquemas vía SQL Editor) + IA (conexión y verificación)
Qué cambió: los 3 microservicios corren contra proyectos reales de Supabase
— `accounts-service` y `risk-service` comparten un proyecto (esquemas
`accounts` y `risk` aislados dentro de él), `clearing-service` tiene su
propio proyecto (esquema `clearing`). Las referencias de proyecto van solo
en los `.env` no versionados, no en este archivo. Los
`.env` de cada servicio y el `.env` de la raíz (no versionados, ver
`.gitignore`) ya están completos con las connection strings reales.
Gotcha importante encontrado y corregido: la conexión directa de Supabase
(`db.<ref>.supabase.co`) resuelve **solo a IPv6**, y Docker Desktop en esta
máquina no tiene salida IPv6 — así que ningún contenedor podía conectar
aunque la contraseña estuviera bien. Hubo que usar el **connection pooler**
(Transaction pooler, `aws-0-<region>.pooler.supabase.com:6543`, usuario
`postgres.<project-ref>` en vez de `postgres`). Actualizados los 4
`.env.example` (raíz + los 3 servicios) para que el equipo no se tropiece
con esto de nuevo.
Contrato afectado: ninguno.
Verificado en vivo contra Supabase real (no el Postgres local desechable de
sesiones anteriores): los 3 endpoints (`/cuentas/.../saldo`,
`/riesgo/validar`, `/pasarela/liquidar`) responden correctos, y CP-01
completo de punta a punta por el orquestador — CONFIRMADO, ACC-001
1.000.000 → 990.000, ACC-002 500.000 → 510.000. Con esto Fase 1 queda
cerrada de verdad (antes solo estaba verificado contra un Postgres local).
```

```
### 2026-09-18 — Aislamiento de datos: gap real encontrado y corregido (Criterio 5)
Autor: IA
Qué se encontró: el código de los 3 servicios nunca cruza esquemas (grep
confirmado: cada `app/store.py` solo referencia tablas de su propio
esquema), pero a nivel de base de datos NO había aislamiento real entre
accounts-service y risk-service — ambos comparten un proyecto de Supabase y
ambos usaban el rol `postgres` (superusuario del proyecto), que puede leer y
escribir cualquier esquema. Lo probé en vivo: con las credenciales de
accounts-service pude hacer `select * from risk.limites` sin ningún error, y
viceversa. `clearing-service` (proyecto separado) sí tenía aislamiento real
— probé que ni siquiera puede ver que el esquema `accounts` existe.
Fix aplicado: creé un rol de Postgres dedicado por esquema —
`accounts_role`, `risk_role` (en el proyecto compartido) y `clearing_role`
(en el suyo, reemplazando ahí también al `postgres` compartido, por
privilegio mínimo frente a los esquemas internos de Supabase como
auth/storage) — cada uno con `GRANT` únicamente sobre su propio esquema
(tablas + secuencias, más `ALTER DEFAULT PRIVILEGES` para que tablas nuevas
hereden el mismo permiso). Verificado: `accounts_role` contra `risk.limites`
y `risk_role` contra `accounts.cuentas` ahora dan `ERROR: permission denied
for schema` — el aislamiento ya lo impone la base, no solo la disciplina del
código. Los 3 `.env` de servicio y el `.env` de la raíz quedaron apuntando a
estos roles nuevos (contraseñas generadas al azar, no las de la cuenta de
Supabase). Confirmado que todo sigue funcionando igual: CP-01 completo de
punta a punta con los roles nuevos, estado CONFIRMADO.
Contrato afectado: ninguno — es un cambio de permisos de base de datos, no
de lógica ni de contrato.
```

```
### 2026-09-18 — Gateway: idempotency-key devuelto al cliente (habilita CP-05 real)
Autor: IA
Qué cambió: `gateway/app/main.py` ahora devuelve el `X-Idempotency-Key`
usado (el que mandó el cliente, o el generado por el Gateway si no mandó
ninguno) como header de la respuesta de `POST /transferencias`. Antes, si el
cliente no mandaba su propio header, el Gateway generaba uno nuevo en cada
request y nunca lo comunicaba de vuelta — así que ningún cliente que no
generara su propio UUID podía reintentar con el mismo key, y CP-05 era
estructuralmente imposible de disparar (más allá de con curl a mano).
Contrato afectado: `contracts/openapi.yaml` — agregado el header de
respuesta `X-Idempotency-Key` en `POST /transferencias`.
Verificado en vivo contra el Gateway real (no `run_demo.py`, que lo evita):
- Orquestación: primera request sin header -> el Gateway genera uno y lo
  devuelve; reenvío con ese mismo header -> mismo `transfer_id`, sin volver
  a despachar — confirmado que ACC-001 solo se debitó una vez pese a las dos
  requests idénticas.
- Coreografía: `POST /transferencias` con `modo: coreografia` (con los 3
  workers de eventos levantados) corrió de punta a punta — DEBITADO →
  RIESGO_OK → LIQUIDADO → CONFIRMADO, bitácora completa en `GET
  /transferencias/{id}`.
Pendiente (ya trackeado): el frontend todavía no captura ni reenvía este
header — sigue siendo el TODO de Fase 5 para demostrar CP-05 desde la UI,
ahora ya sin bloqueante del lado del Gateway.
```

```
### 2026-09-18 — Idempotencia de los 6 endpoints de escritura verificada (Criterio 5)
Autor: IA (verificación, sin cambios de código — ya estaba implementado al
construir cada servicio; esta entrada documenta la prueba explícita que
pide el Criterio 5)
Qué se probó: los 6 endpoints de escritura de los 3 microservicios
(`/cuentas/{id}/debitar`, `/acreditar`, `/revertir-debito`,
`/riesgo/validar`, `/riesgo/revertir`, `/pasarela/liquidar`) contra el
stack real (Supabase), cada uno con el mismo `transfer_id` enviado dos
veces. Para 3 de los 6 (uno por cada patrón de restricción única:
`accounts.movimientos` UNIQUE(transfer_id, tipo), `risk.evaluaciones`
UNIQUE(transfer_id, operacion), `clearing.liquidaciones`
UNIQUE(transfer_id)) se hizo la prueba rigurosa: se borró el key de
idempotencia en Redis (`idemp:{transfer_id}:{operacion}`) entre el primer y
el segundo request, para que el segundo intento NO tuviera ayuda del cache
rápido y dependiera solo de la restricción de la base — en los tres casos
el efecto (débito, evaluación de riesgo, liquidación) se aplicó una sola
vez, confirmado tanto por la respuesta HTTP idéntica como por el conteo de
filas en la tabla correspondiente. Los otros 3 endpoints (`acreditar`,
`revertir-debito`, `revertir`) usan exactamente el mismo mecanismo dentro
del mismo servicio, así que no hizo falta repetir la prueba con bypass de
Redis en los seis — la cobertura por patrón de restricción es completa.
Contrato afectado: ninguno.
```

```
### 2026-09-18 — Retries + on_failure hooks en el flow de Prefect (fallo transitorio vs. de negocio)
Autor: IA
Qué cambió: `orchestrator/flows/transferencia_flow.py` — las 6 tasks HTTP
(`debitar`, `validar_riesgo`, `liquidar`, `acreditar`, `revertir_debito`,
`revertir_riesgo`) ahora tienen `retries=2, retry_delay_seconds=2` y un
`retry_condition_fn` que solo reintenta errores de red/timeout/5xx — un 4xx
(bug determinístico de payload) no se reintenta. La distinción
transitorio/negocio no necesitó lógica nueva: un rechazo de negocio
(fondos_insuficientes, fraude, timeout_pasarela) ya volvía como
`{"ok": false, ...}` sin lanzar excepción — Prefect nunca lo ve como fallo
de task. Solo un error real (conexión caída, timeout, 5xx) lanza excepción,
que es lo único que retries/on_failure pueden interceptar.
Se agregó `on_failure` a nivel de task (`_log_fallo_transitorio`, deja un
paso `error_transitorio` en la bitácora con cuántos intentos hizo y el
error) y a nivel de flow (`_log_flow_fallido`, deja constancia de que la
Saga no llegó a un estado final de negocio). No se agregó ningún estado
final nuevo a `common/models.py` — el `estado` de la transferencia queda en
el último valor de negocio alcanzado (p.ej. DEBITADO); la señal clara de
"esto se rompió de verdad" es que el flow run queda como Failed en el
Prefect UI, visualmente distinto de un RECHAZADO_* que sí es un Completed.
Bug encontrado y corregido en el camino: `TaskRun` no tiene atributo
`.parameters` en `prefect==2.20.7` (sí lo tiene `FlowRun`, asimetría rara)
— el hook de task sacaba `transfer_id` de `TaskRunContext.get().parameters`
en vez de `task_run.parameters`.
Verificado en vivo: paré `accounts-service` con el contenedor apagado a
propósito y corrí una transferencia — `clients.debitar` reintentó 3 veces
en total (1 inicial + 2 reintentos) antes de rendirse, el hook de task
registró `{"intentos": 3, "error": "..."}"` en la bitácora, el hook de flow
registró el aviso general, y el flow run quedó en estado `Failed` en
Prefect (distinto de un `Completed` con RECHAZADO_*). Repuesto
`accounts-service` y confirmado que CP-01 vuelve a correr normal.
Contrato afectado: `contracts/openapi.yaml`/eventos no cambian — esto es
comportamiento interno del orquestador, no un endpoint ni un payload nuevo.
```

```
### 2026-09-18 — Bitácora de auditoría durable de transiciones de estado
Autor: IA
Qué cambió: `common/status_store.py` — `set_estado()` ahora, además de
actualizar `transferencia:{id}:estado` en Redis (rápido, para el polling
del frontend, sin cambios), inserta una fila en `bitacora.transiciones`
(Postgres — ver `common/schema_bitacora.sql`) con estado_anterior,
estado_nuevo y timestamp. Es la ruta DURABLE: `transferencia:{id}:estado`
en Redis solo guarda el valor actual y se pierde si ese contenedor se
reinicia (no hay volumen de persistencia configurado para `event-bus`);
`bitacora.transiciones` sobrevive eso. Nuevo endpoint `GET
/transferencias/{id}/auditoria` en el Gateway para consultarla (además de
SQL directo). Se agregó `get_transiciones()` en el mismo módulo.
`bitacora.transiciones` es cross-cutting (no pertenece a ningún
microservicio — la escriben las 8 piezas que llaman set_estado: gateway,
orchestrator, y los 3 microservicios + sus 3 workers), así que vive en
`common/`, no en `services/*/`, y su esquema `bitacora` está en el mismo
proyecto de Supabase que accounts+risk (esquema propio, aislado igual que
los demás). Rol dedicado `bitacora_role` con permisos SOLO
`INSERT`+`SELECT` — sin `UPDATE`/`DELETE`, verificado en vivo que ambos
fallan con "permission denied": inmutabilidad real de un log de auditoría,
impuesta por la base, no solo por convención de código. Si
`AUDIT_DATABASE_URL` no está configurada, `set_estado`/`get_transiciones`
degradan con gracia (no rompen el resto del sistema) — mismo patrón que
`DATABASE_URL` en cada microservicio.
Se agregó `psycopg[binary]` a `gateway/requirements.txt` y
`orchestrator/requirements.txt` (los 3 microservicios ya lo tenían), y
`AUDIT_DATABASE_URL` a las 8 piezas en `docker-compose.yml` + al `.env` de
la raíz.
Contrato afectado: `contracts/openapi.yaml` — nuevo `GET
/transferencias/{transferId}/auditoria`.
Verificado en vivo: CP-01 en Orquestación (vía `run_demo.py`) y en
Coreografía (vía Gateway con `modo: coreografia`) — en ambos casos
`bitacora.transiciones` y el nuevo endpoint muestran las 5 transiciones
completas (null→PENDIENTE→DEBITADO→RIESGO_OK→LIQUIDADO→CONFIRMADO) con
timestamps reales espaciados por el delay simulado, escritas por procesos
distintos según el modo (orchestrator en un caso, los 3 workers de eventos
en el otro) sin conflictos.
```

```
### 2026-09-18 — Bus de eventos: justificación documentada + 2 bugs de resiliencia reales
Autor: IA
Qué se documentó: `docs/bus-de-eventos.md` (nuevo) — por qué Redis Streams
y no RabbitMQ/Kafka: entrega con ack (`XACK`), un cursor por servicio (3
consumer groups), reintento de mensajes no confirmados, y sobre todo cero
infraestructura nueva (Redis ya corría para idempotencia y la bitácora de
estado). Comparativa completa + trade-offs aceptados + cómo migrar más
adelante si hiciera falta (el contrato en `events.asyncapi.yaml` ya está
escrito para que sea un cambio de transporte, no de diseño).
Qué se encontró y arregló en el camino (probando la afirmación "sobrevive
un reinicio" antes de escribirla, no dándola por sentada):
1. `event-bus` no tenía volumen — un reinicio del contenedor borraba el
   stream completo y los offsets de los 3 consumer groups. Fix:
   `docker-compose.yml` ahora levanta Redis con `--appendonly yes` +
   volumen `event-bus-data`.
2. Los 3 workers de eventos (`common/events.py`, función `consumir()`)
   morían con `ConnectionError` sin capturar cuando `event-bus` se
   reiniciaba — confirmado matando el contenedor a mitad de una Saga en
   Coreografía: los 3 workers crashearon. Peor: el primer intento de fix
   (solo envolver el `xreadgroup` inicial) no alcanzaba, porque el corte
   real pasaba en el `xack` de después de procesar el mensaje — y ese xack
   corría SIEMPRE, incluso si el handler fallaba, así que un evento podía
   quedar marcado como "procesado" sin haberse aplicado nunca. Fix
   definitivo: todo el cuerpo del loop (los dos `xreadgroup` + el `xack`)
   dentro del mismo `try/except ConnectionError` (reintenta en 2s,
   recrea el consumer group si hace falta), y el `xack` ahora solo corre
   si el handler no lanzó excepción — un mensaje que falla queda pendiente
   y se reintenta en la próxima vuelta del loop (se agregó una lectura de
   `{STREAM: "0"}` — pendientes propios — antes de pedir mensajes nuevos).
   De paso, se agregó `PYTHONUNBUFFERED=1` a los 5 Dockerfiles: sin esto,
   los `print()` de diagnóstico quedaban en el buffer de stdout y no se
   veían en `docker logs` mientras el proceso seguía vivo — así fue como
   el primer fix pareció funcionar cuando en realidad no había arreglado
   nada, hasta que revisé el estado real con `XPENDING`/`XINFO GROUPS`.
Se agregó también `restart: unless-stopped` a los 10 servicios de
`docker-compose.yml` como defensa adicional (para cualquier otro crash
futuro, no solo este).
Contrato afectado: ninguno — todo es infraestructura y resiliencia interna.
Verificado en vivo, prueba final: transferencia en Coreografía disparada,
`event-bus` reiniciado a mitad de camino (`docker restart`) — los 3
workers no crashearon (mismo uptime antes/después) y la transferencia
llegó completa a CONFIRMADO. `XINFO GROUPS` después: `pending: 0, lag: 0`
en los tres grupos — sin mensajes huérfanos.
```

```
### 2026-09-18 — Los 6 eventos de dominio verificados en vivo (faltaban RiesgoRechazado y TransferenciaFallida)
Autor: IA (verificación, sin cambios de código — ya estaban definidos en
`contracts/events.asyncapi.yaml` y publicados desde cada `events_worker.py`;
esta entrada es la prueba explícita en vivo de los 6, no solo el camino feliz)
Qué se probó: CP-03 (fraude) y CP-04 (timeout de pasarela) en modo
Coreografía vía el Gateway real — antes solo se había corrido CP-01 en ese
modo, así que `RiesgoRechazado` y `TransferenciaFallida` nunca se habían
visto publicados de verdad. Se volcó el stream completo
(`XRANGE novabank:transferencias - +`) y se confirmaron los 6 + el séptimo
(`CompensacionEjecutada`) con el payload exacto que describe el contrato:
`RiesgoRechazado` con `motivo: "fraude_simulado"`, `TransferenciaFallida`
con `fase: "pasarela", motivo: "timeout_pasarela"` — ambos como `allOf`
sobre `EventoBase`, tal como está declarado en `events.asyncapi.yaml`.
También se confirmó el orden real de publicación en el stream para CP-04:
`TransferenciaSolicitada → SaldoDebitado → RiesgoAprobado →
TransferenciaFallida → CompensacionEjecutada(riesgo) →
CompensacionEjecutada(cuentas)` — coincide con la nota ya existente en el
contrato sobre que risk-service y accounts-service reaccionan al mismo
`TransferenciaFallida` de forma independiente (acá salió primero riesgo,
pero el contrato ya advierte que el orden entre esos dos no está
garantizado).
Contrato afectado: ninguno — confirma lo ya documentado, no lo cambia.
Matriz de la sección 5: CP-03 y CP-04 marcados también en Coreografía.
```

```
### 2026-09-18 — Fase 3 (Coreografía) cerrada: matriz completa, trazabilidad, causa del fallo, doc comparativo
Autor: IA
Qué se hizo (lista de pendientes de Fase 3 del checklist, todos en esta sesión):
1. **Matriz CP-01..CP-05 completa en Coreografía**: corridos CP-02 (RECHAZADO_FONDOS,
   sin reversas, saldo sin cambios) y CP-05 (reenvío inmediato del mismo
   X-Idempotency-Key, mismo transfer_id, un solo débito) vía el Gateway
   real — con esto los 5 casos están validados a mano en los dos modos.
2. **Revisión de acoplamiento**: confirmado por código (no por inspección
   visual) que ningún `events_worker.py` hace llamadas HTTP directas a otro
   servicio (`grep httpx` sin resultados) y que ningún worker escucha un
   evento que él mismo publica — sin dependencias circulares.
3. **Delays suficientes para ver la compensación, no solo el camino feliz**:
   medido con los timestamps reales de la corrida de CP-04 en Coreografía —
   gaps de 2.24s a 6.07s entre pasos, incluidas las dos
   `CompensacionEjecutada` en cadena. `STEP_DELAY_MS=3000` cumple.
4. **Causa del fallo en la bitácora durable**: `bitacora.transiciones` tenía
   estado_anterior/estado_nuevo/timestamp pero no el motivo del rechazo.
   Agregada columna `motivo` (migración `alter table ... add column if not
   exists` aplicada contra Supabase), `set_estado()` ahora acepta un
   parámetro `motivo` opcional, y se pasó el valor real en los 6 puntos
   donde se setea un RECHAZADO_* (3 en `orchestrator/flows/transferencia_flow.py`,
   3 en `services/accounts-service/app/events_worker.py` — es el único
   worker que setea estados de rechazo). Verificado en vivo en los dos
   modos: `motivo: "fraude_simulado"` en Coreografía, `motivo:
   "timeout_pasarela"` en Orquestación, `null` en transiciones de éxito.
5. **Vista de trazabilidad para Coreografía** (pieza que no existía):
   Orquestación tiene el Prefect UI; Coreografía no tenía ningún
   equivalente. Nuevo `common/events.leer_eventos(transfer_id)` (XRANGE
   sobre el stream completo, filtrado por transfer_id en el payload — Redis
   Streams no filtra por campo nativamente) y nuevo endpoint `GET
   /transferencias/{id}/eventos` en el Gateway. Verificado en vivo: devuelve
   la secuencia completa de eventos de dominio en orden cronológico.
6. **Documento comparativo** (`docs/orquestacion-vs-coreografia.md`,
   reescrito de punta a punta — antes era el template vacío de kickoff):
   acoplamiento, control de flujo, y el hallazgo concreto más importante —
   el orden de las compensaciones en CP-04 NO está garantizado en
   Coreografía (a diferencia de Orquestación, donde es secuencial y
   explícito), con los timestamps reales de una corrida como evidencia, no
   como afirmación teórica.
Contrato afectado: `contracts/openapi.yaml` — nuevo `GET
/transferencias/{transferId}/eventos`, y el campo `motivo` agregado al
schema de respuesta de `GET /transferencias/{transferId}/auditoria`.
Con esto, Fase 3 (Coreografía) y el Criterio 2 (Orquestación vs.
Coreografía, 20%) quedan con evidencia completa en ambos modos.
```

```
### 2026-09-18 — STEP_DELAY_MS realmente parametrizable en los 3 microservicios
Autor: IA
Qué se encontró: `STEP_DELAY_MS` solo estaba cableado en el bloque de
`orchestrator` en `docker-compose.yml` — y ahí es código muerto, porque
`orchestrator` nunca llama `simulate_delay()` (confirmado por grep: esa
función solo se usa dentro de `app/core.py` de los 3 microservicios). Los 3
servicios dependían del default hardcodeado en `common/status_store.py`
(3000ms) sin ninguna forma de cambiarlo salvo editar el código fuente — no
era "parametrizable" de verdad pese a funcionar.
Fix: agregado `STEP_DELAY_MS=${STEP_DELAY_MS:-3000}` a los 6 bloques de
`docker-compose.yml` que sí lo usan (accounts-service + worker, risk-service
+ worker, clearing-service + worker), leído del `.env` de la raíz (ya tenía
`STEP_DELAY_MS=3000`). Quitada la línea muerta de `orchestrator`, con un
comentario explicando por qué no va ahí.
Verificado en vivo: sobreescribí `STEP_DELAY_MS=1500` solo para
`risk-service` y medí `simulate_delay()` de forma aislada (sin ruido de red
a Supabase) — tardó exactamente 1.50s. Confirmado que el parámetro
realmente cambia el comportamiento, no es solo un valor decorativo.
Restaurado a 3000 (default) al terminar.
Contrato afectado: ninguno — es configuración de infraestructura.
```

```
### 2026-09-18 — Frontend: CP-05 real, auditoría/eventos en la UI, fix de CORS
Autor: IA
Qué cambió:
- `frontend/src/api.js`: `crearTransferencia` ahora acepta un
  `idempotencyKey` opcional (lo manda como header `X-Idempotency-Key`) y
  siempre devuelve el que el Gateway usó (capturado del header de
  respuesta). Nuevas `consultarAuditoria()` y `consultarEventos()` para los
  dos endpoints nuevos del Gateway.
- `frontend/src/components/ReintentoCP05.jsx` (nuevo): botón "Reenviar"
  que aparece después de iniciar una transferencia — reenvía el mismo
  payload con el mismo `X-Idempotency-Key` capturado. Es un botón, no un
  switch: `reintento_duplicado` en el contrato es informativo, el
  mecanismo real es reenviar la misma clave, y eso no tiene sentido como
  checkbox antes de que exista una primera request.
- `frontend/src/components/AuditoriaYEventos.jsx` (nuevo): muestra la
  bitácora durable (Postgres, con `motivo` del rechazo) y, en modo
  Coreografía, la trazabilidad de eventos del bus — se piden una vez que
  la Saga llega a un estado final.
- `frontend/src/components/SagaTimeline.jsx`: badge de color para los 4
  estados finales (verde CONFIRMADO, rojo los 3 RECHAZADO_*) y muestra el
  `motivo` en la línea del paso cuando existe.
- `frontend/src/components/ChaosSwitches.jsx`: nota explicando por qué CP-05
  no es un cuarto switch.
Bug de CORS encontrado y corregido en el camino: `gateway/app/main.py` no
tenía `expose_headers` en `CORSMiddleware` — sin eso, el navegador bloquea
que el JS del frontend lea `X-Idempotency-Key` de la respuesta (headers
`X-*` no están en la lista "safelisted" que el navegador expone por
default), aunque curl/servidor sí lo vieran bien. Sin este fix, CP-05
habría sido imposible de demostrar desde la UI pese a que el resto de la
lógica estuviera correcta. Agregado `expose_headers=["X-Idempotency-Key"]`.
Bug adicional encontrado al construir el panel de auditoría: cada
transferencia en Orquestación tenía una fila `PENDIENTE -> PENDIENTE`
redundante en `bitacora.transiciones` — `gateway/app/dispatch.py` ya deja
el estado en PENDIENTE antes de llamar al orquestador, y
`orchestrator/flows/transferencia_flow.py` lo volvía a setear como primera
línea del flow. Invisible antes (Redis solo guarda el valor actual, no
historial); visible recién ahora que existe el historial durable.
Corregido quitando el `set_estado(transfer_id, PENDIENTE)` redundante del
flow (y el import ahora no usado).
Cómo se probó (sin herramienta de automatización de navegador disponible
en este entorno — WebFetch no soporta localhost): `npm run build` limpio
(sin errores de sintaxis/JSX), servidor Vite real sirviendo el HTML, el
fix de CORS verificado a nivel HTTP (`Access-Control-Expose-Headers:
X-Idempotency-Key` presente en la respuesta), y el código real de
`api.js` ejecutado contra el Gateway vivo con Node (no una reimplementación
en curl) para CP-01, CP-05, auditoría y eventos de coreografía — los 3
escenarios pasaron. No se hizo verificación visual/interactiva en un
navegador real; eso queda pendiente si se necesita antes del video.
Contrato afectado: ninguno nuevo — usa los endpoints ya documentados
(`/auditoria`, `/eventos`) de la sesión anterior.
```

```
### 2026-09-18 — Rediseño visual del frontend + verificación real en navegador
Autor: IA
Qué cambió: `frontend/src/index.css` (nuevo) — sistema de diseño con
variables CSS (paleta, radios, sombras), tarjetas, badges de estado con
color, stepper vertical con iconos SVG por resultado (check verde =ok, X
roja =rechazado/fallido, flecha de vuelta ámbar =compensado) para la línea
de tiempo, y tablas para auditoría/eventos. Todos los componentes
(`TransferForm`, `ChaosSwitches`, `SagaTimeline`, `ReintentoCP05`,
`AuditoriaYEventos`) reescritos para usar className en vez de estilos
inline. `App.jsx` reorganizado en layout de dos columnas (controles a la
izquierda, resultados a la derecha, se apila en mobile).
Cómo se verificó — esta vez SÍ en un navegador real, no solo build: se
instaló Playwright + Chromium temporalmente (`npm install --no-save
playwright@1.48`, desinstalado al terminar) para manejar la UI de verdad:
CP-03 (fraude, Orquestación) y CP-04 (timeout, Coreografía) disparados
desde el formulario con switches reales, capturas de pantalla confirmando
que el stepper, los badges, la auditoría durable y la trazabilidad de
eventos se ven y renderizan correctamente; y el botón "Reenviar" (CP-05)
clickeado de verdad, confirmando que devuelve el mismo `transfer_id`. Cero
errores de JS en consola (el único mensaje —un 404 esperado de `/eventos`
en modo Orquestación, donde no se publica nada al bus— ya lo maneja
`api.js` con gracia). Capturas y dependencia de Playwright no quedaron en
el repo — solo se usaron para verificar, no son parte del proyecto.
Contrato afectado: ninguno — es solo CSS/estructura visual.
```

<!-- Nueva entrada abajo de esta línea, formato: ### AAAA-MM-DD — título corto / Autor: … / Qué cambió y qué contrato afecta -->

## 7. Estado actual

- **Fase activa:** Fase 1, Fase 3 y Fase 5 (frontend) cerradas — matriz CP-01..CP-05 validada a mano en Orquestación **y** Coreografía, doc comparativo escrito, y el frontend ya dispara los 5 casos, muestra la línea de tiempo con compensaciones, la auditoría durable y la trazabilidad de eventos, con diseño real (verificado en Chrome vía Playwright, no solo build). Falta consolidar Fase 4 (dashboard propio más allá de lo ya construido) y Fase 7 (video, checklist final).
- **Bloqueantes:**
  - Ninguno en persistencia, matriz de pruebas ni frontend — los 3 microservicios corren contra Supabase real con roles restringidos, los 5 CP están validados a mano en los dos modos, y la UI ya reenvía el `X-Idempotency-Key` (CP-05 demostrable desde el navegador, verificado con clic real).
  - `tests/test_cp_matrix.py` con los 5 casos en skip (sin reset de cuentas entre corridas) — sigue sin automatizarse, aunque ya está validado a mano (backend y frontend).
- **Próximo hito:** destrabar `tests/test_cp_matrix.py` quitando el `skip`, terminar el dashboard de Fase 4 si hace falta más allá de lo ya construido, y grabar el video demostrativo (Fase 7) — backend y frontend de los dos modos ya están completos y probados de punta a punta.
