"""Puebla las tablas de dimensión `rutas` y `tramos_carretera` a partir de OSRM.

Cada par origen-destino puede tener varias variantes (caminos alternativos,
ej. autopista de peaje vs carretera libre); cada variante se guarda como una
fila independiente en `rutas`, para poder comparar su riesgo/coste entre sí.

A diferencia de los otros pipelines (gasolineras, DGT, AEMET), este no se
programa de forma periódica: los pares origen-destino son fijos y solo hay
que volver a ejecutar este script cuando se añade uno nuevo a ORIGENES_DESTINOS.
"""
from db.database import get_connection, init_db
from extract.osrm import obtener_rutas
from logging_config import get_logger
from transform.rutas import transformar_rutas

PIPELINE_NAME = "rutas"
logger = get_logger(PIPELINE_NAME)

# Coordenadas (lon, lat) de los pares origen-destino fijos del proyecto.
# Elegidos porque OSRM ofrece más de un camino real y comparable entre sí.
ORIGENES_DESTINOS = [
    {
        "origen": "Zaragoza",
        "destino": "Barcelona",
        "origen_coords": (-0.8891, 41.6488),
        "destino_coords": (2.1686, 41.3874),
    },
    {
        "origen": "Madrid",
        "destino": "Barcelona",
        "origen_coords": (-3.7038, 40.4168),
        "destino_coords": (2.1686, 41.3874),
    },
    {
        "origen": "Bilbao",
        "destino": "Barcelona",
        "origen_coords": (-2.9350, 43.2630),
        "destino_coords": (2.1686, 41.3874),
    },
    {
        "origen": "Sevilla",
        "destino": "Barcelona",
        "origen_coords": (-5.9845, 37.3891),
        "destino_coords": (2.1686, 41.3874),
    },
    {
        "origen": "A Coruña",
        "destino": "Barcelona",
        "origen_coords": (-8.4115, 43.3623),
        "destino_coords": (2.1686, 41.3874),
    },
]

# Provincias que cruza cada variante, definidas a mano (geografía real +
# contraste con las provincias que ya vimos en incidencias_trafico para
# esas mismas vías). Clave = el texto exacto de rutas.variante.
PROVINCIAS_POR_VARIANTE = {
    "N-330, Z-40, A-2, AP-2, AP-7, B-23": [
        "Zaragoza", "Huesca", "Lleida", "Tarragona", "Barcelona",
    ],
    "N-330, A-23, A-22, A-2, B-23": [
        "Zaragoza", "Huesca", "Lleida", "Barcelona",
    ],
    "A-2, AP-2, AP-7, B-23": [
        "Madrid", "Guadalajara", "Soria", "Zaragoza", "Lleida", "Tarragona", "Barcelona",
    ],
    "M-30, A-3, A-7, AP-7, C-32, B-25, C-31C, C-31": [
        "Madrid", "Cuenca", "Valencia", "Castellón", "Tarragona", "Barcelona",
    ],
    "BI-10, A-8, AP-68, Z-40, A-2, AP-2, AP-7, B-23": [
        "Bizkaia", "La Rioja", "Zaragoza", "Huesca", "Lleida", "Tarragona", "Barcelona",
    ],
    # Verificada por geocodificación inversa sobre la geometría real: no pasa
    # por Burgos ni Zaragoza (el A-21 va directo de Navarra a Huesca), y sí
    # cruza Álava, que la lista original no contemplaba.
    "BI-10, A-8, AP-68, N-622, A-1, A-10, AP-15, A-15, A-21, N-240, A-132, A-23, A-22, A-2, B-23": [
        "Bizkaia", "Álava", "Navarra", "Huesca", "Lleida", "Barcelona",
    ],
    # Provincias verificadas por geocodificación inversa (Nominatim) sobre la
    # geometría real de la ruta, no solo a mano.
    "A-4, A-43, A-3, A-7, AP-7, C-32, B-25, C-31C, C-31": [
        "Sevilla", "Córdoba", "Jaén", "Ciudad Real", "Cuenca", "Valencia", "Castellón", "Tarragona", "Barcelona",
    ],
    "N-630, SE-30, A-66, A-5, A-5R, M-40, M-14, A-2, AP-2, AP-7, B-23": [
        "Sevilla", "Badajoz", "Cáceres", "Toledo", "Madrid", "Guadalajara", "Soria",
        "Zaragoza", "Huesca", "Lleida", "Tarragona", "Barcelona",
    ],
    "AC-11, AP-9, AP-9M, A-6, AP-71, A-66, A-231, BU-30R, BU-30, A-1, AP-1, N-232, N-126, AP-68, Z-40, A-2, AP-2, AP-7, B-23": [
        "A Coruña", "Lugo", "León", "Palencia", "Burgos", "La Rioja", "Navarra",
        "Zaragoza", "Huesca", "Lleida", "Tarragona", "Barcelona",
    ],
    # A diferencia de la ruta larga de Bilbao (mismas vías A-1..A-22 en teoría),
    # la geocodificación real confirma que este trayecto no llega a entrar en
    # Zaragoza: el A-21 pasa de Navarra a Huesca directamente. Sí cruza Álava,
    # que no estaba contemplada en ninguna otra ruta.
    "AC-11, AP-9, AP-9M, A-6, AP-71, A-66, A-231, BU-30R, BU-30, A-1, AP-1, A-10, AP-15, A-15, A-21, N-240, A-132, A-23, A-22, A-2, B-23": [
        "A Coruña", "Lugo", "León", "Palencia", "Burgos", "Álava", "Navarra",
        "Huesca", "Lleida", "Barcelona",
    ],
}


def _poblar_provincias(conn, ruta_id: int, variante: str) -> None:
    ya_existe = conn.execute(
        "SELECT id FROM ruta_provincias WHERE ruta_id = ?", (ruta_id,)
    ).fetchone()
    if ya_existe:
        return

    provincias = PROVINCIAS_POR_VARIANTE.get(variante)
    if not provincias:
        logger.warning("Sin provincias definidas para la variante '%s' (ruta_id=%d)", variante, ruta_id)
        return

    for provincia in provincias:
        conn.execute(
            "INSERT INTO ruta_provincias (ruta_id, provincia) VALUES (?, ?)",
            (ruta_id, provincia),
        )


def run() -> None:
    init_db()
    with get_connection() as conn:
        # Rutas que ya existan de una ejecución anterior: solo hace falta
        # rellenarles las provincias si aún no las tienen (no hace falta
        # volver a llamar a OSRM).
        for ruta_id, variante in conn.execute("SELECT id, variante FROM rutas").fetchall():
            _poblar_provincias(conn, ruta_id, variante)

        for par in ORIGENES_DESTINOS:
            lon_o, lat_o = par["origen_coords"]
            lon_d, lat_d = par["destino_coords"]
            datos = obtener_rutas(lon_o, lat_o, lon_d, lat_d)
            variantes = transformar_rutas(datos)

            for variante in variantes:
                ya_existe = conn.execute(
                    "SELECT id, duracion_min FROM rutas WHERE origen = ? AND destino = ? AND variante = ?",
                    (par["origen"], par["destino"], variante["variante"]),
                ).fetchone()
                if ya_existe:
                    # Rutas creadas antes de añadir duracion_min al esquema
                    # se quedaron sin ese dato: lo rellenamos ahora que ya
                    # tenemos la respuesta fresca de OSRM.
                    ruta_id_existente, duracion_existente = ya_existe
                    if duracion_existente is None:
                        conn.execute(
                            "UPDATE rutas SET duracion_min = ? WHERE id = ?",
                            (variante["duracion_min"], ruta_id_existente),
                        )
                    logger.info(
                        "Ruta %s -> %s (%s) ya existe, se omite",
                        par["origen"],
                        par["destino"],
                        variante["variante"],
                    )
                    continue

                cursor = conn.execute(
                    """
                    INSERT INTO rutas (origen, destino, variante, distancia_km, duracion_min, geometry_osrm_polyline)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        par["origen"],
                        par["destino"],
                        variante["variante"],
                        variante["distancia_km"],
                        variante["duracion_min"],
                        variante["geometry_osrm_polyline"],
                    ),
                )
                ruta_id = cursor.lastrowid

                for orden, nombre_via in enumerate(variante["vias"], start=1):
                    conn.execute(
                        "INSERT INTO tramos_carretera (ruta_id, nombre_via, orden) VALUES (?, ?, ?)",
                        (ruta_id, nombre_via, orden),
                    )
                _poblar_provincias(conn, ruta_id, variante["variante"])

                logger.info(
                    "Ruta %s -> %s (%s) creada: %.1f km",
                    par["origen"],
                    par["destino"],
                    variante["variante"],
                    variante["distancia_km"],
                )


if __name__ == "__main__":
    run()
