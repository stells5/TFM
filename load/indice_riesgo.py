"""Calcula y guarda el índice de riesgo/coste de cada ruta.

A diferencia de gasolineras/DGT/AEMET, este pipeline no llama a ninguna API:
combina lo que ya hay en la base de datos (incidencias, meteo, precios) para
cada ruta. Se debe ejecutar después de las otras cuatro, y se reprograma cada
vez que cambian el tráfico o el tiempo (ver periodicidad en run_pipeline.py).
"""
from datetime import datetime, timezone

from db.database import get_connection, init_db
from logging_config import get_logger
from transform.indice_riesgo import (
    calcular_meteo_max,
    calcular_riesgo_meteo,
    calcular_riesgo_trafico,
    calcular_score_coste,
    encontrar_gasolinera_mas_barata,
    incidencia_mas_grave,
    provincias_de_ruta,
    vias_de_ruta,
)

PIPELINE_NAME = "indice_riesgo"
logger = get_logger(PIPELINE_NAME)


def _registrar_ejecucion(inicio, fin, status, filas, error_msg=None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO log_ejecuciones
                (pipeline_name, timestamp_inicio, timestamp_fin, status, filas_procesadas, error_msg)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (PIPELINE_NAME, inicio, fin, status, filas, error_msg),
        )


def run() -> None:
    init_db()
    inicio = datetime.now(timezone.utc).isoformat()
    logger.info("Inicio del cálculo del índice de riesgo/coste")
    try:
        timestamp_calculo = datetime.now(timezone.utc).isoformat()
        n_calculadas = 0
        with get_connection() as conn:
            rutas = conn.execute(
                "SELECT id, origen, destino, variante, distancia_km FROM rutas"
            ).fetchall()
            for ruta_id, origen, destino, variante, distancia_km in rutas:
                vias = vias_de_ruta(conn, ruta_id)
                provincias = provincias_de_ruta(conn, ruta_id)

                riesgo_trafico = calcular_riesgo_trafico(conn, vias, provincias)
                riesgo_meteo = calcular_riesgo_meteo(conn, provincias)
                # Riesgo por cada 100 km, para poder comparar rutas de
                # longitud muy distinta (si no, las rutas más largas
                # acumulan más incidencias solo por tener más km/vías).
                riesgo_absoluto = riesgo_trafico + riesgo_meteo
                score_riesgo = riesgo_absoluto / (distancia_km / 100) if distancia_km else riesgo_absoluto

                score_coste = calcular_score_coste(conn, vias, provincias)
                gasolinera_barata, precio_barato = encontrar_gasolinera_mas_barata(
                    conn, vias, provincias
                )
                viento_max, viento_max_provincia, lluvia_max, lluvia_max_provincia = calcular_meteo_max(
                    conn, provincias
                )
                incidencia_tipo, incidencia_via, incidencia_km = incidencia_mas_grave(
                    conn, vias, provincias
                )

                conn.execute(
                    """
                    INSERT INTO indice_riesgo_ruta
                        (ruta_id, score_riesgo, score_coste, gasolinera_mas_barata, precio_mas_barato,
                         viento_max, viento_max_provincia, lluvia_max, lluvia_max_provincia,
                         incidencia_mas_grave_tipo, incidencia_mas_grave_via, incidencia_mas_grave_km,
                         timestamp_calculo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ruta_id, score_riesgo, score_coste, gasolinera_barata, precio_barato,
                        viento_max, viento_max_provincia, lluvia_max, lluvia_max_provincia,
                        incidencia_tipo, incidencia_via, incidencia_km,
                        timestamp_calculo,
                    ),
                )
                n_calculadas += 1
                logger.info(
                    "Ruta %s -> %s (%s): score_riesgo=%.1f/100km (absoluto=%.1f: trafico=%.1f, meteo=%.1f) "
                    "score_coste=%s mas_barata=%s (%s)",
                    origen,
                    destino,
                    variante,
                    score_riesgo,
                    riesgo_absoluto,
                    riesgo_trafico,
                    riesgo_meteo,
                    f"{score_coste:.3f}" if score_coste is not None else "sin datos",
                    gasolinera_barata or "sin datos",
                    f"{precio_barato:.3f}" if precio_barato is not None else "-",
                )

        fin = datetime.now(timezone.utc).isoformat()
        _registrar_ejecucion(inicio, fin, "OK", n_calculadas)
        logger.info("Cálculo completado correctamente (%d rutas)", n_calculadas)
    except Exception as exc:
        fin = datetime.now(timezone.utc).isoformat()
        logger.exception("Fallo en el cálculo del índice de riesgo")
        _registrar_ejecucion(inicio, fin, "ERROR", 0, str(exc))
        raise


if __name__ == "__main__":
    run()
