"""Transformación de los datos crudos de precios de carburantes."""
from datetime import datetime, timezone

import pandas as pd

# Columnas de la API que nos interesan y el nombre "limpio" que tendrán
# en la tabla `precios_combustible`. Los combustibles no relevantes para
# una flota de transporte (hidrógeno, metanol, GLP, etc.) se descartan.
COLUMNAS_COMBUSTIBLE = {
    "Precio Gasoleo A": "gasoleo_a",
    "Precio Gasoleo Premium": "gasoleo_premium",
    "Precio Gasolina 95 E5": "gasolina_95",
    "Precio Gasolina 98 E5": "gasolina_98",
}


def _a_float(valor: str):
    """Convierte '1,699' -> 1.699. Devuelve None si la estación no vende ese combustible."""
    valor = (valor or "").strip()
    if not valor:
        return None
    return float(valor.replace(",", "."))


def transformar_precios(estaciones: list) -> pd.DataFrame:
    """Convierte la lista de estaciones (formato ancho, crudo de la API) en un
    DataFrame en formato largo: una fila por (estación, tipo de combustible).
    """
    timestamp_captura = datetime.now(timezone.utc).isoformat()
    filas = []
    for estacion in estaciones:
        for columna_api, tipo_combustible in COLUMNAS_COMBUSTIBLE.items():
            precio = _a_float(estacion.get(columna_api))
            if precio is None:
                continue
            filas.append(
                {
                    "provincia": estacion.get("Provincia"),
                    "municipio": estacion.get("Municipio"),
                    # Guardamos la dirección tal cual la da la API (ej. "CARRETERA N-122
                    # KM. 53,5") para poder casar más adelante gasolinera <-> tramo de
                    # carretera de una ruta, buscando el nombre de la vía en el texto.
                    "direccion": estacion.get("Dirección"),
                    "tipo_combustible": tipo_combustible,
                    "precio": precio,
                    "timestamp_captura": timestamp_captura,
                }
            )
    return pd.DataFrame(filas)


if __name__ == "__main__":
    from extract.gasolineras import extraer_precios

    df = transformar_precios(extraer_precios())
    print(df.shape)
    print(df.head())
