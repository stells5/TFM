-- Último índice de riesgo/coste calculado por ruta (una fila por ruta).
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
ORDER BY r.origen, r.destino, i.score_riesgo;
