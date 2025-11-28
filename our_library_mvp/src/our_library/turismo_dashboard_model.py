# src/our_library/turismo_dashboard_model.py

from typing import Optional, List, Tuple
import numpy as np
import pandas as pd

from .turismo_recs import (
    _load_models,
    _neighbors_by_vector,
    _rank_candidates,
    _apply_filters,
    _find_base_idx_by_code,
    _find_base_idx_by_name,
)
from .graph2_1 import show_dashboard_map_force_radar_linked

# Mismas columnas que el radar de la demo
RADAR_COLS = [
    "Food",
    "Altitude",
    "Physical activity",
    "Cultural activity",
    "Safety",
    "Costs",
    "Weather",
    "Outdoor/nature",
    "Party",
    "Open culture",
    "Mobility",
    "Accessibility",
    "Adventure/Adrenaline",
]


def _recommend_core_for_dashboard(
    model_dir: str,
    modo: str,
    valor: str,
    topk: int = 20,
    alpha: float = 1.0,
    geo_km: Optional[float] = None,
    rg_mode: Optional[str] = None,
    rg_weight: float = 0.05,
    filter_cat: Optional[str] = None,
    filter_tipo: Optional[str] = None,
    filter_sub: Optional[str] = None,
    geo_anchor_code: Optional[str] = None,
) -> Tuple[pd.DataFrame, Optional[int], pd.DataFrame]:
    """
    Misma idea que turismo_recs.recommend(), pero:
      - no imprime
      - no guarda CSV
      - devuelve (df_completo, base_idx, recs_df)
    """
    tfidf, knn, df = _load_models(model_dir)

    # preparar consulta (copiado de recommend)
    base_idx = None
    if modo == "code":
        base_idx = _find_base_idx_by_code(df, valor)
        q_vec = tfidf.transform([df.loc[base_idx, "TEXT"]])
    elif modo == "nombre":
        base_idx = _find_base_idx_by_name(df, valor)
        q_vec = tfidf.transform([df.loc[base_idx, "TEXT"]])
    elif modo == "texto":
        q_vec = tfidf.transform([str(valor).lower()])
        if geo_anchor_code is not None:
            try:
                base_idx = _find_base_idx_by_code(df, geo_anchor_code)
            except Exception:
                base_idx = None
    else:
        raise ValueError("modo debe ser 'code', 'nombre' o 'texto'.")

    # vecinos (pedimos un poco más)
    n_total = min(len(df), max(topk + 1, 200))
    idxs, dists = _neighbors_by_vector(knn, q_vec, n_total, len(df))

    # rg_mode
    rgm = None if (rg_mode is None or rg_mode == "none") else rg_mode

    # ranking
    recs = _rank_candidates(
        df,
        base_idx,
        idxs,
        dists,
        alpha=alpha,
        geo_km=geo_km,
        rg_mode=rgm,
        rg_weight=rg_weight,
    )

    # filtros opcionales
    recs = _apply_filters(recs, filter_cat, filter_tipo, filter_sub)

    # limitar topk
    recs = recs.head(topk).reset_index(drop=False)  # guardamos el índice original en "index"
    return df, base_idx, recs


def _row_to_node(row: pd.Series, score_norm: float) -> dict:
    """
    Convierte una fila de MINCETUR (df) en el formato de nodo que
    espera show_dashboard_map_force_radar_linked.

    score_norm: [0..1], se mapea a want_to_go y a los ejes del radar.
    """
    # Queremos algo tipo 4..9 para want_to_go
    want = 4.0 + 5.0 * float(score_norm)

    # ⚠️ MINCETUR: columnas LATITUD/LONGITUD vienen invertidas
    lat = None
    lon = None
    if "LATITUD" in row and "LONGITUD" in row:
        if pd.notna(row["LATITUD"]) and pd.notna(row["LONGITUD"]):
            # OJO: usamos LONGITUD como lat y LATITUD como lon
            lat = float(row["LONGITUD"])   # ~ -16
            lon = float(row["LATITUD"])    # ~ -71

    node = {
        "id": str(row.get("CODE", row.name)),
        "name": str(row.get("NOMBRE DEL RECURSO", row.get("CODE", "sin nombre"))),
        "region": str(row.get("REGION", "")),
        "REGION": str(row.get("REGION", "")),
        "lat": lat,
        "lon": lon,
        "LATITUD": lat,
        "LONGITUD": lon,
        "want_to_go": float(want),
        "url": str(row.get("URL", "")),
    }

    for col in RADAR_COLS:
        node[col] = float(2.0 + 3.0 * float(score_norm))

    return node


def _build_nodes_and_links_for_dashboard(
    df: pd.DataFrame,
    base_idx: Optional[int],
    recs: pd.DataFrame,
) -> Tuple[List[dict], List[dict]]:
    """
    Construye:
      - nodes: [base + recomendaciones]
      - links: base -> cada recomendación, con 'similarity' = SCORE normalizado
    """
    nodes = []
    links = []

    # Normalizamos SCORE para [0..1]
    if "SCORE" in recs.columns and not recs["SCORE"].isna().all():
        s_min = recs["SCORE"].min()
        s_max = recs["SCORE"].max()
        if s_max > s_min:
            scores_norm = (recs["SCORE"] - s_min) / (s_max - s_min)
        else:
            scores_norm = pd.Series(1.0, index=recs.index)
    else:
        scores_norm = pd.Series(0.5, index=recs.index)

    # 1) Nodo base (si existe)
    base_id = None
    if base_idx is not None:
        base_row = df.loc[base_idx]
        # le damos score_norm = 1.0 para que tenga radar grande
        base_node = _row_to_node(base_row, score_norm=1.0)
        base_id = base_node["id"]
        nodes.append(base_node)

    # 2) Nodos recomendados
    for i, rec_row in recs.iterrows():
        # rec_row["index"] = índice original en df
        orig_idx = rec_row["index"]
        full_row = df.loc[orig_idx]
        s_norm = float(scores_norm.loc[i]) if i in scores_norm.index else 0.5

        node = _row_to_node(full_row, score_norm=s_norm)
        # >>>>> NUEVO: guardar SCORE numérico en el nodo <<<<<
        node["SCORE"] = float(rec_row.get("SCORE", 0.0))

        nodes.append(node)

        if base_id is not None:
            # usamos SCORE como medida de similaridad
            sim_val = float(rec_row.get("SCORE", 0.0))
            links.append(
                {
                    "source": base_id,
                    "target": node["id"],
                    "similarity": sim_val,
                }
            )

    return nodes, links


def show_turismo_dashboard_from_model(
    model_dir: str = "models",
    modo: str = "code",
    valor: str = "",
    topk: int = 20,
    alpha: float = 1.0,
    geo_km: Optional[float] = None,
    rg_mode: Optional[str] = None,
    rg_weight: float = 0.05,
    filter_cat: Optional[str] = None,
    filter_tipo: Optional[str] = None,
    filter_sub: Optional[str] = None,
    geo_anchor_code: Optional[str] = None,
):
    """
    High-level:

      show_turismo_dashboard_from_model(
          model_dir="models",
          modo="code", valor="25",
          topk=20,
          alpha=0.8,
          geo_km=40,
          rg_mode="bonus",
      )

    Usa turismo_recs.py (TF-IDF+KNN+joblib+parquet) para:
      - Obtener base + recomendaciones (df, base_idx, recs)
      - Convertir a nodos y enlaces
      - Mostrar dashboard mapa+force+radar enlazado
    """
    df, base_idx, recs = _recommend_core_for_dashboard(
        model_dir=model_dir,
        modo=modo,
        valor=valor,
        topk=topk,
        alpha=alpha,
        geo_km=geo_km,
        rg_mode=rg_mode,
        rg_weight=rg_weight,
        filter_cat=filter_cat,
        filter_tipo=filter_tipo,
        filter_sub=filter_sub,
        geo_anchor_code=geo_anchor_code,
    )

    nodes, links = _build_nodes_and_links_for_dashboard(df, base_idx, recs)
    return show_dashboard_map_force_radar_linked(nodes, links)