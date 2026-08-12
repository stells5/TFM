"""Extracción de rutas desde el servidor demo de OSRM."""
import requests

OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving"


def obtener_rutas(lon_origen: float, lat_origen: float, lon_destino: float, lat_destino: float) -> dict:
    """Consulta a OSRM los trayectos en coche entre dos puntos, incluyendo
    caminos alternativos cuando existe más de uno razonable.

    Devuelve la respuesta JSON tal cual la entrega la API (incluye distancia,
    duración, geometría y el detalle paso a paso de cada alternativa).
    """
    coords = f"{lon_origen},{lat_origen};{lon_destino},{lat_destino}"
    url = f"{OSRM_BASE_URL}/{coords}"
    params = {
        "overview": "full",
        "geometries": "polyline",
        "steps": "true",
        "alternatives": "true",
        "annotations": "false",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    datos = obtener_rutas(-0.8891, 41.6488, 2.1686, 41.3874)
    print(f"{len(datos['routes'])} alternativa(s) encontradas")
