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

### Máquina de estados de la transferencia
```
PENDIENTE → DEBITADO → RIESGO_OK → LIQUIDADO → CONFIRMADO
                 ↘ RECHAZADO_FONDOS (falla antes de debitar)
                 ↘ RECHAZADO_RIESGO (se revierte el débito)
                 ↘ RECHAZADO_RED    (se revierte riesgo + débito, en ese orden)
```

### Endpoints REST (modo orquestado — los llama el flow de Prefect)
- `POST /cuentas/{cuentaId}/debitar` `{transferId, monto}`
- `POST /cuentas/{cuentaId}/acreditar` `{transferId, monto}`
- `POST /cuentas/{cuentaId}/revertir-debito` `{transferId}`
- `POST /riesgo/validar` `{transferId, cuentaOrigen, monto}`
- `POST /riesgo/revertir` `{transferId}`
- `POST /pasarela/liquidar` `{transferId, cuentaDestino, monto}`
- `POST /transferencias` (Gateway) `{cuentaOrigen, cuentaDestino, monto, modo: "orquestacion"|"coreografia", simulacion?: {fondosInsuficientes, fraude, timeoutPasarela, reintentoDuplicado}}` → asigna `transferId`, header `X-Idempotency-Key`. Según `modo`, el Gateway **llama al orquestador** (Prefect) o **publica `TransferenciaSolicitada`** en el bus — nunca ambos.
- Idempotencia a nivel de cada microservicio: los endpoints de escritura (`debitar`, `acreditar`, `liquidar`, …) deben usar `transferId` como clave para no aplicar dos veces la misma operación si llega repetida — el Criterio 5 de la rúbrica la evalúa aparte de la idempotencia del Gateway.

### Eventos de dominio (modo coreografía — mismo payload base: `transferId`, `timestamp`)
- `TransferenciaSolicitada` `{cuentaOrigen, cuentaDestino, monto, simulacion?}` — el campo `simulacion` viaja igual que en el Gateway, para que cada servicio sepa si debe forzar su propio fallo
- `SaldoDebitado` `{cuentaOrigen, monto}`
- `RiesgoAprobado` `{}`
- `RiesgoRechazado` `{motivo}`
- `LiquidacionConfirmada` `{}`
- `TransferenciaFallida` `{fase, motivo}`
- `CompensacionEjecutada` `{servicio, accion}`

> Estos nombres y payloads son la propuesta inicial (sesión de kickoff). En cuanto el equipo los implemente y ajuste, actualicen esta sección en el mismo commit — es lo que evita que Persona A y Persona B (o dos sesiones de IA) asuman contratos distintos.

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
- [ ] CP-01  - [ ] CP-02  - [ ] CP-03  - [ ] CP-04  - [ ] CP-05

**Coreografía:**
- [ ] CP-01  - [ ] CP-02  - [ ] CP-03  - [ ] CP-04  - [ ] CP-05

## 6. Bitácora de cambios (agregar una entrada por sesión de trabajo)

```
### 2026-09-12 — Kickoff
Autor: equipo
Definidos: reparto de trabajo (A: orquestación, B: coreografía + UI), stack sugerido,
máquina de estados, contratos iniciales de endpoints y eventos (sección 3, aún sin
implementar). Checklist interactivo de fases publicado. Sin código todavía.
```

<!-- Nueva entrada abajo de esta línea, formato: ### AAAA-MM-DD — título corto / Autor: … / Qué cambió y qué contrato afecta -->

## 7. Estado actual

- **Fase activa:** Fase 0 — Fundamentos y arranque.
- **Bloqueantes:** ninguno.
- **Próximo hito:** Persona A entrega los 3 microservicios con lógica interna lista (fin Fase 1) para que Persona B empiece a envolverlos con eventos en Fase 3.
