// CP-05 (idempotencia): el switch "reintento_duplicado" del contrato es
// informativo — el mecanismo real es reenviar el MISMO X-Idempotency-Key
// (ver contracts/openapi.yaml). Por eso esto es un botón que reenvía la
// última transferencia tal cual, no un checkbox — un checkbox no tendría
// nada que "reintentar" antes de que exista una primera request.
export default function ReintentoCP05({ idempotencyKey, disabled, onReenviar }) {
  if (!idempotencyKey) return null;

  return (
    <div className="card">
      <h2>CP-05 · Idempotencia</h2>
      <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-muted)", lineHeight: 1.5 }}>
        Reenvía la misma transferencia con el mismo <code>X-Idempotency-Key</code>{" "}
        (<code>{idempotencyKey.slice(0, 8)}…</code>). El Gateway debe reconocer el
        duplicado y devolver el mismo <code>transfer_id</code> sin cobrar dos veces.
      </p>
      <button type="button" className="btn btn-secondary" onClick={onReenviar} disabled={disabled}>
        Reenviar (mismo idempotency-key)
      </button>
    </div>
  );
}
