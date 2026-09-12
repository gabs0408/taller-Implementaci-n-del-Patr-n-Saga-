// Visualización en tiempo real del avance paso a paso (Fase 5, f5-3/f5-4).
// `estado` llega por polling desde GET /transferencias/{id} (ver src/api.js),
// que a su vez lee la bitácora compartida en Redis (common/status_store.py) —
// funciona igual para orquestación y coreografía.

const RESULTADO_COLOR = {
  ok: "#2f6f5c",
  rechazado: "#9c4530",
  fallido: "#9c4530",
  compensado: "#a8792c",
};

export default function SagaTimeline({ transferId, estado, pasos }) {
  if (!transferId) return null;

  return (
    <div style={{ maxWidth: 480 }}>
      <p>
        <strong>Transferencia:</strong> <code>{transferId}</code>
        <br />
        <strong>Estado actual:</strong> {estado || "…"}
      </p>
      <ol style={{ paddingLeft: 20 }}>
        {pasos.map((p, i) => (
          <li key={i} style={{ color: RESULTADO_COLOR[p.resultado] || "inherit" }}>
            <strong>{p.paso}</strong> — {p.resultado}
          </li>
        ))}
      </ol>
    </div>
  );
}
