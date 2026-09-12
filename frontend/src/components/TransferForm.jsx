export default function TransferForm({ values, onChange, onSubmit, disabled }) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 360 }}
    >
      <label>
        Cuenta origen
        <input
          value={values.cuentaOrigen}
          onChange={(e) => onChange({ ...values, cuentaOrigen: e.target.value })}
          placeholder="ACC-001"
          required
        />
      </label>
      <label>
        Cuenta destino
        <input
          value={values.cuentaDestino}
          onChange={(e) => onChange({ ...values, cuentaDestino: e.target.value })}
          placeholder="ACC-002"
          required
        />
      </label>
      <label>
        Importe
        <input
          type="number"
          min="0"
          step="0.01"
          value={values.monto}
          onChange={(e) => onChange({ ...values, monto: e.target.value })}
          required
        />
      </label>
      <label>
        Modo
        <select value={values.modo} onChange={(e) => onChange({ ...values, modo: e.target.value })}>
          <option value="orquestacion">Orquestación (Prefect)</option>
          <option value="coreografia">Coreografía (eventos)</option>
        </select>
      </label>
      <button type="submit" disabled={disabled}>
        {disabled ? "Procesando…" : "Iniciar transferencia"}
      </button>
    </form>
  );
}
