"""Mapa con todas las rutas de la red (o las de un origen concreto),
coloreadas por riesgo, con sus características generales y detalle de
incidencias/gasolineras de la variante que se elija."""
import pandas as pd
import pydeck as pdk
import streamlit as st

from utils import (
    cargar_gasolineras_ruta,
    cargar_incidencias_activas,
    cargar_ranking,
    cargar_rutas,
    color_riesgo,
    decode_polyline,
    estilo_incidencia,
    filtrar_por_proximidad,
    vias_y_provincias,
)

UMBRAL_PROXIMIDAD_KM = 2.0

st.set_page_config(page_title="Mapa de rutas", page_icon="🗺️", layout="wide")
st.title("🗺️ Mapa de la red de rutas")

rutas = cargar_rutas()
ranking = cargar_ranking()

if rutas.empty:
    st.warning("No hay rutas dadas de alta. Ejecuta `python -m load.rutas`.")
    st.stop()

rutas = rutas.merge(
    ranking[["ruta_id", "score_riesgo", "score_coste"]],
    left_on="id", right_on="ruta_id", how="left",
)

origenes = sorted(rutas["origen"].unique())
origen_sel = st.selectbox("Filtrar por origen", ["Todos"] + origenes)
variantes = rutas if origen_sel == "Todos" else rutas[rutas["origen"] == origen_sel]
variantes = variantes.reset_index(drop=True)

st.caption(
    "Color de cada ruta = riesgo relativo frente al resto de la red "
    "(🟢 verde = más segura, 🔴 rojo = más riesgo). Los puntos son incidencias "
    "de tráfico activas a menos de "
    f"{UMBRAL_PROXIMIDAD_KM:.0f} km de la línea real de estas rutas — más "
    "grandes y rojos cuanto más graves (accidentes, obstrucciones...)."
)

min_riesgo = float(rutas["score_riesgo"].min())
max_riesgo = float(rutas["score_riesgo"].max())

paths = []
coords_por_ruta = {}
for _, row in variantes.iterrows():
    coords = decode_polyline(row["geometry_osrm_polyline"])
    coords_por_ruta[int(row["id"])] = coords
    riesgo_txt = f"{row['score_riesgo']:.1f} pts/100km" if pd.notna(row["score_riesgo"]) else "sin datos"
    paths.append(
        {
            "path": [[lon, lat] for lat, lon in coords],
            "color": color_riesgo(row["score_riesgo"], min_riesgo, max_riesgo),
            "tooltip": f"{row['origen']} → {row['destino']}\n{row['variante']}\n{row['distancia_km']:.0f} km · riesgo {riesgo_txt}",
        }
    )

path_df = pd.DataFrame(paths)
todas_coords = [pt for p in path_df["path"] for pt in p]
lon0 = sum(c[0] for c in todas_coords) / len(todas_coords)
lat0 = sum(c[1] for c in todas_coords) / len(todas_coords)
coords_corredor = [coord for lista in coords_por_ruta.values() for coord in lista]

capa_rutas = pdk.Layer(
    "PathLayer",
    data=path_df,
    get_path="path",
    get_color="color",
    width_min_pixels=3,
    pickable=True,
)

# Incidencias activas en las vías/provincias de todas las rutas actualmente
# mostradas (mismo criterio de cruce que usa el índice de riesgo).
vias_todas, provincias_todas = set(), set()
for ruta_id_it in variantes["id"]:
    v, p = vias_y_provincias(int(ruta_id_it))
    vias_todas.update(v)
    provincias_todas.update(p)

incidencias_mapa = cargar_incidencias_activas(tuple(sorted(vias_todas)), tuple(sorted(provincias_todas)))
incidencias_mapa = incidencias_mapa.dropna(subset=["lat", "lon"]) if not incidencias_mapa.empty else incidencias_mapa
# El cruce por vía/provincia es una preselección gruesa (una vía larga como
# la A-2 puede tener incidencias a decenas de km del tramo real de la ruta);
# me quedo solo con las que caen cerca de la geometría real de la ruta.
incidencias_mapa = filtrar_por_proximidad(incidencias_mapa, coords_corredor, UMBRAL_PROXIMIDAD_KM)

capas = [capa_rutas]
if not incidencias_mapa.empty:
    puntos = []
    for _, row in incidencias_mapa.iterrows():
        radio, color = estilo_incidencia(row["tipo_incidencia"])
        km_txt = f"km {row['km']:.0f}" if pd.notna(row["km"]) else "km ?"
        puntos.append(
            {
                "lat": row["lat"],
                "lon": row["lon"],
                "radio": radio,
                "color": color,
                "tooltip": f"🚧 {row['tipo_incidencia']}\n{row['via']} · {row['municipio']} ({km_txt})\n{row['provincia']}",
            }
        )
    puntos_df = pd.DataFrame(puntos)
    capas.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=puntos_df,
            get_position=["lon", "lat"],
            get_radius="radio",
            get_fill_color="color",
            stroked=True,
            get_line_color=[100, 20, 20],
            line_width_min_pixels=1,
            pickable=True,
        )
    )
    st.caption(f"🚧 {len(puntos_df)} incidencia(s) activa(s) mostrada(s) en estas rutas.")

st.pydeck_chart(
    pdk.Deck(
        layers=capas,
        initial_view_state=pdk.ViewState(latitude=lat0, longitude=lon0, zoom=5.3 if origen_sel == "Todos" else 6),
        tooltip={"text": "{tooltip}"},
    ),
    width="stretch",
)

st.subheader("Características generales" + ("" if origen_sel == "Todos" else f" — desde {origen_sel}"))
tabla_general = variantes[
    ["origen", "destino", "variante", "distancia_km", "duracion_min", "score_riesgo", "score_coste"]
].sort_values(["origen", "score_riesgo"])
st.dataframe(
    tabla_general,
    width="stretch",
    hide_index=True,
    column_config={
        "distancia_km": st.column_config.NumberColumn("Distancia (km)", format="%.1f"),
        "duracion_min": st.column_config.NumberColumn("Duración (min)", format="%.0f"),
        "score_riesgo": st.column_config.ProgressColumn(
            "Riesgo (pts/100km)", format="%.1f", min_value=0, max_value=max(max_riesgo, 1.0),
        ),
        "score_coste": st.column_config.NumberColumn("Coste (€/L)", format="%.3f"),
    },
)

st.divider()
st.subheader("Detalle de una variante")
etiquetas = [
    f"{row['origen']} · {row['variante'][:60]}{'…' if len(row['variante']) > 60 else ''} ({row['distancia_km']:.0f} km)"
    for _, row in variantes.iterrows()
]
idx = st.selectbox("Variante", range(len(variantes)), format_func=lambda i: etiquetas[i])
ruta_id = int(variantes.loc[idx, "id"])
vias, provincias = vias_y_provincias(ruta_id)

col_inc, col_gas = st.columns(2)

with col_inc:
    st.markdown("**🚧 Incidencias activas en la ruta**")
    incidencias = cargar_incidencias_activas(tuple(vias), tuple(provincias))
    incidencias = incidencias.dropna(subset=["lat", "lon"])
    incidencias = filtrar_por_proximidad(incidencias, coords_por_ruta[ruta_id], UMBRAL_PROXIMIDAD_KM)
    if incidencias.empty:
        st.info("Sin incidencias activas en las vías de esta ruta ahora mismo.")
    else:
        st.dataframe(
            incidencias.drop(columns=["lat", "lon"]).sort_values("provincia"),
            width="stretch",
            hide_index=True,
        )

with col_gas:
    st.markdown("**⛽ Gasolineras de la ruta (gasóleo A)**")
    gasolineras = cargar_gasolineras_ruta(tuple(vias), tuple(provincias))
    if gasolineras.empty:
        st.info("Sin gasolineras localizadas en las vías de esta ruta.")
    else:
        st.dataframe(gasolineras, width="stretch", hide_index=True)
