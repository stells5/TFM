"""Carga en SQLite de las incidencias de tráfico, con orquestación y logging."""
from datetime import datetime, timezone

import pandas as pd

from db.database import get_connection, init_db
from extract.dgt import extraer_incidencias
from logging_config import get_logger
from transform.dgt import transformar_incidencias

PIPELINE_NAME = "dgt"
logger = get_logger(PIPELINE_NAME)


def cargar_incidencias(df: pd.DataFrame) -> None:
    with get_connection() as conn:
        df.to_sql("incidencias_trafico", conn, if_exists="append", index=False)


def _registrar_ejecucion(inicio, fin, status, filas, error_msg=None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO log_ejecuciones
                (pipeline_name, timestamp_inicio, timestamp_fin, status, filas_procesadas, error_msg)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (PIPELINE_NAME, inicio, fin, status, filas, error_msg),
        )


def run() -> None:
    init_db()
    inicio = datetime.now(timezone.utc).isoformat()
    logger.info("Inicio de la ejecución del pipeline de DGT")
    try:
        incidencias = extraer_incidencias()
        logger.info("Extraídas %d incidencias", len(incidencias))

        df = transformar_incidencias(incidencias)
        logger.info("Transformadas %d filas de incidencias", len(df))

        cargar_incidencias(df)
        logger.info("Cargadas %d filas en incidencias_trafico", len(df))

        fin = datetime.now(timezone.utc).isoformat()
        _registrar_ejecucion(inicio, fin, "OK", len(df))
        logger.info("Ejecución completada correctamente")
    except Exception as exc:
        fin = datetime.now(timezone.utc).isoformat()
        logger.exception("Fallo en el pipeline de DGT")
        _registrar_ejecucion(inicio, fin, "ERROR", 0, str(exc))
        raise


if __name__ == "__main__":
    run()
