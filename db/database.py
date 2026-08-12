"""Conexión y utilidades comunes de la base de datos SQLite del pipeline."""
import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "pipeline.db"
SCHEMA_PATH = DB_DIR / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Crea las tablas que falten a partir de schema.sql (no destruye datos existentes)."""
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _migrar_columnas_nuevas(conn)


COLUMNAS_NUEVAS_POR_TABLA = {
    "rutas": {
        "duracion_min": "REAL",
    },
    "incidencias_trafico": {
        "km": "REAL",
    },
    "indice_riesgo_ruta": {
        "viento_max": "REAL",
        "viento_max_provincia": "TEXT",
        "lluvia_max": "REAL",
        "lluvia_max_provincia": "TEXT",
        "incidencia_mas_grave_tipo": "TEXT",
        "incidencia_mas_grave_via": "TEXT",
        "incidencia_mas_grave_km": "REAL",
    },
}


def _migrar_columnas_nuevas(conn: sqlite3.Connection) -> None:
    """Añade columnas nuevas a tablas ya existentes (CREATE TABLE IF NOT EXISTS
    no las añade si la tabla ya se creó con un esquema antiguo)."""
    for tabla, columnas_nuevas in COLUMNAS_NUEVAS_POR_TABLA.items():
        columnas_existentes = {
            fila[1] for fila in conn.execute(f"PRAGMA table_info({tabla})")
        }
        for columna, tipo in columnas_nuevas.items():
            if columna not in columnas_existentes:
                conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
