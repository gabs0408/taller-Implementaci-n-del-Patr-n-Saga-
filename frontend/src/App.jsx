import { useEffect, useRef, useState } from "react";
import TransferForm from "./components/TransferForm.jsx";
import ChaosSwitches from "./components/ChaosSwitches.jsx";
import SagaTimeline from "./components/SagaTimeline.jsx";
import AuditoriaYEventos from "./components/AuditoriaYEventos.jsx";
import ReintentoCP05 from "./components/ReintentoCP05.jsx";
import { crearTransferencia, consultarEstado, consultarAuditoria, consultarEventos } from "./api.js";

const ESTADOS_FINALES = ["CONFIRMADO", "RECHAZADO_FONDOS", "RECHAZADO_RIESGO", "RECHAZADO_RED"];

export default function App() {
  const [values, setValues] = useState({
    cuentaOrigen: "ACC-001",
    cuentaDestino: "ACC-002",
    monto: "10000",
    modo: "orquestacion",
  });
  const [switches, setSwitches] = useState({
    fondosInsuficientes: false,
    fraude: false,
    timeoutPasarela: false,
  });
  const [transferId, setTransferId] = useState(null);
  const [estado, setEstado] = useState(null);
  const [pasos, setPasos] = useState([]);
  const [modoUsado, setModoUsado] = useState("orquestacion");
  const [idempotencyKey, setIdempotencyKey] = useState(null);
  const [auditoria, setAuditoria] = useState(null);
  const [eventos, setEventos] = useState(null);
  const pollRef = useRef(null);

  async function despachar({ idemKey } = {}) {
    setPasos([]);
    setAuditoria(null);
    setEventos(null);
    setEstado("PENDIENTE");
    setModoUsado(values.modo);
    const resp = await crearTransferencia({ ...values, simulacion: switches, idempotencyKey: idemKey });
    setIdempotencyKey(resp.idempotencyKey);
    setTransferId(resp.transfer_id);
  }

  function iniciar() {
    despachar();
  }

  function reenviar() {
    // CP-05: mismo idempotencyKey capturado de la respuesta anterior — el
    // Gateway debe devolver el mismo transfer_id sin volver a despachar.
    despachar({ idemKey: idempotencyKey });
  }

  useEffect(() => {
    if (!transferId) return;
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const data = await consultarEstado(transferId);
        setEstado(data.estado);
        setPasos(data.pasos);
        if (ESTADOS_FINALES.includes(data.estado)) {
          clearInterval(pollRef.current);
          const [aud, ev] = await Promise.all([
            consultarAuditoria(transferId).catch(() => null),
            consultarEventos(transferId).catch(() => null),
          ]);
          setAuditoria(aud);
          setEventos(ev);
        }
      } catch {
        // TODO (Fase 5): manejar el caso en que el gateway todavía no
        // tiene registro (carrera con el primer paso) sin ensuciar la consola.
      }
    }, 1000);
    return () => clearInterval(pollRef.current);
  }, [transferId]);

  const enProceso = transferId && !ESTADOS_FINALES.includes(estado);

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>NovaBank Saga — Simulador</h1>
        <p>
          Taller de Arquitectura de Software Distribuida: patrón Saga bancario, contrastando
          Orquestación (Prefect) y Coreografía (eventos) con compensaciones estrictas en reversa.
        </p>
      </header>

      <div className="app-layout">
        <div className="control-column">
          <TransferForm values={values} onChange={setValues} onSubmit={iniciar} disabled={enProceso} />
          <ChaosSwitches values={switches} onChange={setSwitches} />
          <ReintentoCP05 idempotencyKey={idempotencyKey} disabled={enProceso} onReenviar={reenviar} />
        </div>

        <div className="results-column">
          <SagaTimeline transferId={transferId} estado={estado} pasos={pasos} />
          <AuditoriaYEventos modo={modoUsado} auditoria={auditoria} eventos={eventos} />
        </div>
      </div>
    </div>
  );
}
