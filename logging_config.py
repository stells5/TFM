"""Configuración común de logging para todos los scripts del pipeline."""
import logging
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parent / "logs"


def get_logger(nombre: str) -> logging.Logger:
    LOGS_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(nombre)
    if logger.handlers:
        return logger  # ya configurado (evita duplicar handlers si se llama varias veces)

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    file_handler = logging.FileHandler(LOGS_DIR / f"{nombre}.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
