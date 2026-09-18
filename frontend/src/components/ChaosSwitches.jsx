// Simulador de caos (Fase 5). Cada switch corresponde a un caso de
// prueba de la matriz CP-01..CP-05 — ver CLAUDE.md sección 5.
const SWITCHES = [
  { key: "fondosInsuficientes", label: "CP-02 · Fondos insuficientes" },
  { key: "fraude", label: "CP-03 · Forzar fraude / riesgo" },
  { key: "timeoutPasarela", label: "CP-04 · Caída de la pasarela" },
];

export default function ChaosSwitches({ values, onChange }) {
  return (
    <div className="card">
      <h2>Simulador de caos</h2>
      <div className="switch-list">
        {SWITCHES.map((s) => (
          <label key={s.key} className="switch-row">
            <input
              type="checkbox"
              checked={values[s.key]}
              onChange={(e) => onChange({ ...values, [s.key]: e.target.checked })}
            />
            {s.label}
          </label>
        ))}
      </div>
      <p className="card-hint">
        CP-01 = ningún switch activado. CP-05 (reintento duplicado) no es un
        switch — es el botón "Reenviar" que aparece debajo de la línea de
        tiempo una vez que iniciás una transferencia.
      </p>
    </div>
  );
}
