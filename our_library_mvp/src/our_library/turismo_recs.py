# turismo_recs.py
# Requisitos:
#   pip install pandas numpy scikit-learn joblib pyarrow
# Uso:
#   1) Entrenar una vez:
#      python turismo_recs.py train --input /ruta/datos.csv --model_dir models
#   2) Recomendar (sin reentrenar):
#      # por CODE
#      python turismo_recs.py recommend --modo code --valor 25 --model_dir models --topk 10 --alpha 0.8 --geo_km 40 --rg_mode bonus --output recs_code.csv
#      # por NOMBRE (busca fragmento en "NOMBRE DEL RECURSO")
#      python turismo_recs.py recommend --modo nombre --valor "catarata" --model_dir models --topk 10 --alpha 1.0 --output recs_nombre.csv
#      # por TEXTO LIBRE (tema) + ancla geográfica (opcional)
#      python turismo_recs.py recommend --modo texto --valor "montañas nevado trekking" --geo_anchor_code 25 --geo_km 50 --alpha 0.85 --rg_mode bonus --output recs_texto.csv

import os
import argparse
import joblib
import numpy as np
import pandas as pd
from math import radians, sin, cos, asin, sqrt
from typing import Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

# ------------------ utilidades ------------------

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _validate_cols(df: pd.DataFrame):
    needed = ["CODE","NOMBRE DEL RECURSO","CATEGORIA","TIPO_DE_CATEGORIA","SUB_TIPO_CATEGORIA"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {missing}")
    # LAT/LON si existen -> numérico
    for c in ["LATITUD","LONGITUD"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

def _build_text(df: pd.DataFrame) -> pd.DataFrame:
    if "TEXT" not in df.columns:
        df["TEXT"] = (
            df["NOMBRE DEL RECURSO"].fillna("") + " " +
            df["CATEGORIA"].fillna("") + " " +
            df["TIPO_DE_CATEGORIA"].fillna("") + " " +
            df["SUB_TIPO_CATEGORIA"].fillna("")
        ).str.lower()
    return df

def _haversine_km(lat1, lon1, lat2, lon2):
    vals = [lat1, lon1, lat2, lon2]
    if any(pd.isna(v) for v in vals): 
        return np.nan
    R = 6371.0
    dlat, dlon = radians(lat2-lat1), radians(lon2-lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2 * R * asin(sqrt(a))

# ------------------ entrenamiento ------------------

def train_and_save(input_csv: str, model_dir: str, min_df=2, max_features=20000, ngram_max=2):
    _ensure_dir(model_dir)
    df = pd.read_csv(input_csv)
    _validate_cols(df)
    df = _build_text(df).reset_index(drop=True)

    tfidf = TfidfVectorizer(
        min_df=min_df,
        max_features=max_features,
        ngram_range=(1, ngram_max)
    ).fit(df["TEXT"])

    X = tfidf.transform(df["TEXT"])
    knn = NearestNeighbors(metric="cosine", algorithm="brute").fit(X)

    joblib.dump(tfidf, os.path.join(model_dir, "tfidf.joblib"))
    joblib.dump(knn,   os.path.join(model_dir, "knn.joblib"))
    df.to_parquet(os.path.join(model_dir, "recursos.parquet"))

    print("=== ENTRENAMIENTO OK ===")
    print(f"- Artefactos: {model_dir}")
    print(f"- Registros: {len(df):,} | Vocabulario TF-IDF: {len(tfidf.vocabulary_):,}")

# ------------------ carga e inferencia ------------------

def _load_models(model_dir: str):
    tfidf = joblib.load(os.path.join(model_dir, "tfidf.joblib"))
    knn   = joblib.load(os.path.join(model_dir, "knn.joblib"))
    df    = pd.read_parquet(os.path.join(model_dir, "recursos.parquet"))
    return tfidf, knn, df

def _neighbors_by_vector(knn, q_vec, n: int, universe_size: int):
    n = min(n, universe_size)
    distances, indices = knn.kneighbors(q_vec, n_neighbors=n)
    return indices[0].tolist(), distances[0].tolist()

def _rank_candidates(df: pd.DataFrame,
                     base_idx: Optional[int],
                     idxs, dists,
                     alpha=1.0, geo_km=None,
                     rg_mode=None, rg_weight=0.05):
    # similitud de texto
    sim = pd.Series(1.0 - np.array(dists), index=idxs)
    cand = df.iloc[idxs].copy()
    if base_idx is not None and base_idx in cand.index:
        cand = cand.drop(index=base_idx)
    cand["SIM_TEXT"] = cand.index.map(sim).astype(float)

    # macro-región (requiere columna y base_idx)
    if "REGION_GEOGRAFICA" in df.columns and base_idx is not None:
        base_rg = df.loc[base_idx, "REGION_GEOGRAFICA"]
        if rg_mode == "filter":
            cand = cand[cand["REGION_GEOGRAFICA"] == base_rg].copy()
            cand["RG_BONUS"] = 0.0
        elif rg_mode == "bonus":
            cand["RG_BONUS"] = (cand["REGION_GEOGRAFICA"] == base_rg).astype(float)
        else:
            cand["RG_BONUS"] = 0.0
    else:
        cand["RG_BONUS"] = 0.0

    # geografía (si hay ancla con lat/lon y radio definido)
    if geo_km is not None and base_idx is not None and "LATITUD" in df.columns and "LONGITUD" in df.columns:
        lat0, lon0 = df.loc[base_idx, "LATITUD"], df.loc[base_idx, "LONGITUD"]
        if pd.notna(lat0) and pd.notna(lon0):
            cand["DIST_KM"] = cand.apply(lambda r: _haversine_km(lat0, lon0, r.get("LATITUD", np.nan), r.get("LONGITUD", np.nan)), axis=1)
            cand["GEO_BONUS"] = (1.0 - cand["DIST_KM"]/float(geo_km)).clip(lower=0, upper=1)
        else:
            cand["DIST_KM"] = np.nan
            cand["GEO_BONUS"] = 0.0
    else:
        cand["DIST_KM"] = np.nan
        cand["GEO_BONUS"] = 0.0

    cand["SCORE"] = alpha*cand["SIM_TEXT"] + (1.0 - alpha)*cand["GEO_BONUS"] + rg_weight*cand["RG_BONUS"]

    cols = ["CODE","REGION","PROVINCIA","DISTRITO","NOMBRE DEL RECURSO","CATEGORIA",
            "TIPO_DE_CATEGORIA","SUB_TIPO_CATEGORIA","URL","LATITUD","LONGITUD",
            "REGION_GEOGRAFICA","SIM_TEXT","GEO_BONUS","RG_BONUS","DIST_KM","SCORE"]
    cols = [c for c in cols if c in cand.columns]
    return cand.sort_values("SCORE", ascending=False)[cols]

def _apply_filters(recs: pd.DataFrame, filter_cat=None, filter_tipo=None, filter_sub=None):
    if filter_cat:
        recs = recs[recs["CATEGORIA"].astype(str).str.contains(filter_cat, case=False, na=False)]
    if filter_tipo:
        recs = recs[recs["TIPO_DE_CATEGORIA"].astype(str).str.contains(filter_tipo, case=False, na=False)]
    if filter_sub:
        recs = recs[recs["SUB_TIPO_CATEGORIA"].astype(str).str.contains(filter_sub, case=False, na=False)]
    return recs

def _find_base_idx_by_code(df: pd.DataFrame, code):
    m = df.index[df["CODE"].astype(str) == str(code)]
    if len(m) == 0: 
        raise ValueError(f"No existe CODE={code}")
    return int(m[0])

def _find_base_idx_by_name(df: pd.DataFrame, fragmento: str):
    hits = df[df["NOMBRE DEL RECURSO"].astype(str).str.contains(str(fragmento), case=False, na=False)]
    if hits.empty:
        raise ValueError(f"No hallé nombres que contengan: {fragmento}")
    return int(hits.index[0])

# ------------------ interfaz de recomendación ------------------

def recommend(model_dir: str,
              modo: str,
              valor: str,
              topk=10,
              alpha=1.0,
              geo_km: Optional[float]=None,
              rg_mode: Optional[str]=None,
              rg_weight: float=0.05,
              filter_cat: Optional[str]=None,
              filter_tipo: Optional[str]=None,
              filter_sub: Optional[str]=None,
              geo_anchor_code: Optional[str]=None,
              output: Optional[str]=None):
    """
    modo: 'code' | 'nombre' | 'texto'
      - code/nombre: usa el recurso base como ancla (puede aplicar geo y macro-región)
      - texto: consulta libre; si pasas geo_anchor_code, lo usa como ancla para DIST_KM/GEO_BONUS
    """
    tfidf, knn, df = _load_models(model_dir)

    # preparar consulta
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

    # vecinos (pedimos más para poder excluir el propio)
    n_total = min(len(df), max(topk+1, 200))
    idxs, dists = _neighbors_by_vector(knn, q_vec, n_total, len(df))

    # rg_mode
    rgm = None if (rg_mode is None or rg_mode == "none") else rg_mode

    # ranking
    recs = _rank_candidates(df, base_idx, idxs, dists, alpha=alpha, geo_km=geo_km, rg_mode=rgm, rg_weight=rg_weight)

    # filtros opcionales
    recs = _apply_filters(recs, filter_cat, filter_tipo, filter_sub)

    # limitar y salida
    recs = recs.head(topk).reset_index(drop=True)

    # imprimir base si aplica
    if base_idx is not None:
        base = df.loc[base_idx, ["CODE","NOMBRE DEL RECURSO","REGION"]].to_dict()
        print(f"[Base] CODE={base.get('CODE')} | {base.get('NOMBRE DEL RECURSO')} | {base.get('REGION','')}")
    else:
        print("[Base] Consulta por TEXTO LIBRE (sin ancla geográfica)")

    if output:
        recs.to_csv(output, index=False)
        print(f"Guardado en: {output}")

    with pd.option_context("display.max_colwidth", None):
        print(recs)

    return recs

# ------------------ CLI ------------------

def _parse_args():
    p = argparse.ArgumentParser(description="Recomendador turístico: entrena una vez y recomienda variando parámetros.")
    sub = p.add_subparsers(dest="cmd", required=True)

    # train
    p_train = sub.add_parser("train", help="Entrena y guarda artefactos (TF-IDF + KNN + dataset)")
    p_train.add_argument("--input", required=True, help="CSV MINCETUR")
    p_train.add_argument("--model_dir", default="models", help="Carpeta de artefactos")
    p_train.add_argument("--min_df", type=int, default=2)
    p_train.add_argument("--max_features", type=int, default=20000)
    p_train.add_argument("--ngram_max", type=int, default=2)

    # recommend
    p_rec = sub.add_parser("recommend", help="Carga modelos y recomienda (sin reentrenar)")
    p_rec.add_argument("--model_dir", default="models", help="Carpeta de artefactos")
    p_rec.add_argument("--modo", choices=["code","nombre","texto"], required=True)
    p_rec.add_argument("--valor", required=True, help="CODE (si modo=code), fragmento de nombre (si modo=nombre), o texto libre (si modo=texto)")
    p_rec.add_argument("--topk", type=int, default=10)
    p_rec.add_argument("--alpha", type=float, default=1.0, help="Peso del texto (0..1). 1=solo texto")
    p_rec.add_argument("--geo_km", type=float, default=None, help="Radio km para bonus geográfico (None desactiva)")
    p_rec.add_argument("--rg_mode", choices=["none","filter","bonus"], default="none", help="Macro-región: none|filter|bonus")
    p_rec.add_argument("--rg_weight", type=float, default=0.05, help="Peso del bonus de macro-región (si rg_mode=bonus)")
    p_rec.add_argument("--filter_cat",  default=None, help="Filtrar CATEGORIA (contiene, case-insensitive)")
    p_rec.add_argument("--filter_tipo", default=None, help="Filtrar TIPO_DE_CATEGORIA (contiene)")
    p_rec.add_argument("--filter_sub",  default=None, help="Filtrar SUB_TIPO_CATEGORIA (contiene)")
    p_rec.add_argument("--geo_anchor_code", default=None, help="(Solo modo=texto) CODE para anclar geografía")
    p_rec.add_argument("--output", default=None, help="CSV de salida")
    return p.parse_args()

def main():
    args = _parse_args()
    if args.cmd == "train":
        train_and_save(args.input, args.model_dir, args.min_df, args.max_features, args.ngram_max)
    elif args.cmd == "recommend":
        recommend(
            model_dir=args.model_dir,
            modo=args.modo,
            valor=args.valor,
            topk=args.topk,
            alpha=args.alpha,
            geo_km=args.geo_km,
            rg_mode=args.rg_mode,
            rg_weight=args.rg_weight,
            filter_cat=args.filter_cat,
            filter_tipo=args.filter_tipo,
            filter_sub=args.filter_sub,
            geo_anchor_code=args.geo_anchor_code,
            output=args.output
        )

if __name__ == "__main__":
    main()