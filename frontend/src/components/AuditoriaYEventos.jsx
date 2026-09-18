// Dos vistas que complementan el timeline rápido (SagaTimeline, Redis):
//
// - Auditoría durable: bitacora.transiciones en Postgres — sobrevive un
//   reinicio de Redis y trae el `motivo` del rechazo, que el timeline
//   rápido no siempre expone tan claro.
// - Trazabilidad de eventos: solo tiene contenido real en modo Coreografía
//   (lee el stream de Redis) — es el equivalente al Prefect UI para el modo
//   sin coordinador. En Orquestación normalmente solo va a aparecer
//   TransferenciaSolicitada, porque el resto no pasa por el bus.

function Reloj({ iso }) {
  try {
    return <span className="audit-time">{new Date(iso).toLocaleTimeString()}</span>;
  } catch {
    return <span className="audit-time">{iso}</span>;
  }
}

export default function AuditoriaYEventos({ modo, auditoria, eventos }) {
  const tieneAuditoria = auditoria?.transiciones?.length > 0;
  const tieneEventos = modo === "coreografia" && eventos?.eventos?.length > 0;

  if (!tieneAuditoria && !tieneEventos) return null;

  return (
    <div className={`audit-grid ${tieneAuditoria && tieneEventos ? "two-col" : ""}`}>
      {tieneAuditoria && (
        <div className="card">
          <h3>Auditoría durable (Postgres)</h3>
          <table className="audit-table">
            <tbody>
              {auditoria.transiciones.map((t, i) => (
                <tr key={i}>
                  <td>
                    <Reloj iso={t.ts} />
                  </td>
                  <td>
                    {t.estado_anterior || "—"} → <strong>{t.estado_nuevo}</strong>
                  </td>
                  <td className="audit-motivo">{t.motivo || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tieneEventos && (
        <div className="card">
          <h3>Trazabilidad de eventos (bus)</h3>
          <table className="audit-table">
            <tbody>
              {eventos.eventos.map((e, i) => (
                <tr key={e.id || i}>
                  <td className="audit-time">{new Date(e.ts * 1000).toLocaleTimeString()}</td>
                  <td>
                    <code>{e.tipo}</code>
                    {e.payload?.motivo && <span className="audit-motivo"> — {e.payload.motivo}</span>}
                    {e.payload?.servicio && <span className="audit-service"> ({e.payload.servicio})</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
