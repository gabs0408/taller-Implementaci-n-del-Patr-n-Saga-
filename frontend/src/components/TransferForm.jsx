export default function TransferForm({ values, onChange, onSubmit, disabled }) {
  return (
    <form
      className="card"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <h2>Transferencia</h2>

      <div className="field">
        <label>Cuenta origen</label>
        <input
          value={values.cuentaOrigen}
          onChange={(e) => onChange({ ...values, cuentaOrigen: e.target.value })}
          placeholder="ACC-001"
          required
        />
      </div>

      <div className="field">
        <label>Cuenta destino</label>
        <input
          value={values.cuentaDestino}
          onChange={(e) => onChange({ ...values, cuentaDestino: e.target.value })}
          placeholder="ACC-002"
          required
        />
      </div>

      <div className="field">
        <label>Importe</label>
        <input
          type="number"
          min="0"
          step="0.01"
          value={values.monto}
          onChange={(e) => onChange({ ...values, monto: e.target.value })}
          required
        />
      </div>

      <div className="field">
        <label>Modo de la Saga</label>
        <select value={values.modo} onChange={(e) => onChange({ ...values, modo: e.target.value })}>
          <option value="orquestacion">Orquestación (Prefect)</option>
          <option value="coreografia">Coreografía (eventos)</option>
        </select>
      </div>

      <button type="submit" className="btn btn-primary" disabled={disabled}>
        {disabled ? "Procesando…" : "Iniciar transferencia"}
      </button>
    </form>
  );
}
