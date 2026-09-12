# Pipeline de riesgo y coste de rutas

Pipeline ETL que calcula un índice de riesgo y coste para distintas rutas por carretera en España, combinando incidencias de tráfico, meteorología, precios de combustible y datos de rutas reales, más un panel interactivo para explotar los resultados. Trabajo Fin de Máster — UCM, Big Data, Data Science e Inteligencia Artificial.

## Qué hace

Para cada ruta del dataset (origen → Barcelona, con sus variantes/caminos alternativos), el pipeline:

1. Descarga y guarda datos en bruto de 4 fuentes públicas (ver abajo).
2. Cruza esos datos con las vías y provincias que atraviesa cada ruta.
3. Calcula un **score de riesgo** (incidencias de tráfico ponderadas por tipo/severidad + alertas meteorológicas) normalizado por cada 100 km, y un **score de coste** (precio medio de combustible en las gasolineras de la ruta), además de la gasolinera más barata, el viento/lluvia máximos (y en qué provincia) y la incidencia más grave (tipo, vía, kilómetro).
4. Deja los resultados en tablas SQLite listas para consultar o explotar (BI, modelización, etc.) — incluido un panel interactivo en Streamlit ya montado sobre esas tablas.

## Fuentes de datos

| Fuente | Qué aporta | Periodicidad |
|---|---|---|
| [DGT (NAP)](https://nap.dgt.es) | Incidencias de tráfico activas (accidentes, obras, retenciones...) con vía, provincia, punto kilométrico y coordenadas | cada 20 min |
| [AEMET OpenData](https://opendata.aemet.es) | Observaciones meteorológicas (viento, precipitación) por estación | cada 120 min |
| [Geoportal de Gasolineras (MITECO)](https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes) | Precios de combustible por gasolinera y provincia (27 provincias cubiertas, las que atraviesan las 10 rutas del dataset) | 1 vez al día |
| [OSRM](http://router.project-osrm.org) | Rutas reales entre origen y destino: distancia, duración, geometría y vías que atraviesa | solo al añadir una ruta nueva (no periódico) |

> **Nota:** OSRM se consulta contra el servidor demo público (`router.project-osrm.org`), pensado solo para pruebas puntuales, no para uso intensivo en producción. Como `load/rutas.py` no se ejecuta de forma periódica (solo al dar de alta una ruta nueva), el impacto es bajo, pero para un despliegue real convendría un servidor OSRM propio o un servicio de routing comercial.

## Instalación

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # y rellena tu AEMET_API_KEY (gratuita, ver https://opendata.aemet.es/centrodedescargas/altaUsuario)
```

`db/pipeline.db` se incluye tal cual en el repositorio, con datos reales ya descargados — no hace falta ejecutar el pipeline para ver resultados, ni siquiera tener una `AEMET_API_KEY` propia. Solo hace falta si quieres refrescar los datos tú mismo.

## Uso

```bash
# Ver los resultados ya calculados (funciona directamente, sin más pasos)
python ver_indice.py
streamlit run streamlit_app/Inicio.py

# Para refrescar los datos: da de alta las rutas (una sola vez, o al añadir un origen nuevo)
python -m load.rutas

# Corre el pipeline completo en bucle (descarga periódica + recálculo del índice)
python run_pipeline.py

# O ejecuta una fuente suelta
python -m load.dgt
python -m load.aemet
python -m load.gasolineras
python -m load.indice_riesgo
```

La periodicidad de cada fuente se configura en `.env` (`DGT_INTERVAL_MINUTES`, `AEMET_INTERVAL_MINUTES`, `GASOLINERAS_HORA_DIARIA`), ver `.env.example`.

## Panel interactivo (Streamlit)

Tres páginas, todas leyendo directamente `db/pipeline.db` (sin servidor propio):

- **Inicio** — el usuario elige su ciudad de origen y ve, en grande, la ruta más corta y la de menos riesgo hacia Barcelona, con nivel de riesgo (Bajo/Medio/Alto) y la variante más barata en combustible.
- **Mapa** — geometría real de cada variante sobre un mapa, con las incidencias de tráfico activas superpuestas. Aquí el cruce ruta↔incidencia ya no es por texto: se filtra por **distancia real** (fórmula de Haversine) entre la coordenada de la incidencia y la geometría de la ruta, más preciso que el criterio de vía/provincia que usa el cálculo del índice.
- **Tendencias** — evolución histórica de meteo, incidencias y precio de combustible para la ruta seleccionada, usando todo el histórico acumulado (no solo la última captura).

## Estructura del proyecto

```
extract/       Descarga datos en crudo de cada fuente (llamadas a las APIs)
transform/     Limpia y transforma cada fuente al formato de la tabla destino
load/          Orquesta extract+transform+carga en SQLite, con logging y manejo de errores
db/            Esquema (schema.sql) y conexión a la base de datos SQLite
streamlit_app/ Panel interactivo (Inicio, Mapa, Tendencias) sobre los resultados del pipeline
queries/       Consultas SQL guardadas para reutilizar desde un cliente SQL (ej. SQLTools)
run_pipeline.py   Orquestador: programa la ejecución periódica de las 4 fuentes
ver_indice.py     Muestra por pantalla el último índice calculado por ruta
```

Arquitectura en capas ETL (extract → transform → load), con una base de datos SQLite (`db/pipeline.db`) dividida en:
- **Tablas de dimensión** (estáticas): `rutas`, `tramos_carretera`, `ruta_provincias`.
- **Tablas de hechos** (alimentadas por ETL periódica): `incidencias_trafico` (incluye lat/lon de cada incidencia), `condiciones_meteo`, `precios_combustible`, `indice_riesgo_ruta`.
- **Tabla de monitorización**: `log_ejecuciones` (registra cada ejecución, éxito/error, filas procesadas).

## Dataset

10 rutas (5 orígenes × 2 variantes cada uno) hacia Barcelona, elegidas para cubrir distintas distancias, climas y regiones de España: Zaragoza, Madrid, Bilbao, Sevilla y A Coruña.

## Limitaciones conocidas

- El cálculo del índice de riesgo/coste cruza rutas e incidencias/meteo/precios por coincidencia de texto (nombre de vía, provincia), no por coordenadas — es la aproximación más razonable con los datos disponibles, pero puede fallar en carreteras muy largas que se repiten en varias zonas del país. La vista de Mapa del panel interactivo sí usa las coordenadas reales para este cruce; llevar ese mismo criterio al cálculo del índice queda como mejora pendiente.
- El feed de la DGT no incluye incidencias de Cataluña ni País Vasco (las gestionan sus propias policías autonómicas, fuera del NAP estatal).
- `condiciones_meteo` e `incidencias_trafico` acumulan histórico en cada ejecución (no se sobrescriben); las consultas de resultados filtran a la captura más reciente, salvo la página de Tendencias, que usa el histórico completo a propósito.
