"""Transformación de la respuesta de OSRM a las variantes que necesita la tabla `rutas`."""


def _extraer_vias(ruta: dict) -> list:
    """Códigos de vía (ref, ej. "A-2", "AP-68") de un trayecto, en el orden
    en que aparecen."""
    vias = []
    for step in ruta["legs"][0]["steps"]:
        ref = step.get("ref")
        if not ref:
            continue
        # OSRM junta varios códigos en un mismo tramo con ";" (ej. "Z-40; A-2")
        for codigo in ref.split(";"):
            codigo = codigo.strip()
            if codigo and codigo not in vias:
                vias.append(codigo)
    return vias


def transformar_rutas(datos_osrm: dict) -> list:
    """Convierte la respuesta de OSRM en una lista de variantes de ruta,
    cada una con su distancia, duración base (sin incidencias, tráfico fluido),
    geometría y los códigos de vía que atraviesa.
    """
    variantes = []
    for ruta in datos_osrm["routes"]:
        vias = _extraer_vias(ruta)
        variantes.append(
            {
                "distancia_km": round(ruta["distance"] / 1000, 1),
                "duracion_min": round(ruta["duration"] / 60, 1),
                "geometry_osrm_polyline": ruta["geometry"],
                "vias": vias,
                "variante": ", ".join(vias) if vias else "sin nombre",
            }
        )
    return variantes
