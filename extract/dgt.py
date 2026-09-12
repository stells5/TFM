"""Extracción de incidencias de tráfico desde el NAP de la DGT (DATEX2 v3.6).

Nota: este feed excluye las incidencias de Cataluña y País Vasco (las
gestionan sus propias policías de tráfico, fuera del NAP estatal).
"""
import xml.etree.ElementTree as ET

import requests

URL = "https://nap.dgt.es/datex2/v3/dgt/SituationPublication/datex2_v36.xml"

NS = {
    "sit": "http://levelC/schema/3/situation",
    "com": "http://levelC/schema/3/common",
    "loc": "http://levelC/schema/3/locationReferencing",
    "lse": "http://levelC/schema/3/locationReferencingSpanishExtension",
}


def _texto(elem, xpath: str):
    hijo = elem.find(xpath, NS)
    return hijo.text if hijo is not None else None


def _coordenadas(record):
    """Lat/lon del primer punto localizado en locationReference. Tanto las
    incidencias puntuales (tpegPointLocation) como los tramos
    (tpegLinearLocation, que traen "from" y "to") incluyen pointCoordinates;
    para un tramo me quedo con el primero que aparece en el XML ("to").
    Devuelve (None, None) si el registro no trae coordenadas."""
    punto = record.find(".//loc:pointCoordinates", NS)
    if punto is None:
        return None, None
    lat = _texto(punto, "loc:latitude")
    lon = _texto(punto, "loc:longitude")
    return (float(lat) if lat is not None else None, float(lon) if lon is not None else None)


def _parsear_record(record) -> dict:
    lat, lon = _coordenadas(record)
    return {
        "situacion_id": record.get("id"),
        "cause_type": _texto(record, "sit:cause/sit:causeType"),
        "severity": _texto(record, "sit:severity"),
        "road_name": _texto(record, ".//loc:roadInformation/loc:roadName"),
        "province": _texto(record, ".//lse:province"),
        "municipality": _texto(record, ".//lse:municipality"),
        "km": _texto(record, ".//lse:kilometerPoint"),
        "lat": lat,
        "lon": lon,
        "start_time": _texto(
            record, "sit:validity/com:validityTimeSpecification/com:overallStartTime"
        ),
    }


def extraer_incidencias() -> list:
    """Descarga el feed nacional de incidencias activas de la DGT.

    Devuelve una lista de diccionarios "en crudo" (uno por situationRecord).
    """
    resp = requests.get(URL, timeout=60)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    incidencias = []
    for situacion in root.findall("sit:situation", NS):
        for record in situacion.findall("sit:situationRecord", NS):
            incidencias.append(_parsear_record(record))
    return incidencias


if __name__ == "__main__":
    datos = extraer_incidencias()
    print(f"Descargadas {len(datos)} incidencias.")
    print(datos[0])
