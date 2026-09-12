// Simulador de caos (Fase 5). Cada switch corresponde a un caso de
// prueba de la matriz CP-01..CP-05 — ver CONTEXT.md sección 5.
const SWITCHES = [
  { key: "fondosInsuficientes", label: "CP-02 · Fondos insuficientes" },
  { key: "fraude", label: "CP-03 · Forzar fraude / riesgo" },
  { key: "timeoutPasarela", label: "CP-04 · Caída de la pasarela" },
];

export default function ChaosSwitches({ values, onChange }) {
  return (
    <fieldset style={{ display: "flex", flexDirection: "column", gap: 6, maxWidth: 360 }}>
      <legend>Simular fallo (CP-01 = ninguno activado)</legend>
      {SWITCHES.map((s) => (
        <label key={s.key} style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="checkbox"
            checked={values[s.key]}
            onChange={(e) => onChange({ ...values, [s.key]: e.target.checked })}
          />
          {s.label}
        </label>
      ))}
    </fieldset>
  );
}
