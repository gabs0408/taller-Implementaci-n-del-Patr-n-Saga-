# Orquestación vs. Coreografía — NovaBank Saga

> Entregable pedido en el enunciado (sección 5) y evaluado en el Criterio 2
> de la rúbrica (20%). Complétenlo a medida que avanzan las Fases 2 y 3 del
> checklist — no lo dejen para el final, se nota cuando está escrito sin haber
> corrido el sistema.

## Resumen

_(2-3 párrafos: qué implementaron, con qué tecnología, y la conclusión
principal del contraste.)_

## Acoplamiento

| | Orquestación | Coreografía |
|---|---|---|
| Quién conoce a quién | El orquestador conoce a los 3 servicios | Cada servicio solo conoce los eventos a los que se suscribe |
| Punto único de fallo | El orquestador | El bus de eventos |
| Facilidad para añadir un paso nuevo | _(completar tras implementar)_ | _(completar tras implementar)_ |

## Control de flujo

_(¿Dónde vive la lógica de "qué sigue si esto falla"? ¿Es más fácil de
seguir/depurar en un modo que en el otro? Referencien capturas del Prefect UI
y de la bitácora de eventos.)_

## Cuándo usar cada uno

_(Conclusión propia del equipo — no la definición de libro, sino qué
aprendieron construyendo los dos sobre el mismo dominio.)_
