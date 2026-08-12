-- Esquema de la base de datos del pipeline de riesgo/eficiencia de rutas.

-- ---------- Tablas de dimensión (datos estáticos) ----------

-- Cada fila es una variante (camino alternativo) de un trayecto origen-destino,
-- ej. Zaragoza-Barcelona "vía AP-2" y Zaragoza-Barcelona "vía A-23" son dos filas.
CREATE TABLE IF NOT EXISTS rutas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origen TEXT NOT NULL,
    destino TEXT NOT NULL,
    variante TEXT NOT NULL,
    distancia_km REAL,
    duracion_min REAL,
    geometry_osrm_polyline TEXT
);

CREATE TABLE IF NOT EXISTS tramos_carretera (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruta_id INTEGER NOT NULL,
    nombre_via TEXT NOT NULL,
    orden INTEGER NOT NULL,
    FOREIGN KEY (ruta_id) REFERENCES rutas (id)
);

-- Provincias que cruza cada ruta (definidas a mano en load/rutas.py). Se
-- usan para afinar el cruce con incidencias_trafico/precios_combustible:
-- exigir vía + provincia evita falsos positivos en carreteras muy largas
-- que pasan por medio país (ej. la A-7).
CREATE TABLE IF NOT EXISTS ruta_provincias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruta_id INTEGER NOT NULL,
    provincia TEXT NOT NULL,
    FOREIGN KEY (ruta_id) REFERENCES rutas (id)
);

-- ---------- Tablas de hechos (alimentadas por ETL periódica) ----------

-- Guardamos la vía (ej. "A-2") tal cual la da la DGT, en vez de un tramo_id
-- fijo: una misma vía puede pertenecer a varias rutas/variantes, así que el
-- cruce incidencia <-> ruta se hace por texto en el cálculo del índice
-- (mismo criterio que en precios_combustible.direccion).
CREATE TABLE IF NOT EXISTS incidencias_trafico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    situacion_id TEXT NOT NULL,
    via TEXT,
    provincia TEXT,
    municipio TEXT,
    tipo_incidencia TEXT,
    severidad TEXT,
    km REAL,
    timestamp_inicio TEXT,
    timestamp_captura TEXT NOT NULL,
    fuente TEXT NOT NULL DEFAULT 'DGT'
);

-- Una estación puede aparecer varias veces (una fila por lectura horaria);
-- timestamp_observacion es el momento real de la medición ("fint" en AEMET),
-- distinto de timestamp_captura (cuándo la descargamos nosotros).
CREATE TABLE IF NOT EXISTS condiciones_meteo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zona_aemet TEXT NOT NULL,
    temperatura REAL,
    precipitacion REAL,
    viento REAL,
    alerta TEXT,
    timestamp_observacion TEXT,
    timestamp_captura TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS precios_combustible (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provincia TEXT NOT NULL,
    municipio TEXT,
    direccion TEXT,
    tipo_combustible TEXT NOT NULL,
    precio REAL NOT NULL,
    timestamp_captura TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS indice_riesgo_ruta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruta_id INTEGER NOT NULL,
    score_riesgo REAL,
    score_coste REAL,
    gasolinera_mas_barata TEXT,
    precio_mas_barato REAL,
    viento_max REAL,
    viento_max_provincia TEXT,
    lluvia_max REAL,
    lluvia_max_provincia TEXT,
    incidencia_mas_grave_tipo TEXT,
    incidencia_mas_grave_via TEXT,
    incidencia_mas_grave_km REAL,
    timestamp_calculo TEXT NOT NULL,
    FOREIGN KEY (ruta_id) REFERENCES rutas (id)
);

-- ---------- Tabla de monitorización ----------

CREATE TABLE IF NOT EXISTS log_ejecuciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_name TEXT NOT NULL,
    timestamp_inicio TEXT NOT NULL,
    timestamp_fin TEXT,
    status TEXT NOT NULL,
    filas_procesadas INTEGER,
    error_msg TEXT
);
