# Bus de eventos — por qué Redis Streams

Pedido en CLAUDE.md sección 2 (stack) y en el enunciado del taller: elegir
entre Redis Streams, RabbitMQ o Kafka para la Saga Coreografiada (Fase 3),
y documentar la elección — no solo mencionarla en una tabla.

## Decisión: Redis Streams

## Qué necesitaba realmente este proyecto

No un bus de eventos genérico — específicamente lo mínimo para que 3
microservicios se coordinen sin coordinador central, con:

1. **Entrega al menos una vez, con ack explícito** — si `risk-service` se
   cae a mitad de procesar `SaldoDebitado`, ese evento no se puede perder.
2. **Un cursor de lectura por servicio** — cada uno de los 3 workers
   escucha eventos distintos (`accounts-service` escucha
   `TransferenciaSolicitada`, `RiesgoRechazado`, `TransferenciaFallida`,
   `LiquidacionConfirmada`; `risk-service` y `clearing-service` cada uno
   los suyos) y necesita avanzar su propio puntero sin pisar el de los
   otros dos.
3. **Reintento del mismo mensaje si el consumidor no lo confirmó** — la
   base de la idempotencia por `transfer_id` (Criterio 5) asume que un
   evento puede reprocesarse.
4. Nada de volumen: en la demo, unas pocas transferencias por minuto. Ni
   Kafka ni RabbitMQ están resolviendo un problema de escala acá.

Los tres candidatos ofrecen (1)-(3). La diferencia real es cuánto cuesta
levantar y operar cada uno para lo que hace falta en (4).

## Comparativa

| | **Redis Streams** | RabbitMQ | Kafka |
|---|---|---|---|
| Infraestructura nueva que sumar | Ninguna — Redis ya estaba en el stack (idempotencia, bitácora de estado) | Un broker nuevo (proceso + puerto + imagen) | Un broker nuevo + Zookeeper/KRaft — el más pesado de los tres |
| Consumer groups con ack (`XACK`) | Sí (`XREADGROUP`/`XACK`) | Sí (colas + ack manual) | Sí (offsets por grupo) |
| Reintento de mensajes no confirmados | `XPENDING`/`XCLAIM` | Redelivery automático | Reprocesar desde el offset |
| Curva de aprendizaje para el equipo | Ya sabíamos Redis (idempotencia, bitácora) | Nueva (exchanges, bindings, colas) | Nueva y más profunda (particiones, offsets, consumer rebalancing) |
| Uso de memoria/operación en una demo de escritorio | Mínimo, ya corriendo | Extra ~150-200MB de proceso | Extra varios cientos de MB (broker + Zookeeper) |
| Encaja con "un único stream, varios consumer groups" (nuestro diseño) | Natural | Requiere exchange + 3 colas con bindings | Requiere un topic con particiones + 3 consumer groups |
| Para volumen alto / múltiples data centers | No es su punto fuerte | Bueno | Ahí es donde gana de verdad |

**Ganó Redis Streams por costo de infraestructura, no por ser "mejor" en
abstracto.** RabbitMQ y Kafka resuelven problemas (routing complejo,
throughput masivo, retención larga con replay) que esta Saga no tiene. Ya
había un Redis corriendo en el stack para dos cosas distintas —
idempotencia (`common/idempotency.py`) y la bitácora de estado
(`common/status_store.py`) — así que sumarlo como bus de eventos también
significó **cero infraestructura nueva**, en vez de meter un tercer sistema
externo a coordinar solo para la Fase 3.

## Trade-offs que aceptamos a cambio

- **Un único nodo, sin particionamiento horizontal.** Si el volumen
  creciera en serio, Redis Streams no reparte carga entre particiones como
  Kafka. No es un problema para este taller.
- **Sin schema registry.** Los eventos son JSON libre — `contracts/events.asyncapi.yaml`
  es la única fuente de verdad del contrato, no algo que el bus imponga.
- **Sin retención configurable por política de negocio.** El stream crece
  indefinidamente salvo que alguien lo recorte a mano (`XTRIM`) — no hace
  falta para la demo, pero en un sistema real habría que decidir una
  política de retención.
- **Persistencia no viene gratis.** Por defecto, un contenedor de Redis sin
  volumen pierde el stream completo (y los offsets de los 3 consumer
  groups) si se reinicia — lo encontramos así el 2026-09-18 al recrear
  `event-bus` para otra cosa: los 3 workers crashearon con
  `ConnectionError` en vez de reconectar solos. Corregido:
  `docker-compose.yml` ahora levanta `event-bus` con `--appendonly yes` +
  volumen (`event-bus-data`), y `common/events.py` atrapa el
  `ConnectionError` en el loop de consumo, espera 2s, reconecta y
  vuelve a asegurar el consumer group en vez de morir. Verificado: reiniciar
  `event-bus` con `docker compose restart` ya no tumba a ningún worker.

## Cómo levantarlo

Ya está arriba con el resto del stack — no hace falta ningún paso aparte:

```bash
docker compose up -d event-bus
```

Verificar que está vivo y ver el estado real de los 3 consumer groups:

```bash
docker exec novabank-saga-event-bus-1 redis-cli PING
docker exec novabank-saga-event-bus-1 redis-cli XINFO STREAM novabank:transferencias
docker exec novabank-saga-event-bus-1 redis-cli XINFO GROUPS novabank:transferencias
```

`lag: 0` y `pending: 0` en los tres grupos (`accounts-service`,
`risk-service`, `clearing-service`) significa que los tres workers están
al día — ni atrasados ni con mensajes entregados y nunca confirmados.

## Si el equipo quisiera migrar a RabbitMQ o Kafka más adelante

El contrato de eventos (`contracts/events.asyncapi.yaml`) ya está escrito
para que esto sea un cambio de transporte, no de diseño — lo dice
explícitamente esa sección del archivo: "si el equipo prefiere un
exchange/tema por evento (RabbitMQ/Kafka), este archivo sigue siendo
válido — cambia el transporte, no el contrato de payloads." Lo único que
habría que reescribir es `common/events.py` (las funciones `publicar()` y
`consumir()`); ningún microservicio conoce los detalles de Redis
directamente — todos pasan por ese único módulo.
