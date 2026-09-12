"""Página de inicio: el transportista elige su origen y ve, en grande, cuál
es la ruta más corta y cuál la de menos riesgo hacia el almacén de Barcelona."""
import streamlit as st

from utils import cargar_ranking, color_riesgo_css, nivel_riesgo

st.set_page_config(page_title="Rutas a Barcelona", page_icon="🚚", layout="wide")

st.title("🚚 ¿Qué ruta cojo hasta el almacén de Barcelona?")
st.caption(
    "Riesgo = incidencias de tráfico (DGT) + alertas de lluvia/viento (AEMET) en el "
    "camino, normalizado por cada 100 km para poder comparar rutas de distinta longitud."
)

df = cargar_ranking()

if df.empty:
    st.warning(
        "Todavía no hay ningún cálculo del índice en la base de datos. "
        "Ejecuta `python -m load.rutas` y luego `python run_pipeline.py`."
    )
    st.stop()

q33, q66 = df["score_riesgo"].quantile([0.33, 0.66])
riesgo_min, riesgo_max = float(df["score_riesgo"].min()), float(df["score_riesgo"].max())

origenes = sorted(df["origen"].unique())
origen_sel = st.selectbox("📍 Tu punto de salida", origenes)

vista = df[df["origen"] == origen_sel].copy()
st.caption(f"Última actualización del índice: {vista['timestamp_calculo'].max()}")


def tarjeta(titulo: str, ruta, destacar_color: str | None = None) -> str:
    color = destacar_color or "var(--secondary-background-color, #262730)"
    return f"""
    <div style="background:{color}; border-radius:14px; padding:22px 26px; color:white; height:100%;">
        <div style="font-size:13px; letter-spacing:.04em; opacity:.9; text-transform:uppercase;">{titulo}</div>
        <div style="font-size:22px; font-weight:700; margin-top:6px;">{ruta['origen']} → {ruta['destino']}</div>
        <div style="font-size:14px; opacity:.9; margin-top:2px;">{ruta['variante']}</div>
        <div style="display:flex; gap:28px; margin-top:16px;">
            <div>
                <div style="font-size:30px; font-weight:800;">{ruta['distancia_km']:.0f} km</div>
                <div style="font-size:12px; opacity:.85;">{ruta['duracion_min']:.0f} min sin incidencias</div>
            </div>
            <div>
                <div style="font-size:30px; font-weight:800;">{ruta['score_riesgo']:.1f}</div>
                <div style="font-size:12px; opacity:.85;">pts riesgo /100km — {nivel_riesgo(ruta['score_riesgo'], q33, q66)}</div>
            </div>
        </div>
    </div>
    """


mas_corta = vista.loc[vista["distancia_km"].idxmin()]
mas_segura = vista.loc[vista["score_riesgo"].idxmin()]
color_segura = color_riesgo_css(mas_segura["score_riesgo"], riesgo_min, riesgo_max)

if mas_corta["ruta_id"] == mas_segura["ruta_id"]:
    st.markdown(
        tarjeta("⭐ Ruta recomendada — la más corta y la de menos riesgo", mas_corta, color_segura),
        unsafe_allow_html=True,
    )
else:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(tarjeta("🏁 Ruta más corta", mas_corta, "#2b5fa8"), unsafe_allow_html=True)
    with col2:
        st.markdown(tarjeta("🛡️ Ruta con menos riesgo", mas_segura, color_segura), unsafe_allow_html=True)

st.write("")

if vista["score_coste"].notna().any():
    mas_barata = vista.loc[vista["score_coste"].idxmin()]
    st.caption(
        f"⛽ La variante más barata en combustible es **{mas_barata['variante'][:60]}** "
        f"({mas_barata['score_coste']:.3f} €/L de media, más barata en "
        f"{mas_barata['gasolinera_mas_barata'] or 'sin datos'})."
    )

st.divider()
st.subheader(f"Todas las variantes desde {origen_sel}")

tabla = vista[
    [
        "variante", "distancia_km", "duracion_min", "score_riesgo", "score_coste",
        "incidencia_mas_grave_tipo", "viento_max", "lluvia_max",
    ]
].sort_values("score_riesgo")

st.dataframe(
    tabla,
    width="stretch",
    hide_index=True,
    column_config={
        "variante": "Variante (vías)",
        "distancia_km": st.column_config.NumberColumn("Distancia (km)", format="%.1f"),
        "duracion_min": st.column_config.NumberColumn("Duración (min)", format="%.0f"),
        "score_riesgo": st.column_config.ProgressColumn(
            "Riesgo (pts/100km)", format="%.1f", min_value=0, max_value=max(riesgo_max, 1.0),
        ),
        "score_coste": st.column_config.NumberColumn("Coste (€/L)", format="%.3f"),
        "viento_max": st.column_config.NumberColumn("Viento máx. (m/s)", format="%.1f"),
        "lluvia_max": st.column_config.NumberColumn("Lluvia máx. (mm)", format="%.1f"),
        "incidencia_mas_grave_tipo": "Incidencia más grave",
    },
)

with st.expander("¿Cómo se calcula el riesgo y el coste?"):
    st.markdown(
        """
- **Riesgo**: suma ponderada de incidencias de tráfico activas (DGT) en las
  vías/provincias de la ruta + puntos por lluvia (>5 mm) o viento (>10 m/s)
  fuerte en las provincias que atraviesa, normalizada por cada 100 km.
- **Nivel Bajo/Medio/Alto**: se calcula comparando el riesgo de esta ruta
  contra el de todas las rutas del sistema (terciles).
- **Coste**: precio medio del gasóleo A en las gasolineras situadas en las
  vías/provincias de la ruta.
- El cruce ruta↔incidencia/meteo/precio se hace por coincidencia de texto
  (nombre de vía, provincia), no por coordenadas exactas.
- La DGT no informa incidencias de Cataluña ni País Vasco (gestionadas por
  sus policías autonómicas).
        """
    )
