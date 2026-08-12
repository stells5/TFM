"""Cálculo del score_riesgo y score_coste de una ruta a partir de lo que ya
hay en la base de datos (incidencias DGT, meteo AEMET, precios de gasolineras).

No hay tramo_id/coordenadas exactas: el cruce se hace por texto (nombre de
vía, nombre de ciudad/provincia), el mismo criterio usado en todo el proyecto.
"""
import sqlite3

# Peso base de cada incidencia según su tipo (la DGT casi nunca informa la
# severidad -ver PESO_SEVERIDAD abajo-, así que el tipo es la señal que más
# fiablemente tenemos: un accidente pesa más que unas obras rutinarias).
PESO_CAUSA = {
    "accident": 3,
    "infrastructureDamageObstruction": 3,
    "environmentalObstruction": 2,
    "vehicleObstruction": 1.5,
    "obstruction": 1.5,
    "poorEnvironment": 1.5,
    "abnormalTraffic": 1,
    "roadOrCarriagewayOrLaneManagement": 1,
    "roadMaintenance": 0.5,
}
PESO_CAUSA_DEFECTO = 1

# Cuando la DGT sí informa la severidad, actúa como multiplicador sobre el
# peso de la causa (si no la informa, no escala: multiplicador 1).
MULTIPLICADOR_SEVERIDAD = {"highest": 2.0, "high": 1.5, "medium": 1.2}
MULTIPLICADOR_SEVERIDAD_DEFECTO = 1.0

# Umbrales para considerar que el tiempo añade riesgo a la ruta.
UMBRAL_PRECIPITACION_MM = 5.0
UMBRAL_VIENTO_MS = 10.0
PUNTOS_LLUVIA = 2
PUNTOS_VIENTO = 1

# Ciudad por la que se busca cada provincia en los nombres de estación de
# AEMET (normalmente la capital, salvo cuando la propia provincia no sirve
# como término de búsqueda, ej. "Bizkaia" -> se busca "BILBAO").
CIUDAD_REPRESENTATIVA_PROVINCIA = {
    "Bizkaia": "BILBAO",
    "La Rioja": "LOGROÑO",
    "Navarra": "PAMPLONA",
    "Álava": "VITORIA",
}


def vias_de_ruta(conn: sqlite3.Connection, ruta_id: int) -> list:
    filas = conn.execute(
        "SELECT nombre_via FROM tramos_carretera WHERE ruta_id = ?", (ruta_id,)
    ).fetchall()
    return [f[0] for f in filas]


def provincias_de_ruta(conn: sqlite3.Connection, ruta_id: int) -> list:
    filas = conn.execute(
        "SELECT provincia FROM ruta_provincias WHERE ruta_id = ?", (ruta_id,)
    ).fetchall()
    return [f[0] for f in filas]


def _provincia_coincide(provincia_fila, provincias_ruta: list) -> bool:
    """Compara ignorando mayúsculas/acentos y nombres bilingües tipo
    "València/Valencia" (DGT) frente a "VALENCIA" (gasolineras)."""
    if not provincia_fila:
        return False
    texto = provincia_fila.casefold()
    return any(p.casefold() in texto for p in provincias_ruta)


def _peso_incidencia(tipo_incidencia, severidad) -> float:
    """Peso de una incidencia: su causa (causeType) multiplicada por la
    severidad cuando la DGT la informa (rara vez)."""
    peso = PESO_CAUSA.get(tipo_incidencia, PESO_CAUSA_DEFECTO)
    multiplicador = MULTIPLICADOR_SEVERIDAD.get(severidad, MULTIPLICADOR_SEVERIDAD_DEFECTO)
    return peso * multiplicador


def calcular_riesgo_trafico(conn: sqlite3.Connection, vias: list, provincias: list) -> float:
    """Suma ponderada de incidencias activas en alguna de las vías dadas,
    exigiendo además que estén en una de las provincias de la ruta (evita
    contar incidencias de la misma vía pero a cientos de km, ej. la A-7).

    Solo mira la última captura de la DGT: incidencias_trafico acumula el
    histórico de cada ejecución, así que sin este filtro una misma incidencia
    activa se contaría una vez por cada vez que se ha capturado.
    """
    if not vias:
        return 0.0
    placeholders = ",".join("?" * len(vias))
    filas = conn.execute(
        f"""
        SELECT tipo_incidencia, severidad, provincia FROM incidencias_trafico
        WHERE via IN ({placeholders})
        AND timestamp_captura = (SELECT MAX(timestamp_captura) FROM incidencias_trafico)
        """,
        vias,
    ).fetchall()

    riesgo = 0.0
    for tipo_incidencia, severidad, provincia in filas:
        if provincias and not _provincia_coincide(provincia, provincias):
            continue
        riesgo += _peso_incidencia(tipo_incidencia, severidad)
    return riesgo


def incidencia_mas_grave(conn: sqlite3.Connection, vias: list, provincias: list):
    """Incidencia de mayor peso (mismo criterio que calcular_riesgo_trafico)
    entre las que afectan a la ruta. Devuelve (tipo_incidencia, via, km), con
    None en los tres si no hay ninguna incidencia. Igual que calcular_riesgo_trafico,
    solo mira la última captura de la DGT.
    """
    if not vias:
        return None, None, None
    placeholders = ",".join("?" * len(vias))
    filas = conn.execute(
        f"""
        SELECT tipo_incidencia, severidad, provincia, via, km
        FROM incidencias_trafico
        WHERE via IN ({placeholders})
        AND timestamp_captura = (SELECT MAX(timestamp_captura) FROM incidencias_trafico)
        """,
        vias,
    ).fetchall()

    mejor_peso = -1.0
    resultado = (None, None, None)
    for tipo_incidencia, severidad, provincia, via, km in filas:
        if provincias and not _provincia_coincide(provincia, provincias):
            continue
        peso = _peso_incidencia(tipo_incidencia, severidad)
        if peso > mejor_peso:
            mejor_peso = peso
            resultado = (tipo_incidencia, via, km)
    return resultado


def _zona_coincide(zona, ciudades: list) -> bool:
    """Igual que _provincia_coincide pero para zona_aemet: comparación por
    substring en Python (no SQL LIKE), porque LIKE en SQLite solo ignora
    mayúsculas/minúsculas en ASCII y falla con acentos (ej. 'Jaén' LIKE
    '%Jaén%' no encuentra la estación 'JAÉN')."""
    if not zona:
        return False
    texto = zona.casefold()
    return any(c.casefold() in texto for c in ciudades)


def calcular_riesgo_meteo(conn: sqlite3.Connection, provincias: list) -> float:
    """Riesgo por lluvia/viento fuerte a lo largo de la ruta: mira la
    lectura más reciente de una estación representativa de cada provincia
    que cruza la ruta (no solo origen/destino).
    """
    if not provincias:
        return 0.0
    ciudades = [CIUDAD_REPRESENTATIVA_PROVINCIA.get(p, p) for p in provincias]
    filas = conn.execute(
        """
        SELECT zona_aemet, precipitacion, viento, timestamp_observacion
        FROM condiciones_meteo
        ORDER BY timestamp_observacion DESC
        """
    ).fetchall()

    # Nos quedamos solo con la lectura más reciente de cada estación.
    vistas = set()
    riesgo = 0.0
    for zona, precipitacion, viento, _ts in filas:
        if not _zona_coincide(zona, ciudades) or zona in vistas:
            continue
        vistas.add(zona)
        if precipitacion is not None and precipitacion > UMBRAL_PRECIPITACION_MM:
            riesgo += PUNTOS_LLUVIA
        if viento is not None and viento > UMBRAL_VIENTO_MS:
            riesgo += PUNTOS_VIENTO
    return riesgo


def calcular_meteo_max(conn: sqlite3.Connection, provincias: list):
    """Viento y lluvia máximos (última lectura de la estación representativa
    de cada provincia) a lo largo de la ruta, y en qué provincia se dio cada
    máximo. Devuelve (viento_max, viento_max_provincia, lluvia_max, lluvia_max_provincia),
    con None en los cuatro si no hay datos.
    """
    if not provincias:
        return None, None, None, None
    ciudad_de = {p: CIUDAD_REPRESENTATIVA_PROVINCIA.get(p, p) for p in provincias}
    filas = conn.execute(
        """
        SELECT zona_aemet, precipitacion, viento, timestamp_observacion
        FROM condiciones_meteo
        ORDER BY timestamp_observacion DESC
        """
    ).fetchall()

    viento_max = viento_max_provincia = None
    lluvia_max = lluvia_max_provincia = None
    pendientes = set(provincias)
    for zona, precipitacion, viento, _ts in filas:
        if not pendientes:
            break
        # La primera coincidencia de cada provincia es la más reciente,
        # porque las filas vienen ordenadas por timestamp_observacion DESC.
        for provincia in [p for p in pendientes if _zona_coincide(zona, [ciudad_de[p]])]:
            pendientes.discard(provincia)
            if viento is not None and (viento_max is None or viento > viento_max):
                viento_max, viento_max_provincia = viento, provincia
            if precipitacion is not None and (lluvia_max is None or precipitacion > lluvia_max):
                lluvia_max, lluvia_max_provincia = precipitacion, provincia
    return viento_max, viento_max_provincia, lluvia_max, lluvia_max_provincia


def _gasolineras_de_ruta(
    conn: sqlite3.Connection, vias: list, provincias: list, tipo_combustible: str
) -> list:
    """Filas (municipio, direccion, precio) de precios_combustible cuya
    dirección menciona alguna de las vías dadas y cuya provincia es una de
    las de la ruta."""
    if not vias:
        return []
    condiciones = " OR ".join("direccion LIKE ?" for _ in vias)
    patrones = [f"%{v}%" for v in vias]
    filas = conn.execute(
        f"""
        SELECT municipio, direccion, precio, provincia FROM precios_combustible
        WHERE tipo_combustible = ? AND ({condiciones})
        """,
        [tipo_combustible] + patrones,
    ).fetchall()

    return [
        (municipio, direccion, precio)
        for municipio, direccion, precio, provincia in filas
        if not provincias or _provincia_coincide(provincia, provincias)
    ]


def calcular_score_coste(
    conn: sqlite3.Connection, vias: list, provincias: list, tipo_combustible: str = "gasoleo_a"
):
    """Precio medio (€/L) del combustible en las gasolineras de la ruta.
    Devuelve None si no hay datos.
    """
    gasolineras = _gasolineras_de_ruta(conn, vias, provincias, tipo_combustible)
    if not gasolineras:
        return None
    precios = [precio for _municipio, _direccion, precio in gasolineras]
    return sum(precios) / len(precios)


def encontrar_gasolinera_mas_barata(
    conn: sqlite3.Connection, vias: list, provincias: list, tipo_combustible: str = "gasoleo_a"
):
    """Gasolinera más barata de la ruta. Devuelve (etiqueta, precio) o
    (None, None) si no hay datos.
    """
    gasolineras = _gasolineras_de_ruta(conn, vias, provincias, tipo_combustible)
    if not gasolineras:
        return None, None

    municipio, direccion, precio = min(gasolineras, key=lambda g: g[2])
    etiqueta = f"{municipio} ({direccion})" if direccion else municipio
    return etiqueta, precio
