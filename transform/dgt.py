"""Transformación de las incidencias de tráfico crudas de la DGT."""
from datetime import datetime, timezone

import pandas as pd


def transformar_incidencias(incidencias: list) -> pd.DataFrame:
    """Convierte la lista de incidencias en crudo en el DataFrame que espera
    la tabla `incidencias_trafico`.
    """
    timestamp_captura = datetime.now(timezone.utc).isoformat()
    filas = [
        {
            "situacion_id": inc["situacion_id"],
            "via": inc["road_name"],
            "provincia": inc["province"],
            "municipio": inc["municipality"],
            "tipo_incidencia": inc["cause_type"],
            "severidad": inc["severity"],
            "km": float(inc["km"]) if inc["km"] is not None else None,
            "timestamp_inicio": inc["start_time"],
            "timestamp_captura": timestamp_captura,
        }
        for inc in incidencias
    ]
    return pd.DataFrame(filas)


if __name__ == "__main__":
    from extract.dgt import extraer_incidencias

    df = transformar_incidencias(extraer_incidencias())
    print(df.shape)
    print(df.head())
