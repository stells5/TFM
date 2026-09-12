"""Evolución en el tiempo de meteo, incidencias y precio de combustible
para las vías/provincias de una ruta."""
import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (
    capturas_dgt_por_dia,
    cargar_rutas,
    tendencia_incidencias,
    tendencia_meteo,
    tendencia_precios,
    vias_y_provincias,
)

st.set_page_config(page_title="Tendencias", page_icon="📈", layout="wide")
st.title("📈 Tendencias históricas")
st.caption(
    "Evolución de las fuentes que alimentan el índice de riesgo/coste a lo largo "
    "del tiempo, para las vías y provincias de la ruta seleccionada. El histórico "
    "empieza a acumularse desde que arrancó el pipeline."
)

rutas = cargar_rutas()
if rutas.empty:
    st.warning("No hay rutas dadas de alta. Ejecuta `python -m load.rutas`.")
    st.stop()

rutas = rutas.sort_values(["origen", "variante"])
etiquetas = [
    f"{row['origen']} · {row['variante'][:60]}{'…' if len(row['variante']) > 60 else ''}"
    for _, row in rutas.iterrows()
]
idx = st.selectbox("Ruta", range(len(rutas)), format_func=lambda i: etiquetas[i])
ruta_id = int(rutas.iloc[idx]["id"])
vias, provincias = vias_y_provincias(ruta_id)

tab_meteo, tab_incidencias, tab_precios = st.tabs(
    ["🌦️ Meteorología", "🚧 Incidencias", "⛽ Combustible"]
)

with tab_meteo:
    df = tendencia_meteo(tuple(provincias))
    if df.empty:
        st.info("Sin datos meteorológicos para las provincias de esta ruta.")
    else:
        df["fecha"] = pd.to_datetime(df["timestamp_observacion"]).dt.floor("D")
        agg = (
            df.groupby(["fecha", "provincia"])
            .agg(viento=("viento", "mean"), precipitacion=("precipitacion", "sum"))
            .reset_index()
        )
        fig_viento = px.line(
            agg, x="fecha", y="viento", color="provincia",
            labels={"fecha": "", "viento": "Viento medio diario (m/s)"},
            title="Viento medio diario por provincia",
        )
        fig_viento.add_hline(y=10, line_dash="dot", annotation_text="umbral de riesgo (10 m/s)")
        st.plotly_chart(fig_viento, width='stretch')

        fig_lluvia = px.bar(
            agg, x="fecha", y="precipitacion", color="provincia", barmode="group",
            labels={"fecha": "", "precipitacion": "Precipitación diaria (mm)"},
            title="Precipitación diaria por provincia",
        )
        fig_lluvia.add_hline(y=5, line_dash="dot", annotation_text="umbral de riesgo (5 mm)")
        st.plotly_chart(fig_lluvia, width='stretch')

with tab_incidencias:
    df = tendencia_incidencias(tuple(vias), tuple(provincias))
    if df.empty:
        st.info("Sin incidencias registradas en las vías de esta ruta.")
    else:
        df["fecha"] = pd.to_datetime(df["timestamp_captura"]).dt.floor("D")
        incidencias_por_dia = df.groupby("fecha").size().reset_index(name="incidencias")
        # Parto del total de capturas del pipeline de DGT ese día (no solo
        # las capturas en las que esta vía tuvo alguna incidencia): si no,
        # un día sin incidencias en la ruta no contaría ninguna captura y la
        # media saldría inflada en vez de con un 0 real ese día.
        conteo = capturas_dgt_por_dia().merge(incidencias_por_dia, on="fecha", how="left")
        conteo["incidencias"] = conteo["incidencias"].fillna(0)
        conteo["incidencias_por_captura"] = conteo["incidencias"] / conteo["capturas"]

        fig_incidencias = px.line(
            conteo, x="fecha", y="incidencias_por_captura",
            labels={"fecha": "", "incidencias_por_captura": "Incidencias activas (media por captura)"},
            title="Incidencias activas en la ruta a lo largo del tiempo",
        )
        st.plotly_chart(fig_incidencias, width='stretch')

        por_tipo = df["tipo_incidencia"].value_counts().reset_index()
        por_tipo.columns = ["tipo_incidencia", "capturas"]
        fig_tipo = px.bar(
            por_tipo, x="capturas", y="tipo_incidencia", orientation="h",
            labels={"capturas": "Nº de capturas con esta incidencia activa", "tipo_incidencia": ""},
            title="Tipos de incidencia más frecuentes en la ruta",
        )
        st.plotly_chart(fig_tipo, width='stretch')

with tab_precios:
    df = tendencia_precios(tuple(vias), tuple(provincias))
    if df.empty:
        st.info("Sin datos de precios de combustible para esta ruta.")
    else:
        df["fecha"] = pd.to_datetime(df["timestamp_captura"]).dt.floor("D")
        agg = df.groupby("fecha")["precio"].mean().reset_index()
        fig_precio = px.line(
            agg, x="fecha", y="precio",
            labels={"fecha": "", "precio": "Precio medio gasóleo A (€/L)"},
            title="Evolución del precio medio del gasóleo A en la ruta",
        )
        st.plotly_chart(fig_precio, width='stretch')
