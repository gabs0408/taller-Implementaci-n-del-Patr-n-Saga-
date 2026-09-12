# Diagrama de la máquina de estados — Saga de Transferencia

Pedido explícitamente en la rúbrica ("diagramas de flujo completos", Criterio 6).

![Máquina de estados de la Saga](./diagrama-estados.png)

Fuente editable en `diagrama-estados.dot` (Graphviz) — para regenerar el PNG/SVG
tras cambiar un estado o una compensación:

```bash
dot -Tpng -Gdpi=200 docs/diagrama-estados.dot -o docs/diagrama-estados.png
dot -Tsvg docs/diagrama-estados.dot -o docs/diagrama-estados.svg
```

También queda la versión Mermaid abajo por si prefieren pegarla directo en el
README (GitHub la renderiza sola, sin necesitar el PNG):

```mermaid
stateDiagram-v2
    [*] --> PENDIENTE
    PENDIENTE --> DEBITADO: debitar() ok
    PENDIENTE --> RECHAZADO_FONDOS: debitar() rechaza (CP-02)
    DEBITADO --> RIESGO_OK: validar_riesgo() ok
    DEBITADO --> RECHAZADO_RIESGO: validar_riesgo() rechaza (CP-03)\n+ revertir_debito()
    RIESGO_OK --> LIQUIDADO: liquidar() ok
    RIESGO_OK --> RECHAZADO_RED: liquidar() falla (CP-04)\n+ revertir_riesgo() + revertir_debito()
    LIQUIDADO --> CONFIRMADO: acreditar()
    CONFIRMADO --> [*]
    RECHAZADO_FONDOS --> [*]
    RECHAZADO_RIESGO --> [*]
    RECHAZADO_RED --> [*]
```

Falta: diagrama de secuencia por modo (uno para Orquestación, uno para
Coreografía) mostrando quién llama a quién — o quién publica/escucha qué
evento. Fase 7, junto con el C4.
