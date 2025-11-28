# src/our_library/__init__.py

# src/our_library/__init__.py

"""
our_library: MVP para visualización interactiva de grafos + dashboards turísticos.
"""

# --- Opcional: recommender (si en el futuro lo agregas) ---
try:
    from .recommender import (
        load_recs,
        recs_ready,
        show_recs_table,
        show_city_card,
        show_city_gallery,
        show_city_details,
        show_rec_dashboard,
    )
except Exception:
    # Si no existe recommender.py o falla, no bloqueamos el paquete
    pass

# --- Funciones de grafos y dashboards ---
try:
    from .graph2_1 import (
        enable_colab_bridge,
        start_server,
        get_current_node,
        get_click_history,
        get_simple_click_history,
        clear_click_history,
        get_clicks_by_source,
        print_click_summary,
        hello1_d3,
        show_graph1,
        show_graph_force1,
        show_graph_force_vanilla1,
        show_graph_force_vanilla_checklist1,
        show_matrix_layout1,
        show_radar_layout1,
        show_dashboard_matrix_radar_force7,
        show_linked_dashboard,
        show_dashboard_map_force_radar_linked,
        show_click_timecurve,             
        show_click_timecurve_from_history
    )
except Exception:
    # Si no existe graph.py en esta build, tampoco reventamos el import base
    pass


# --- API de turismo basada en modelos entrenados ---
from .turismo_dashboard_model import show_turismo_dashboard_from_model


# --- Visualizaciones extra de turismo (clima, transporte, denuncias) ---
try:
    from .turismo_extra_charts import (
        show_transport_access,
        show_crime_monthly_dashboard,
        show_temperature_sunflower,
        show_region_weather_face,
        show_region_footprint,
    )
except Exception:
    # Si no existe el módulo en alguna build, simplemente no se exportan
    pass


__all__ = [
    # grafos (solo estarán si graph.py existe)
    "enable_colab_bridge",
    "start_server",
    "hello1_d3",
    "show_graph1",
    "show_graph_force1",
    "show_graph_force_vanilla1",
    "show_graph_force_vanilla_checklist1",
    "show_matrix_layout1",
    "show_radar_layout1",
    "show_dashboard_matrix_radar_force7",
    "show_linked_dashboard",
    "show_dashboard_map_force_radar_linked",
    # recommender (si existiera)
    "load_recs",
    "recs_ready",
    "show_recs_table",
    "show_city_card",
    "show_city_gallery",
    "show_city_details",
    "show_rec_dashboard",
    "get_current_node",
    "get_click_history",
    "get_simple_click_history",
    "clear_click_history",
    "get_clicks_by_source",
    "print_click_summary",
    "show_dashboard_map_force_radar_linked",
    "show_click_timecurve",
    "show_click_timecurve_from_history",
]

__all__ += [
    "show_turismo_dashboard_from_model",
    # vistas extra
    "show_transport_access",
    "show_crime_monthly_dashboard",
    "show_temperature_sunflower",
    "show_region_weather_face",
    "show_region_footprint",
]
__version__ = "8.0.0"