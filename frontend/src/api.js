const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL || "http://localhost:8000";

export async function crearTransferencia({ cuentaOrigen, cuentaDestino, monto, modo, simulacion }) {
  const res = await fetch(`${GATEWAY_URL}/transferencias`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cuenta_origen: cuentaOrigen,
      cuenta_destino: cuentaDestino,
      monto: Number(monto),
      modo,
      simulacion,
    }),
  });
  if (!res.ok) throw new Error(`Gateway respondió ${res.status}`);
  return res.json();
}

export async function consultarEstado(transferId) {
  const res = await fetch(`${GATEWAY_URL}/transferencias/${transferId}`);
  if (!res.ok) throw new Error(`Gateway respondió ${res.status}`);
  return res.json();
}
