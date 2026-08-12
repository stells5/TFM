"""Orquestador del pipeline: programa la ejecución periódica de cada fuente
usando la librería `schedule`.

La periodicidad de cada fuente se configura en el fichero .env (ver
.env.example), sin tocar código. `rutas` (OSRM) no se programa aquí: los
pares origen-destino son fijos y solo se dan de alta a mano con
`python -m load.rutas` cuando se añade una ruta nueva.

El índice de riesgo/coste no tiene intervalo propio: se recalcula justo
después de cada ejecución de DGT, AEMET o gasolineras, que es lo único que
puede cambiar su resultado.
"""
import time

import schedule
from dotenv import load_dotenv

from config import AEMET_INTERVAL_MINUTES, DGT_INTERVAL_MINUTES, GASOLINERAS_HORA_DIARIA
from load import aemet, dgt, gasolineras, indice_riesgo
from logging_config import get_logger

load_dotenv()

logger = get_logger("run_pipeline")


def _ejecutar(nombre: str, funcion) -> None:
    """Ejecuta un pipeline protegiendo el bucle del scheduler: si falla, se
    registra (el propio pipeline ya lo deja en log_ejecuciones) y se sigue
    con la siguiente ejecución programada en vez de tumbar el proceso.
    """
    try:
        funcion()
    except Exception:
        logger.exception(
            "El pipeline '%s' ha fallado, se reintentará en su siguiente ejecución programada",
            nombre,
        )


def job_dgt() -> None:
    _ejecutar("dgt", dgt.run)
    _ejecutar("indice_riesgo", indice_riesgo.run)


def job_aemet() -> None:
    _ejecutar("aemet", aemet.run)
    _ejecutar("indice_riesgo", indice_riesgo.run)


def job_gasolineras() -> None:
    _ejecutar("gasolineras", gasolineras.run)
    _ejecutar("indice_riesgo", indice_riesgo.run)


def _primera_ejecucion() -> None:
    """Ejecuta las 4 fuentes una vez al arrancar, para no esperar al primer
    intervalo programado antes de tener datos."""
    logger.info("Primera ejecución inmediata de todas las fuentes")
    _ejecutar("dgt", dgt.run)
    _ejecutar("aemet", aemet.run)
    _ejecutar("gasolineras", gasolineras.run)
    _ejecutar("indice_riesgo", indice_riesgo.run)


def main() -> None:
    schedule.every(DGT_INTERVAL_MINUTES).minutes.do(job_dgt)
    schedule.every(AEMET_INTERVAL_MINUTES).minutes.do(job_aemet)
    schedule.every().day.at(GASOLINERAS_HORA_DIARIA).do(job_gasolineras)

    logger.info(
        "Pipeline programado: DGT cada %d min, AEMET cada %d min, gasolineras a las %s. "
        "El indice de riesgo se recalcula tras cada uno de ellos.",
        DGT_INTERVAL_MINUTES,
        AEMET_INTERVAL_MINUTES,
        GASOLINERAS_HORA_DIARIA,
    )

    _primera_ejecucion()

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
