# Orquestación vs. Coreografía — NovaBank Saga

> Entregable pedido en el enunciado (sección 5) y evaluado en el Criterio 2
> de la rúbrica (20%). Escrito después de correr la matriz completa
> (CP-01..CP-05) en los dos modos contra el stack real — no es una
> comparación de libro, son hallazgos concretos de este proyecto.

## Resumen

Implementamos la misma lógica de negocio (débito, validación de riesgo,
liquidación, reversas) de dos formas: un flow de Prefect que llama a los 3
microservicios uno por uno (`orchestrator/flows/transferencia_flow.py`), y
3 workers de eventos que reaccionan de forma autónoma a lo que pasa en un
stream de Redis (`services/*/app/events_worker.py`). Los dos modos
comparten exactamente el mismo código de negocio — `app/core.py` en cada
microservicio — así que la comparación de abajo es sobre **coordinación**,
no sobre lógica duplicada (regla 3 de CLAUDE.md).

Conclusión corta: Orquestación fue más fácil de razonar, depurar y
extender; Coreografía tiene menos acoplamiento de verdad, pero ese
desacoplamiento tiene un costo concreto que solo se ve al implementar la
compensación de un fallo tardío (CP-04) — no es gratis.

## Acoplamiento

| | Orquestación | Coreografía |
|---|---|---|
| Quién conoce a quién | El orquestador conoce los 3 servicios (`orchestrator/flows/clients.py` llama por HTTP a cada uno) | Cada worker solo conoce los eventos a los que se suscribe — confirmado por código: `accounts-service` escucha 4 eventos, `risk-service` 2, `clearing-service` 1, y no hay ninguna llamada HTTP directa entre servicios de dominio (`grep httpx` en los 3 `events_worker.py` no encuentra nada) |
| Punto único de fallo | El orquestador — si el contenedor `orchestrator` se cae a mitad de un flow, esa Saga queda colgada | El bus de eventos (Redis) — lo confirmamos apagándolo a mitad de una Saga en Coreografía: mientras estuvo caído, nada avanzaba en ningún servicio; al volver, los 3 workers reconectaron solos y la Saga terminó bien (ver bitácora 2026-09-18, "Bus de eventos") |
| Dependencias circulares | N/A (no aplica, hay un coordinador) | Revisado: ningún worker escucha un evento que él mismo publica. `accounts-service` publica `SaldoDebitado` y `CompensacionEjecutada` pero no los escucha; `risk-service` publica `RiesgoAprobado`/`RiesgoRechazado` pero no los escucha; `clearing-service` publica `LiquidacionConfirmada`/`TransferenciaFallida` pero no los escucha. Sin ciclos. |
| Facilidad para añadir un paso nuevo | Un archivo: agregar un `@task` + una llamada en `transferencia_saga()` | Varios archivos: agregar el evento al contrato (`events.asyncapi.yaml`), un handler nuevo, registrarlo en el `handlers` dict del worker que corresponda, y actualizar el paso anterior de la cadena para que publique el evento nuevo — el grafo de "quién dispara a quién" queda implícito en el código de 3 archivos distintos, no en un solo lugar |

## Control de flujo

**Dónde vive la lógica de "qué sigue si esto falla":** en Orquestación,
adentro de una sola función (`transferencia_saga`) que se lee de arriba
hacia abajo — el orden de las compensaciones en CP-04 (revertir riesgo,
*después* revertir débito) es una secuencia explícita de dos líneas de
código, una atrás de la otra. En Coreografía esa misma garantía **no
existe**: `TransferenciaFallida` la escuchan `risk-service` y
`accounts-service` de forma independiente, cada uno reacciona por su
cuenta, y no hay nada que le diga a uno que espere al otro. El propio
contrato ya lo advierte (`contracts/events.asyncapi.yaml`, mensaje
`TransferenciaFallida`): *"los dos reaccionan al mismo evento, en cualquier
orden"*.

Esto no es teórico — lo medimos. En la corrida de CP-04 en Coreografía del
2026-09-18, el stream de eventos quedó así (timestamps reales):

```
TransferenciaFallida            → 1789721611.59
CompensacionEjecutada(riesgo)   → 1789721616.06   (+4.47s)
CompensacionEjecutada(cuentas)  → 1789721618.30   (+2.24s)
```

Salió en el orden "correcto" (riesgo antes que cuentas, igual que en
Orquestación) — pero **por casualidad**, no por diseño: nada en el código
fuerza ese orden entre los dos workers. Si `risk-service` estuviera más
lento que `accounts-service` en una corrida distinta, `CompensacionEjecutada(cuentas)`
podría salir primero. Para esta Saga en particular no importa (las dos
reversas son independientes entre sí — revertir el débito no depende de
que ya se haya revertido el riesgo), pero es la diferencia real de fondo
entre los dos modos: Orquestación puede **garantizar** un orden;
Coreografía, tal como está construida, solo puede **tender a** un orden.

**Depurar y observar:** Orquestación tiene el Prefect UI (`:4200`) con el
grafo de tasks, duración de cada una, y estado final del flow run
(`Completed` vs. `Failed` — usamos esa distinción explícitamente para
diferenciar un rechazo de negocio de un fallo transitorio de infraestructura,
ver bitácora 2026-09-18 "Retries + on_failure hooks"). Coreografía no tiene
nada parecido de fábrica — hubo que construirlo a mano:
`GET /transferencias/{id}/eventos` (lee el stream de Redis y arma la traza
de una transferencia) es el equivalente que hicimos para no depender solo
del Prefect UI, que en Coreografía nunca se entera de nada.

**Resiliencia:** en Orquestación, los reintentos ante un fallo transitorio
(red caída, timeout) los da Prefect gratis (`retries`, `retry_delay_seconds`,
`on_failure`). En Coreografía hubo que escribirlos a mano en
`common/events.py` — reconexión al perder Redis, reintento de mensajes no
confirmados vía `XREADGROUP` con id `"0"` — y nos costó un bug real en el
camino (un mensaje se confirmaba aunque el handler fallara, perdiendo el
evento en silencio; corregido, ver bitácora 2026-09-18).

## Lo que NO cambia entre los dos modos

Vale la pena decirlo porque es fácil asumir lo contrario: la **idempotencia**
por `transfer_id` (Criterio 5) es idéntica en ambos modos, porque vive en
`app/core.py`/`app/store.py` de cada microservicio — la misma función que
llama `routes.py` (Orquestación) también la llama `events_worker.py`
(Coreografía). Tampoco cambia el aislamiento de datos (cada servicio con su
propio esquema y rol de Postgres) ni los delays configurables
(`STEP_DELAY_MS`, aplicado igual en los dos modos — confirmado: los gaps
entre pasos en la corrida de CP-04 en Coreografía fueron de 2.2 a 6.1
segundos, todos perceptibles).

## Cuándo usar cada uno

Para NovaBank, con solo 3 servicios y una secuencia lineal fija (débito →
riesgo → liquidación → crédito), **Orquestación fue más fácil de construir
bien a la primera** — la lógica de compensación en un solo lugar es más
fácil de auditar que confiar en que 3 equipos distintos implementen
correctamente su reacción a cada evento. Coreografía empieza a pagarse sola
cuando el número de servicios crece y agregar un participante nuevo (por
ejemplo, un servicio de notificaciones que solo necesita *enterarse* de que
la transferencia se confirmó, sin bloquear nada) no debería requerir tocar
un coordinador central — ahí el desacoplamiento es una ventaja real, no
solo una promesa de arquitectura.
