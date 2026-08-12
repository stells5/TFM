"""Muestra por pantalla el último índice de riesgo/coste calculado para cada ruta."""
import pandas as pd

from db.database import get_connection

QUERY = """
SELECT r.origen, r.destino, r.variante,
       r.distancia_km AS "distancia_km (km)",
       r.duracion_min AS "duracion_min (min)",
       i.score_coste AS "score_coste (€/L)",
       i.gasolinera_mas_barata,
       i.precio_mas_barato AS "precio_mas_barato (€/L)",
       i.viento_max AS "viento_max (m/s)",
       i.viento_max_provincia,
       i.lluvia_max AS "lluvia_max (mm)",
       CASE WHEN i.lluvia_max IS NULL OR i.lluvia_max = 0 THEN '-' ELSE i.lluvia_max_provincia END AS lluvia_max_provincia,
       i.incidencia_mas_grave_tipo,
       i.incidencia_mas_grave_via,
       i.incidencia_mas_grave_km AS "incidencia_mas_grave_km (km)",
       i.score_riesgo AS "score_riesgo (pts/100km)"
FROM indice_riesgo_ruta i
JOIN rutas r ON r.id = i.ruta_id
WHERE i.timestamp_calculo = (
    SELECT MAX(timestamp_calculo) FROM indice_riesgo_ruta WHERE ruta_id = i.ruta_id
)
ORDER BY r.origen, r.destino, i.score_riesgo
"""

if __name__ == "__main__":
    with get_connection() as conn:
        df = pd.read_sql(QUERY, conn)
    pd.set_option("display.width", 160)
    pd.set_option("display.max_colwidth", 60)
    print(df.to_string(index=False))
