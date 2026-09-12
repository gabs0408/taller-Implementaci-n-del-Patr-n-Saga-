"""Corre una transferencia directo contra el flow, sin pasar por el
Gateway ni el frontend — para la sesión presencial (Fase 0, f0-7):
"puesta en marcha del orquestador inicial con el primer caso exitoso
(CP-01)".

Uso, con el stack ya levantado (docker-compose up):

    docker compose exec orchestrator python run_demo.py               # CP-01, camino feliz
    docker compose exec orchestrator python run_demo.py --fraude      # CP-03
    docker compose exec orchestrator python run_demo.py --sin-fondos  # CP-02
    docker compose exec orchestrator python run_demo.py --timeout     # CP-04
"""
import argparse
import uuid

from flows.transferencia_flow import transferencia_saga

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sin-fondos", action="store_true")
    parser.add_argument("--fraude", action="store_true")
    parser.add_argument("--timeout", action="store_true")
    args = parser.parse_args()

    transfer_id = str(uuid.uuid4())
    simulacion = {
        "fondos_insuficientes": args.sin_fondos,
        "fraude": args.fraude,
        "timeout_pasarela": args.timeout,
    }

    print(f"Transferencia {transfer_id} — simulación: {simulacion}")
    estado_final = transferencia_saga(
        transfer_id=transfer_id,
        cuenta_origen="ACC-001",
        cuenta_destino="ACC-002",
        monto=10_000.0,
        simulacion=simulacion,
    )
    print(f"Estado final: {estado_final}")
