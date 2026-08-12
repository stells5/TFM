"""Carga en SQLite de las observaciones meteorológicas, con orquestación y logging."""
from datetime import datetime, timezone

import pandas as pd

from db.database import get_connection, init_db
from extract.aemet import extraer_observaciones
from logging_config import get_logger
from transform.aemet import transformar_observaciones

PIPELINE_NAME = "aemet"
logger = get_logger(PIPELINE_NAME)


def cargar_observaciones(df: pd.DataFrame) -> None:
    with get_connection() as conn:
        df.to_sql("condiciones_meteo", conn, if_exists="append", index=False)


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
    logger.info("Inicio de la ejecución del pipeline de AEMET")
    try:
        observaciones = extraer_observaciones()
        logger.info("Extraídas %d observaciones", len(observaciones))

        df = transformar_observaciones(observaciones)
        logger.info("Transformadas %d filas de observaciones", len(df))

        cargar_observaciones(df)
        logger.info("Cargadas %d filas en condiciones_meteo", len(df))

        fin = datetime.now(timezone.utc).isoformat()
        _registrar_ejecucion(inicio, fin, "OK", len(df))
        logger.info("Ejecución completada correctamente")
    except Exception as exc:
        fin = datetime.now(timezone.utc).isoformat()
        logger.exception("Fallo en el pipeline de AEMET")
        _registrar_ejecucion(inicio, fin, "ERROR", 0, str(exc))
        raise


if __name__ == "__main__":
    run()
