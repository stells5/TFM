"""Carga en SQLite de los precios de carburantes, con orquestación y logging.

Este módulo ata el patrón extract -> transform -> load -> log para la fuente
de gasolineras. `run()` es la función que `run_pipeline.py` programará con
la librería `schedule`.
"""
from datetime import datetime, timezone

import pandas as pd

from db.database import get_connection, init_db
from extract.gasolineras import extraer_precios
from logging_config import get_logger
from transform.gasolineras import transformar_precios

PIPELINE_NAME = "gasolineras"
logger = get_logger(PIPELINE_NAME)


def cargar_precios(df: pd.DataFrame) -> None:
    with get_connection() as conn:
        df.to_sql("precios_combustible", conn, if_exists="append", index=False)


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
    logger.info("Inicio de la ejecución del pipeline de gasolineras")
    try:
        estaciones = extraer_precios()
        logger.info("Extraídas %d estaciones", len(estaciones))

        df = transformar_precios(estaciones)
        logger.info("Transformadas %d filas de precios", len(df))

        cargar_precios(df)
        logger.info("Cargadas %d filas en precios_combustible", len(df))

        fin = datetime.now(timezone.utc).isoformat()
        _registrar_ejecucion(inicio, fin, "OK", len(df))
        logger.info("Ejecución completada correctamente")
    except Exception as exc:
        fin = datetime.now(timezone.utc).isoformat()
        logger.exception("Fallo en el pipeline de gasolineras")
        _registrar_ejecucion(inicio, fin, "ERROR", 0, str(exc))
        raise


if __name__ == "__main__":
    run()
