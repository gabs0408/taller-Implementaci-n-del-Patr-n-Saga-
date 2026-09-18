# Contratos entre servicios — Fase 0, tarea f0-5

Dos archivos, uno por modo:

- **`openapi.yaml`** — las llamadas HTTP síncronas que hace el Orchestrator
  en modo Orquestación (y el único endpoint que el frontend conoce, en el
  Gateway).
- **`events.asyncapi.yaml`** — los eventos del bus de Redis en modo
  Coreografía.

Los dos describen **el mismo negocio** (mismos campos: `transfer_id`,
`cuenta_origen`, `cuenta_destino`, `monto`, `simulacion`) porque la lógica de
cada microservicio es una sola — solo cambia si la dispara una llamada REST o
un evento (regla 3 de `/CONTEXT.md`). Si agregan un campo, agréguenlo en los
dos archivos y en `common/models.py`, en el mismo commit.

## Cómo viajan `modo` y `simulacion` desde el frontend

```
Frontend                Gateway                  Orchestrator / Bus            Microservicio
--------                -------                  -------------------            -------------
{modo, simulacion} ---> POST /transferencias
                         (openapi.yaml)
                              |
                    lee `modo` UNA sola vez:
                              |
                    modo=orquestacion ------------> POST /run-transferencia --> POST /cuentas/.../debitar
                    (ya no se vuelve a mirar)        (bridge propio :8010)       { transfer_id, monto,
                                                      El Orchestrator arma        simulacion }  <- viaja
                                                      el body de cada REST        en el body de
                                                      call con `simulacion`       CADA llamada REST
                                                      adentro (openapi.yaml)      (openapi.yaml)
                              |
                    modo=coreografia --------------> publica TransferenciaSolicitada
                                                      { ..., simulacion }         --> cada worker la
                                                      (events.asyncapi.yaml)          lee del evento
                                                                                       que consume
```

Puntos concretos:

1. **`modo` se lee una sola vez**, en `gateway/app/dispatch.py`. De ahí en
   adelante el sistema entero ya "está" en un modo u otro para esa
   transferencia — ningún microservicio vuelve a preguntar por `modo`.
2. **`simulacion` viaja completo, sin filtrar, en cada paso** — no es que el
   Gateway decida a quién le manda cada flag. `{fondos_insuficientes, fraude,
   timeout_pasarela, reintento_duplicado}` llega entero a los tres servicios
   (o los tres workers), y cada uno solo lee el campo que le importa (p.ej.
   `risk-service` solo mira `fraude`). Así, si más adelante agregan un cuarto
   servicio que necesite un switch nuevo, no hay que tocar el Gateway — solo
   agregar el campo a `Simulacion` en los dos contratos y leerlo donde
   corresponda.
3. **En Orquestación**, `simulacion` va dentro del *body* de cada POST REST
   (ver `DebitarBody`, `ValidarRiesgoBody`, `LiquidarBody` en `openapi.yaml`).
   **En Coreografía**, va dentro del *payload* de `TransferenciaSolicitada`
   (ver `EventoBase` en `events.asyncapi.yaml`) y de ahí cada evento
   siguiente lo re-publica sin tocarlo (`{**payload}` en el código).

## Cómo abrirlos

Sin instalar nada, en <https://editor.swagger.io> (pegan `openapi.yaml`) y
<https://studio.asyncapi.com> (pegan `events.asyncapi.yaml`) — ambos
renderizan documentación navegable y validan el archivo al vuelo.

Localmente:

```bash
pip install openapi-spec-validator
python -c "from openapi_spec_validator import validate; import yaml; validate(yaml.safe_load(open('contracts/openapi.yaml')))"
```
