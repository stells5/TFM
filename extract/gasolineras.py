"""Extracción de precios de carburantes desde el Geoportal de Gasolineras (MITECO)."""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

BASE_URL = (
    "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes"
    "/PreciosCarburantes/EstacionesTerrestres/FiltroProvincia"
)


class _LegacyTLSAdapter(HTTPAdapter):
    """El servidor del Ministerio usa una configuración TLS obsoleta que el
    OpenSSL moderno rechaza por defecto ("SSLEOFError"). Bajamos el nivel de
    seguridad de los cifrados sólo para este host."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def _session() -> requests.Session:
    s = requests.Session()
    s.mount("https://", _LegacyTLSAdapter())
    return s

# Códigos de provincia (INE) que atraviesan las 6 rutas del proyecto
# (ver ORIGENES_DESTINOS en load/rutas.py). Añade aquí el código de
# cualquier provincia nueva que necesites cubrir.
PROVINCIAS = {
    "50": "Zaragoza",
    "28": "Madrid",
    "08": "Barcelona",
    "48": "Bizkaia",
    "22": "Huesca",
    "25": "Lleida",
    "19": "Guadalajara",
    "16": "Cuenca",
    "46": "Valencia",
    "12": "Castellón",
    "43": "Tarragona",
    "09": "Burgos",
    "31": "Navarra",
    "26": "La Rioja",
}


def extraer_precios(provincias: dict = PROVINCIAS) -> list:
    """Descarga las estaciones de servicio de cada provincia indicada.

    Devuelve una lista de diccionarios "en crudo", tal y como los entrega
    la API (una entrada por estación de servicio).
    """
    estaciones = []
    with _session() as s:
        for codigo in provincias:
            url = f"{BASE_URL}/{codigo}"
            resp = s.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            estaciones.extend(data["ListaEESSPrecio"])
    return estaciones


if __name__ == "__main__":
    datos = extraer_precios()
    print(f"Descargadas {len(datos)} estaciones de servicio.")
    print(datos[0])
