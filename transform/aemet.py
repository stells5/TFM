"""Transformación de las observaciones meteorológicas crudas de AEMET."""
from datetime import datetime, timezone

import pandas as pd


def transformar_observaciones(observaciones: list) -> pd.DataFrame:
    """Convierte la lista de observaciones en crudo en el DataFrame que
    espera la tabla `condiciones_meteo`.

    Campos de la API: "ubi" (nombre/ubicación de la estación), "ta"
    (temperatura actual, ºC), "prec" (precipitación acumulada, mm),
    "vv" (velocidad del viento, m/s).
    """
    timestamp_captura = datetime.now(timezone.utc).isoformat()
    filas = [
        {
            "zona_aemet": obs.get("ubi"),
            "temperatura": obs.get("ta"),
            "precipitacion": obs.get("prec"),
            "viento": obs.get("vv"),
            "alerta": None,
            "timestamp_observacion": obs.get("fint"),
            "timestamp_captura": timestamp_captura,
        }
        for obs in observaciones
    ]
    return pd.DataFrame(filas)


if __name__ == "__main__":
    from extract.aemet import extraer_observaciones

    df = transformar_observaciones(extraer_observaciones())
    print(df.shape)
    print(df.head())
