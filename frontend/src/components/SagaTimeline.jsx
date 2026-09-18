// Visualización en tiempo real del avance paso a paso (Fase 5, f5-3/f5-4).
// `estado` llega por polling desde GET /transferencias/{id} (ver src/api.js),
// que a su vez lee la bitácora compartida en Redis (common/status_store.py) —
// funciona igual para orquestación y coreografía.

const ESTADO_FINAL = {
  CONFIRMADO: "badge-ok",
  RECHAZADO_FONDOS: "badge-danger",
  RECHAZADO_RIESGO: "badge-danger",
  RECHAZADO_RED: "badge-danger",
};

function EstadoBadge({ estado }) {
  const clase = ESTADO_FINAL[estado];
  if (!clase) {
    return (
      <span className="badge badge-pending">
        <span className="badge-dot" />
        {estado || "…"}
      </span>
    );
  }
  return <span className={`badge ${clase}`}>{estado}</span>;
}

const ICONOS = {
  ok: <path d="M2 6l3 3 5-6" stroke="white" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />,
  rechazado: <path d="M2 2l8 8M10 2l-8 8" stroke="white" strokeWidth="1.6" strokeLinecap="round" />,
  fallido: <path d="M2 2l8 8M10 2l-8 8" stroke="white" strokeWidth="1.6" strokeLinecap="round" />,
  error_transitorio: <path d="M2 2l8 8M10 2l-8 8" stroke="white" strokeWidth="1.6" strokeLinecap="round" />,
  compensado: <path d="M9 3H4.5A2.5 2.5 0 002 5.5v0A2.5 2.5 0 004.5 8H8M9 3L6.5 0.5M9 3L6.5 5.5" stroke="white" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />,
};

function StepIcon({ resultado }) {
  return (
    <div className={`step-icon step-icon-${resultado}`}>
      <svg viewBox="0 0 12 12">{ICONOS[resultado] || ICONOS.ok}</svg>
    </div>
  );
}

export default function SagaTimeline({ transferId, estado, pasos }) {
  if (!transferId) {
    return (
      <div className="card empty-card">
        Completá el formulario y arrancá una transferencia para ver el avance acá.
      </div>
    );
  }

  return (
    <div className="card">
      <h2>Línea de tiempo de la Saga</h2>
      <div className="transfer-meta">
        <code>{transferId}</code>
        <EstadoBadge estado={estado} />
      </div>

      {pasos.length === 0 ? (
        <p className="card-hint" style={{ margin: 0 }}>
          Esperando el primer paso… (cada uno simula 2-4s para poder verlo).
        </p>
      ) : (
        <ol className="stepper">
          {pasos.map((p, i) => (
            <li key={i} className="step">
              <div className="step-rail">
                <StepIcon resultado={p.resultado} />
                <div className="step-line" />
              </div>
              <div className="step-body">
                <div className="step-title">
                  {p.paso}
                  <span className={`step-result step-result-${p.resultado}`}>{p.resultado}</span>
                </div>
                {p.detalle?.motivo && <div className="step-motivo">Motivo: {p.detalle.motivo}</div>}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
