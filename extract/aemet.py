"""Extracción de observaciones meteorológicas desde AEMET OpenData.

Requiere una API key gratuita (https://opendata.aemet.es/centrodedescargas/altaUsuario),
guardada en la variable de entorno AEMET_API_KEY (fichero .env, ver .env.example).
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://opendata.aemet.es/opendata/api"
OBSERVACION_URL = f"{BASE_URL}/observacion/convencional/todas"


def _api_key() -> str:
    api_key = os.getenv("AEMET_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta AEMET_API_KEY. Crea un fichero .env (copia .env.example) con tu clave de "
            "https://opendata.aemet.es/centrodedescargas/altaUsuario"
        )
    return api_key


def _obtener_datos(endpoint_url: str):
    """AEMET responde en dos pasos: primero da una URL temporal con los
    datos reales, que hay que volver a descargar."""
    resp = requests.get(endpoint_url, params={"api_key": _api_key()}, timeout=30)
    resp.raise_for_status()
    referencia = resp.json()
    if referencia.get("estado") != 200:
        raise RuntimeError(f"AEMET devolvió un error: {referencia.get('descripcion')}")

    resp_datos = requests.get(referencia["datos"], timeout=30)
    resp_datos.raise_for_status()
    return resp_datos.json()


def extraer_observaciones() -> list:
    """Descarga las observaciones meteorológicas de todas las estaciones de España."""
    return _obtener_datos(OBSERVACION_URL)


if __name__ == "__main__":
    datos = extraer_observaciones()
    print(f"Descargadas {len(datos)} observaciones.")
    print(datos[0])
