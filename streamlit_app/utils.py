"""Utilidades compartidas por las páginas del Streamlit: conexión a la base
de datos del pipeline, consultas reutilizadas y decodificación de las
polylines de OSRM. No hay servidor propio: se lee directamente `db/pipeline.db`.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.database import get_connection  # noqa: E402
from transform.indice_riesgo import (  # noqa: E402
    CIUDAD_REPRESENTATIVA_PROVINCIA,
    PESO_CAUSA,
    PESO_CAUSA_DEFECTO,
    provincias_de_ruta,
    via_en_direccion,
    vias_de_ruta,
)

# Tiempo de cacheo de las consultas: suficientemente corto para reflejar
# ejecuciones nuevas del pipeline sin recargar la base de datos en cada clic.
CACHE_TTL = 300


def coincide(texto: str, terminos: list) -> bool:
    """Comparación case/accent-insensitive por substring: mismo criterio que
    usa el pipeline (transform/indice_riesgo.py) para cruzar vía/provincia
    con incidencias, meteo y precios."""
    if not texto:
        return False
    texto = texto.casefold()
    return any(t.casefold() in texto for t in terminos)


@st.cache_data(ttl=CACHE_TTL)
def cargar_ranking() -> pd.DataFrame:
    """Último índice de riesgo/coste calculado para cada ruta."""
    query = """
        SELECT r.id AS ruta_id, r.origen, r.destino, r.variante,
               r.distancia_km, r.duracion_min,
               i.score_riesgo, i.score_coste,
               i.gasolinera_mas_barata, i.precio_mas_barato,
               i.viento_max, i.viento_max_provincia,
               i.lluvia_max, i.lluvia_max_provincia,
               i.incidencia_mas_grave_tipo, i.incidencia_mas_grave_via, i.incidencia_mas_grave_km,
               i.timestamp_calculo
        FROM indice_riesgo_ruta i
        JOIN rutas r ON r.id = i.ruta_id
        WHERE i.timestamp_calculo = (
            SELECT MAX(timestamp_calculo) FROM indice_riesgo_ruta WHERE ruta_id = i.ruta_id
        )
        ORDER BY r.origen, i.score_riesgo
    """
    with get_connection() as conn:
        return pd.read_sql(query, conn)


@st.cache_data(ttl=CACHE_TTL)
def cargar_rutas() -> pd.DataFrame:
    """Dimensión de rutas (dato estático, no cambia salvo al dar de alta una nueva)."""
    with get_connection() as conn:
        return pd.read_sql(
            "SELECT id, origen, destino, variante, distancia_km, duracion_min, "
            "geometry_osrm_polyline FROM rutas",
            conn,
        )


def vias_y_provincias(ruta_id: int):
    """Vías y provincias de una ruta (para cruzar con incidencias/meteo/precios)."""
    with get_connection() as conn:
        return vias_de_ruta(conn, ruta_id), provincias_de_ruta(conn, ruta_id)


@st.cache_data(ttl=CACHE_TTL)
def cargar_incidencias_activas(vias: tuple, provincias: tuple) -> pd.DataFrame:
    """Incidencias de la última captura de la DGT que afectan a las vías/provincias dadas."""
    if not vias:
        return pd.DataFrame()
    placeholders = ",".join("?" * len(vias))
    query = f"""
        SELECT via, provincia, municipio, tipo_incidencia, severidad, km, lat, lon, timestamp_inicio
        FROM incidencias_trafico
        WHERE via IN ({placeholders})
        AND timestamp_captura = (SELECT MAX(timestamp_captura) FROM incidencias_trafico)
    """
    with get_connection() as conn:
        df = pd.read_sql(query, conn, params=vias)
    if provincias and not df.empty:
        df = df[df["provincia"].apply(lambda p: coincide(p, list(provincias)))]
    return df


@st.cache_data(ttl=CACHE_TTL)
def cargar_gasolineras_ruta(vias: tuple, provincias: tuple, tipo_combustible: str = "gasoleo_a") -> pd.DataFrame:
    """Gasolineras (última lectura de precio) cuya dirección menciona alguna vía de la ruta
    como código completo (ver via_en_direccion: "A-2" no debe colar "A-22")."""
    if not vias:
        return pd.DataFrame()
    query = """
        SELECT provincia, municipio, direccion, precio, timestamp_captura
        FROM precios_combustible
        WHERE tipo_combustible = ?
        AND timestamp_captura = (SELECT MAX(timestamp_captura) FROM precios_combustible)
    """
    with get_connection() as conn:
        df = pd.read_sql(query, conn, params=[tipo_combustible])
    if not df.empty:
        df = df[df["direccion"].apply(lambda d: via_en_direccion(d, list(vias)))]
    if provincias and not df.empty:
        df = df[df["provincia"].apply(lambda p: coincide(p, list(provincias)))]
    return df.sort_values("precio")


@st.cache_data(ttl=CACHE_TTL)
def tendencia_incidencias(vias: tuple, provincias: tuple) -> pd.DataFrame:
    """Histórico completo (todas las capturas) de incidencias en las vías de la ruta."""
    if not vias:
        return pd.DataFrame()
    placeholders = ",".join("?" * len(vias))
    query = f"""
        SELECT provincia, tipo_incidencia, severidad, timestamp_captura
        FROM incidencias_trafico
        WHERE via IN ({placeholders})
    """
    with get_connection() as conn:
        df = pd.read_sql(query, conn, params=vias)
    if provincias and not df.empty:
        df = df[df["provincia"].apply(lambda p: coincide(p, list(provincias)))]
    return df


@st.cache_data(ttl=CACHE_TTL)
def capturas_dgt_por_dia() -> pd.DataFrame:
    """Nº de ejecuciones del pipeline de DGT por día, contando TODAS las
    capturas (no solo las de una vía concreta). Sirve de denominador para
    "incidencias activas por captura": si se filtrara por las capturas que
    aparecen en tendencia_incidencias, un día en el que la ruta no tuvo
    ninguna incidencia activa no contaría ninguna captura ese día, e
    infla la media artificialmente."""
    with get_connection() as conn:
        df = pd.read_sql("SELECT DISTINCT timestamp_captura FROM incidencias_trafico", conn)
    if df.empty:
        return df
    df["fecha"] = pd.to_datetime(df["timestamp_captura"]).dt.floor("D")
    return df.groupby("fecha").size().reset_index(name="capturas")


@st.cache_data(ttl=CACHE_TTL)
def tendencia_precios(vias: tuple, provincias: tuple, tipo_combustible: str = "gasoleo_a") -> pd.DataFrame:
    """Histórico completo de precios de combustible en las gasolineras de la ruta
    (vía como código completo, ver via_en_direccion)."""
    if not vias:
        return pd.DataFrame()
    query = """
        SELECT provincia, direccion, precio, timestamp_captura
        FROM precios_combustible
        WHERE tipo_combustible = ?
    """
    with get_connection() as conn:
        df = pd.read_sql(query, conn, params=[tipo_combustible])
    if not df.empty:
        df = df[df["direccion"].apply(lambda d: via_en_direccion(d, list(vias)))]
    if provincias and not df.empty:
        df = df[df["provincia"].apply(lambda p: coincide(p, list(provincias)))]
    return df.drop(columns=["direccion"])


@st.cache_data(ttl=CACHE_TTL)
def tendencia_meteo(provincias: tuple) -> pd.DataFrame:
    """Histórico completo de meteo en las estaciones representativas de las provincias dadas."""
    if not provincias:
        return pd.DataFrame()
    with get_connection() as conn:
        df = pd.read_sql(
            "SELECT zona_aemet, precipitacion, viento, timestamp_observacion FROM condiciones_meteo",
            conn,
        )
    trozos = []
    for provincia in provincias:
        ciudad = CIUDAD_REPRESENTATIVA_PROVINCIA.get(provincia, provincia)
        sub = df[df["zona_aemet"].apply(lambda z: coincide(z, [ciudad]))].copy()
        if not sub.empty:
            sub["provincia"] = provincia
            trozos.append(sub)
    return pd.concat(trozos, ignore_index=True) if trozos else pd.DataFrame()


def decode_polyline(encoded: str, precision: int = 5):
    """Decodifica una polyline codificada (algoritmo estándar de Google/OSRM,
    precisión 5) en una lista de tuplas (lat, lon)."""
    factor = 10 ** precision
    coords = []
    index = 0
    lat = 0
    lon = 0
    length = len(encoded)
    while index < length:
        shift, result = 0, 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if result & 1 else (result >> 1)
        lat += dlat

        shift, result = 0, 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlon = ~(result >> 1) if result & 1 else (result >> 1)
        lon += dlon

        coords.append((lat / factor, lon / factor))
    return coords


def color_riesgo(score, minimo, maximo):
    """Color RGBA (verde=bajo riesgo, rojo=alto riesgo) según la posición de
    `score` en el rango [minimo, maximo] de todas las rutas."""
    if score is None or pd.isna(score):
        return [140, 140, 140, 160]
    if maximo == minimo:
        t = 0.0
    else:
        t = (score - minimo) / (maximo - minimo)
    t = max(0.0, min(1.0, t))
    r = int(60 + 195 * t)
    g = int(180 - 140 * t)
    return [r, g, 60, 200]


def color_riesgo_css(score, minimo, maximo) -> str:
    """Igual que color_riesgo pero como color CSS, para tarjetas HTML."""
    r, g, b, _a = color_riesgo(score, minimo, maximo)
    return f"rgb({r},{g},{b})"


def _distancia_minima_km(lat: float, lon: float, coords_ruta: np.ndarray) -> float:
    """Distancia (km, fórmula de haversine) del punto (lat, lon) al punto más
    cercano de `coords_ruta` (array Nx2 de [lat, lon])."""
    R = 6371.0
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    lat2 = np.radians(coords_ruta[:, 0])
    lon2 = np.radians(coords_ruta[:, 1])
    dphi = lat2 - lat1
    dlambda = lon2 - lon1
    a = np.sin(dphi / 2) ** 2 + math.cos(lat1) * np.cos(lat2) * np.sin(dlambda / 2) ** 2
    return float((2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))).min())


def filtrar_por_proximidad(incidencias: pd.DataFrame, coords_ruta: list, umbral_km: float = 2.0) -> pd.DataFrame:
    """Se queda solo con las incidencias cuya coordenada cae a menos de
    `umbral_km` de algún punto de la geometría real de la ruta (OSRM).

    Más preciso que el cruce por vía/provincia usado en el resto del
    proyecto (transform/indice_riesgo.py): una vía larga (ej. A-2) puede
    tener incidencias a decenas de km del tramo que usa esta ruta en
    concreto, aunque compartan nombre de vía y provincia.
    """
    if incidencias.empty or not coords_ruta:
        return incidencias.iloc[0:0]
    coords = np.array(coords_ruta)
    mask = incidencias.apply(
        lambda r: _distancia_minima_km(r["lat"], r["lon"], coords) <= umbral_km, axis=1
    )
    return incidencias[mask]


def estilo_incidencia(tipo_incidencia: str):
    """Radio (metros) y color de un punto de incidencia en el mapa, según el
    mismo peso de causa que usa el índice de riesgo (transform/indice_riesgo.py):
    a más peso (más grave), punto más grande y más rojo."""
    peso = PESO_CAUSA.get(tipo_incidencia, PESO_CAUSA_DEFECTO)
    peso_max = max(PESO_CAUSA.values())
    t = min(peso / peso_max, 1.0)
    radio = 800 + 2200 * t
    color = [int(200 + 55 * t), int(140 - 100 * t), 30, 220]
    return radio, color


def nivel_riesgo(score, q33: float, q66: float) -> str:
    """Etiqueta cualitativa del riesgo según su posición frente a los
    terciles de score_riesgo de todas las rutas del dataset."""
    if score is None or pd.isna(score):
        return "Sin datos"
    if score <= q33:
        return "Bajo"
    if score <= q66:
        return "Medio"
    return "Alto"
