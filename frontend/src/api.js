const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL || "http://localhost:8000";

// El backend (common/models.py y contracts/*.yaml) espera `Simulacion` en
// snake_case. Los switches del frontend viven en camelCase (ChaosSwitches.jsx)
// así que hay que traducir las claves aquí, en el borde de la API — si no,
// Pydantic ignora en silencio las claves que no reconoce y los switches de
// CP-02/CP-04 nunca llegan a activarse en el backend.
function simulacionASnakeCase(simulacion = {}) {
  return {
    fondos_insuficientes: !!simulacion.fondosInsuficientes,
    fraude: !!simulacion.fraude,
    timeout_pasarela: !!simulacion.timeoutPasarela,
    reintento_duplicado: !!simulacion.reintentoDuplicado,
  };
}

// CP-05 (idempotencia): el Gateway siempre devuelve el X-Idempotency-Key que
// usó (el que mandamos, o uno generado si no mandamos ninguno) en el header
// de respuesta. Si lo capturamos y lo reenviamos tal cual en un segundo
// POST con el mismo body, el Gateway reconoce el duplicado y devuelve el
// mismo transfer_id sin volver a despachar — eso es lo que "Reenviar" hace
// más abajo en App.jsx. Sin capturar este header, cada request generaría
// una clave nueva y CP-05 sería imposible de demostrar desde la UI.
export async function crearTransferencia({ cuentaOrigen, cuentaDestino, monto, modo, simulacion, idempotencyKey }) {
  const headers = { "Content-Type": "application/json" };
  if (idempotencyKey) headers["X-Idempotency-Key"] = idempotencyKey;

  const res = await fetch(`${GATEWAY_URL}/transferencias`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      cuenta_origen: cuentaOrigen,
      cuenta_destino: cuentaDestino,
      monto: Number(monto),
      modo,
      simulacion: simulacionASnakeCase(simulacion),
    }),
  });
  if (!res.ok) throw new Error(`Gateway respondió ${res.status}`);
  const data = await res.json();
  return { ...data, idempotencyKey: res.headers.get("X-Idempotency-Key") };
}

export async function consultarEstado(transferId) {
  const res = await fetch(`${GATEWAY_URL}/transferencias/${transferId}`);
  if (!res.ok) throw new Error(`Gateway respondió ${res.status}`);
  return res.json();
}

// Bitácora DURABLE (Postgres, bitacora.transiciones) — estado_anterior,
// estado_nuevo, motivo del rechazo y timestamp. Distinta de consultarEstado
// (Redis, rápida, para el polling) — esta es la que sobrevive un reinicio
// de Redis y la que trae la causa del fallo.
export async function consultarAuditoria(transferId) {
  const res = await fetch(`${GATEWAY_URL}/transferencias/${transferId}/auditoria`);
  if (res.status === 404) return null; // AUDIT_DATABASE_URL sin configurar, o aún sin transiciones
  if (!res.ok) throw new Error(`Gateway respondió ${res.status}`);
  return res.json();
}

// Trazabilidad de Coreografía: lee el bus de eventos directo. En
// Orquestación normalmente solo va a traer `TransferenciaSolicitada`,
// porque el resto de los pasos no pasa por el bus en ese modo.
export async function consultarEventos(transferId) {
  const res = await fetch(`${GATEWAY_URL}/transferencias/${transferId}/eventos`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Gateway respondió ${res.status}`);
  return res.json();
}
