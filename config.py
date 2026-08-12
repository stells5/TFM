"""Configuración de periodicidad del pipeline, editable desde .env sin tocar código."""
import os

from dotenv import load_dotenv

load_dotenv()

DGT_INTERVAL_MINUTES = int(os.getenv("DGT_INTERVAL_MINUTES", "20"))
AEMET_INTERVAL_MINUTES = int(os.getenv("AEMET_INTERVAL_MINUTES", "120"))
GASOLINERAS_HORA_DIARIA = os.getenv("GASOLINERAS_HORA_DIARIA", "06:00")
