# Mapify

Mapify is a Python library for exploring Peruvian travel destinations through interactive, linked visualisations. It combines geospatial analytics, machine learning recommendations, dashboards, and seasonal data exploration to help users discover new places with confidence.

---

## Overview

Mapify provides:

- Interactive **city-level Peruvian data** visualised geospatially.
- A **machine learning recommendation engine** to suggest similar destinations.
- Fully **linked visualisations**: clicking one graph highlights relevant elements on the others.
- Dashboards covering tourism similarity, transport access, crime trends, and temperature seasonality.

You can run Mapify in **Google Colab** or in any Python environment (Jupyter, VSCode, local machine).

---

## How to use
You can run the code directly from Google Colab, or from another Python environment. The examples below show how to run the dashboards in Google Colab. 

### 1. First, you need to place the files in the correct directory. The correct file structure is:

```
mapify/
├── models/
│   ├── knn.joblib
│   ├── recursos.parquet
│   └── tfidf.joblib
├── data/
│   ├── acceso_capital_departamento_transportes_SI_NO
│   ├── ALL_REGIONS_2024_daily_temperature.csv
│   ├── CO2
│   ├── denuncias_2024_por_mes_wide
│   └── recursos_mincetur_con_region_geografica  
└── our_library_mvp-8.0.0-py3-none-any.whl
```

It is important that the machine-learning model files are placed inside the _models_ folder.

### 2. Basic code

```
!python3 -m pip install --force-reinstall our_library_mvp-6.1.0-py3-none-any.whl
!pip install --upgrade "scikit-learn==1.7.2"
```

```
from our_library import (
    enable_colab_bridge,
    start_server,
    show_turismo_dashboard_from_model,
    show_transport_access,
    show_crime_monthly_dashboard,
    show_temperature_sunflower,
)

enable_colab_bridge()
start_server()
```

### 3. Change
#### Dashboard
```
show_turismo_dashboard_from_model(
    model_dir="/content/models",
    modo="code",
    valor="11996",   # most important
    topk=10,         # number of recommendations
    alpha=0.8,
    geo_km=40,       # radius in kilometers
    rg_mode="bonus",
)
```
The parameters to adjust are:
* valor — the ID of the location of interest (from `recursos.parquet`)
* topk — number of recommended similar locations
* geo_km — radius in kilometers around the initial point of interest

_Graph_  
This map can be used to explore similarities between the selected location and other destinations. A machine-learning model is used to generate the recommendations. These recommendations are based on geographic distance and attribute similarity.  
The user can interact with this visualisation, by clicking on one of them the other visualisations in the dashboard will light up accordingly. The strength of the relation is represented by the line tickness. 

_Ranking_  
This visualisation shows the ranking of the recommended locations. The highest-ranked one is the most similar to the initial point of interest. It is based on the ML-scores.  
The first listed, is the most similar city. 

_Geographical map_  
This visualisation displays the similar locations on a map. When selecting points on the map, those points will also be highlighted in the ranking and the other graphs.

_Selection_  
Locations selected in any visualisation will appear in the _Selection_ view. This part of the dashboard contains links to more information about these locations.

#### Complementary information
```
show_transport_access(
    csv_path="/content/acceso_capital_departamento_transportes_SI_NO.csv",
    highlight_region="Cusco",
)
```

This graph visualises how different locations can be accessed, using Lima as the starting point. A dot indicates that a particular transport mode is suitable for that location. Clicking a dot reveals more detailed information.  
Starting point = Lima. Clicking on one of the nodes will give more textual info. 

```
show_crime_monthly_dashboard(
    csv_path="/content/denuncias_2024_por_mes_wide.csv",
    region="PUNO",
)
```

This graph shows the number of police reports per month for the selected department. The connected points show the trend over time.  
The user can collect the regio of interest. 

```
show_temperature_sunflower(
    csv_path="/content/ALL_REGIONS_2024_daily_temperature.csv",
    region="Puno",
    date_col="time",
    region_col="REGION",
    tmax_col="temperature_2m_max (°C)",
    tmin_col="temperature_2m_min (°C)",
)
```

A sunflower visualisation displays seasonal temperature data of the past year. This helps travellers choose the optimal month to visit their destination.  
Users can click through cities, find similar locations, and explore yearly patterns in crime data and weather.  
Getting the daily data, is possible by clicking on one of the months. The user can decide what month it's best to travel.  

### Closing remarks
Mapify helps you discover new places with confidence. Try the dashboards, interact with the visualisations, and start finding destinations that match your travel style! Mapify allows for intuitive interaction to find a travel destination on multiple levels! It alows for clicking, hovering, selecting, filtering, and comparing (over time).  

If you have feedback, ideas, or want to contribute, we’d love to hear from you!


## Pasos mínimos para instalar y habilitar el entorno de la librería

1. **Ir a la carpeta del proyecto**

   - `cd /Users/johar/Desktop/Vizulation/proyect_visualization`

2. **Crear y activar el entorno virtual (macOS)**

   - `python3 -m venv new_library`  
   - `source new_library/bin/activate`

3. **Actualizar pip e instalar lo básico para notebooks**

   - `python -m pip install --upgrade pip`  
   - `pip install jupyter ipykernel ipywidgets`

4. **Instalar la librería en modo editable**

   - `cd our_library_mvp`  
   - `python -m pip install -e .`

5. **Registrar el kernel de Jupyter para este entorno**

   - `python -m ipykernel install --user --name our_library-mvp --display-name "Python (our_library-mvp)"`

6. **Probar la instalación en un notebook (usando el kernel “Python (our_library-mvp)”)**

   En una celda de código del notebook:

   - `import our_library as ol`  
   - `print("our_library version:", getattr(ol, "__version__", "sin __version__"))`  
   - `ol.hello_d3()`  *(si la función existe, debería mostrar el círculo D3)*

