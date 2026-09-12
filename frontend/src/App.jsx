import { useEffect, useRef, useState } from "react";
import TransferForm from "./components/TransferForm.jsx";
import ChaosSwitches from "./components/ChaosSwitches.jsx";
import SagaTimeline from "./components/SagaTimeline.jsx";
import { crearTransferencia, consultarEstado } from "./api.js";

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
  const pollRef = useRef(null);

  async function iniciar() {
    setPasos([]);
    setEstado("PENDIENTE");
    const resp = await crearTransferencia({ ...values, simulacion: switches });
    setTransferId(resp.transfer_id);
  }

  useEffect(() => {
    if (!transferId) return;
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const data = await consultarEstado(transferId);
        setEstado(data.estado);
        setPasos(data.pasos);
        if (ESTADOS_FINALES.includes(data.estado)) clearInterval(pollRef.current);
      } catch {
        // TODO (Fase 5): manejar el caso en que el gateway todavía no
        // tiene registro (carrera con el primer paso) sin ensuciar la consola.
      }
    }, 1000);
    return () => clearInterval(pollRef.current);
  }, [transferId]);

  const enProceso = transferId && !ESTADOS_FINALES.includes(estado);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: 24, display: "grid", gap: 24, maxWidth: 960 }}>
      <h1>NovaBank Saga — Simulador</h1>

      <section style={{ display: "flex", gap: 40, flexWrap: "wrap" }}>
        <TransferForm values={values} onChange={setValues} onSubmit={iniciar} disabled={enProceso} />
        <ChaosSwitches values={switches} onChange={setSwitches} />
      </section>

      <SagaTimeline transferId={transferId} estado={estado} pasos={pasos} />

      <p style={{ fontSize: 13, color: "#5c6b6a" }}>
        CP-05 (idempotencia): vuelve a enviar el mismo formulario sin cambiar nada —
        el Gateway debe reconocer el reintento por el header X-Idempotency-Key.
        {/* TODO (Fase 5): exponer un botón "reenviar" que reuse el mismo
            idempotency-key en vez de generar uno nuevo por request. */}
      </p>
    </main>
  );
}
