# src/our_library/turismo_extra_charts.py

from __future__ import annotations

import re
import json
import unicodedata
import uuid
from pathlib import Path
from typing import Optional

import pandas as pd
from IPython.display import HTML


# ----------------- Helpers comunes ----------------- #

def _normalize_region(name: Optional[str]) -> str:
    """Normaliza nombres de región/departamento: quita tildes, mayúsculas."""
    if name is None:
        return ""
    s = str(name).strip()
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.upper()


def _ensure_path(path: str | Path) -> Path:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No encuentro el archivo: {p}")
    return p


# =========================================================
#  1) Acceso a la capital regional · Modos de transporte
# =========================================================

def show_transport_access(
    csv_path: str | Path,
    highlight_region: Optional[str] = None,
) -> HTML:
    """
    Visualización D3:

      - Matriz Departamento × Modo (Avión/Bus/Tren/Barco).
      - Cada celda es un círculo ⇒ "Sí" (color por modo) o "No" (gris).
      - Clic en departamento muestra detalle en un panel lateral.

    Parámetros
    ----------
    csv_path : ruta al CSV `acceso_capital_departamento_transportes_SI_NO.csv`
    highlight_region : nombre de departamento/región a resaltar (opcional),
                       se compara sin tildes y sin distinguir mayúsculas.
    """
    csv_path = _ensure_path(csv_path)
    df = pd.read_csv(csv_path)

    # Esperamos columnas como:
    # Departamento, Avión, Bus, Tren, Barco
    if "Departamento" not in df.columns:
        raise ValueError("Se esperaba una columna 'Departamento' en el CSV.")

    mode_cols = [c for c in df.columns if c != "Departamento"]
    if not mode_cols:
        raise ValueError("No encontré columnas de modos de transporte (Avión/Bus/Tren/Barco).")

    df["norm"] = df["Departamento"].map(_normalize_region)
    highlight_norm = _normalize_region(highlight_region) if highlight_region else None

    rows = []
    for _, r in df.iterrows():
        modes = []
        for m in mode_cols:
            val = str(r[m]).strip().lower()
            has_mode = val in ("si", "sí", "yes", "true", "1")
            modes.append({"mode": m, "has": bool(has_mode)})
        rows.append(
            {
                "dept": str(r["Departamento"]),
                "norm": str(r["norm"]),
                "modes": modes,
            }
        )

    payload = {
        "rows": rows,
        "modes": mode_cols,
        "highlight": highlight_norm,
    }

    data_json = json.dumps(payload, ensure_ascii=False)
    chart_id = f"transport-{uuid.uuid4().hex}"

    template = """
<div id="[CHART_ID]" style="width:100%; max-width:900px; margin:10px auto; font-family:system-ui;">
  <h3 style="margin:0 0 8px;">Acceso a la capital regional · Modos de transporte</h3>
  <p style="margin:0 0 10px; font-size:12px; color:#555;">
    Cada fila es un departamento. Cada columna, un modo de transporte. Los círculos llenos indican que puedes llegar usando ese modo.
  </p>
  <div style="display:flex; gap:16px; align-items:flex-start;">
    <div id="[CHART_ID]-svg" style="flex:1 1 auto; min-height:360px;"></div>
    <div id="[CHART_ID]-panel" style="width:260px; font-size:12px; background:#f8f9fa; border-radius:8px; padding:8px 10px; border:1px solid #e0e0e0;">
      <strong>Detalle de la selección</strong>
      <div id="[CHART_ID]-panel-body" style="margin-top:6px; line-height:1.4;">
        Haz clic en un departamento para ver sus combinaciones de transporte.
      </div>
    </div>
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script>
(function() {
  const payload = [DATA];
  const rows = payload.rows || [];
  const modes = payload.modes || [];
  const highlightNorm = payload.highlight || null;

  const rootId = "[CHART_ID]";
  const svgHost = document.getElementById(rootId + "-svg");
  const panelBody = document.getElementById(rootId + "-panel-body");
  if (!svgHost || !panelBody) return;

  const margin = { top: 30, right: 20, bottom: 30, left: 120 };
  const width = svgHost.clientWidth || 600;
  const height = Math.max(60 + rows.length * 22, 220);

  const svg = d3.select(svgHost)
    .append("svg")
    .attr("width", width)
    .attr("height", height);

  const g = svg.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const innerWidth  = width  - margin.left - margin.right;
  const innerHeight = height - margin.top  - margin.bottom;

  const deptNames = rows.map(r => r.dept);
  const y = d3.scaleBand()
    .domain(deptNames)
    .range([0, innerHeight])
    .padding(0.2);

  const x = d3.scaleBand()
    .domain(modes)
    .range([0, innerWidth])
    .padding(0.2);

  const modeColor = d3.scaleOrdinal()
    .domain(modes)
    .range(["#1565c0", "#ef6c00", "#2e7d32", "#6a1b9a"]);

  // Fondo suave
  g.append("rect")
    .attr("x", -margin.left + 10)
    .attr("y", -margin.top + 5)
    .attr("width", width - 20)
    .attr("height", height - 20)
    .attr("fill", "#fafbff")
    .attr("rx", 10);

  // Eje X
  g.append("g")
    .attr("transform", `translate(0,${innerHeight})`)
    .call(d3.axisBottom(x))
    .selectAll("text")
    .attr("font-size", 11);

  // Eje Y
  g.append("g")
    .call(d3.axisLeft(y))
    .selectAll("text")
    .attr("font-size", 11)
    .attr("font-weight", d => {
      const row = rows.find(r => r.dept === d);
      return (row && row.norm === highlightNorm) ? "bold" : "normal";
    });

  // Datos planos (dept × modo)
  const flat = [];
  rows.forEach(r => {
    (r.modes || []).forEach(m => {
      flat.push({
        dept: r.dept,
        norm: r.norm,
        mode: m.mode,
        has: !!m.has
      });
    });
  });

  const rowByDept = new Map(rows.map(r => [r.dept, r]));

  const cells = g.selectAll("circle.cell")
    .data(flat)
    .join("circle")
    .attr("class", "cell")
    .attr("cx", d => (x(d.mode) || 0) + x.bandwidth() / 2)
    .attr("cy", d => (y(d.dept) || 0) + y.bandwidth() / 2)
    .attr("r", d => d.has ? Math.min(x.bandwidth(), y.bandwidth()) / 2.2
                           : Math.min(x.bandwidth(), y.bandwidth()) / 3.2)
    .attr("fill", d => d.has ? modeColor(d.mode) : "#e0e0e0")
    .attr("fill-opacity", d => d.has ? 0.95 : 0.3)
    .attr("stroke", d => {
      if (!highlightNorm) return "#ffffff";
      return d.norm === highlightNorm ? "#000" : "#ffffff";
    })
    .attr("stroke-width", d => (d.norm === highlightNorm ? 1.6 : 1.0))
    .style("cursor", "pointer")
    .on("click", (_, d) => {
      const row = rowByDept.get(d.dept);
      if (row) renderPanel(row);
    });

  function renderPanel(row) {
    const modesSorted = (row.modes || []).slice()
      .sort((a, b) => d3.ascending(a.mode, b.mode));

    const yes = modesSorted.filter(m => m.has);
    const no  = modesSorted.filter(m => !m.has);

    const yesList = yes.length
      ? `<ul style="padding-left:16px; margin:4px 0;">${
          yes.map(m => `<li>${m.mode}</li>`).join("")
        }</ul>`
      : "<em>No tiene conexión directa registrada.</em>";

    const noList = no.length
      ? `<ul style="padding-left:16px; margin:4px 0;">${
          no.map(m => `<li>${m.mode}</li>`).join("")
        }</ul>`
      : "<em>Tiene todos los modos listados.</em>";

    panelBody.innerHTML = `
      <div style="font-size:13px; margin-bottom:4px;">
        <strong>${row.dept}</strong>
      </div>
      <div style="margin-bottom:4px;">
        <span style="font-size:11px; color:#666;">Modos disponibles:</span>
        ${yesList}
      </div>
      <div>
        <span style="font-size:11px; color:#666;">No disponibles:</span>
        ${noList}
      </div>
    `;
  }

  // Autoselección si hay región destacada
  if (highlightNorm) {
    const row = rows.find(r => r.norm === highlightNorm);
    if (row) renderPanel(row);
  }
})();
</script>
"""

    html = template.replace("[CHART_ID]", chart_id).replace("[DATA]", data_json)
    return HTML(html)


# =========================================================
#  2) Denuncias 2024 por mes · Dashboard interactivo
# =========================================================

def show_crime_monthly_dashboard(
    csv_path: str | Path,
    region: Optional[str] = None,
) -> HTML:
    """
    Dashboard D3 para `denuncias_2024_por_mes_wide.csv`:

      - Selector de región.
      - Gráfico principal de línea + "barras de calor" por mes para la región
        seleccionada.
      - Panel lateral con resumen (total anual, mes pico, etc.).

    El CSV se espera en formato ancho:
      MES, AMAZONAS, ANCASH, APURIMAC, ..., UCAYALI
    """
    csv_path = _ensure_path(csv_path)
    df = pd.read_csv(csv_path)

    if "MES" not in df.columns:
        raise ValueError("Se esperaba una columna 'MES' con el número de mes (1-12).")

    month_col = "MES"
    region_cols = [c for c in df.columns if c != month_col]

    regions_meta = [{"name": c, "norm": _normalize_region(c)} for c in region_cols]

    series = []
    global_min = None
    global_max = None

    for col, meta in zip(region_cols, regions_meta):
        vals = []
        for _, row in df.iterrows():
            m = int(row[month_col])
            v = float(row[col])
            vals.append({"month": m, "value": v})
            if global_min is None or v < global_min:
                global_min = v
            if global_max is None or v > global_max:
                global_max = v
        series.append(
            {
                "region": meta["name"],
                "norm": meta["norm"],
                "values": vals,
            }
        )

    if global_min is None:
        global_min = 0.0
    if global_max is None:
        global_max = 1.0

    target_norm = _normalize_region(region) if region else None
    if target_norm and not any(s["norm"] == target_norm for s in series):
        target_norm = None

    payload = {
        "series": series,
        "regions": regions_meta,
        "globalMin": global_min,
        "globalMax": global_max,
        "defaultRegionNorm": target_norm,
    }

    data_json = json.dumps(payload, ensure_ascii=False)
    chart_id = f"crime-{uuid.uuid4().hex}"

    template = """
<div id="[CHART_ID]" style="width:100%; max-width:1000px; margin:10px auto; font-family:system-ui;">
  <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:8px;">
    <h3 style="margin:0;">Denuncias 2024 · Serie mensual por región</h3>
    <div style="font-size:12px;">
      Región:
      <select id="[CHART_ID]-select" style="font-size:12px; padding:2px 4px;"></select>
    </div>
  </div>
  <p style="margin:0 0 8px; font-size:12px; color:#555;">
    El color de fondo por mes refleja la intensidad relativa de denuncias; la línea muestra la evolución mensual.
  </p>
  <div style="display:flex; gap:16px; align-items:stretch;">
    <div id="[CHART_ID]-svg" style="flex:1 1 auto; min-height:360px;"></div>
    <div id="[CHART_ID]-sidebar" style="width:260px; font-size:12px; background:#f8f9fa; border-radius:8px; padding:8px 10px; border:1px solid #e0e0e0;">
      <strong>Resumen anual</strong>
      <div id="[CHART_ID]-sidebar-body" style="margin-top:6px; line-height:1.4;">
        Selecciona una región para ver su resumen.
      </div>
    </div>
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script>
(function() {
  const payload = [DATA];
  const series = payload.series || [];
  const regions = payload.regions || [];
  const globalMin = payload.globalMin ?? 0;
  const globalMax = payload.globalMax ?? 1;
  const defaultNorm = payload.defaultRegionNorm || (regions[0] && regions[0].norm);

  const rootId = "[CHART_ID]";
  const svgHost = document.getElementById(rootId + "-svg");
  const sidebar = document.getElementById(rootId + "-sidebar-body");
  const select = document.getElementById(rootId + "-select");
  if (!svgHost || !sidebar || !select || !series.length) return;

  // Llenar el selector
  regions.forEach(r => {
    const opt = document.createElement("option");
    opt.value = r.norm;
    opt.textContent = r.name;
    select.appendChild(opt);
  });

  const margin = { top: 30, right: 20, bottom: 40, left: 60 };
  const width = svgHost.clientWidth || 640;
  const height = 380;

  const svg = d3.select(svgHost)
    .append("svg")
    .attr("width", width)
    .attr("height", height);

  const g = svg.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const innerWidth  = width  - margin.left - margin.right;
  const innerHeight = height - margin.top  - margin.bottom;

  const months = d3.range(1, 13);
  const monthLabels = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];

  const x = d3.scaleBand()
    .domain(months)
    .range([0, innerWidth])
    .padding(0.15);

  const y = d3.scaleLinear()
    .range([innerHeight, 0]);

  const color = d3.scaleSequential(d3.interpolateOrRd)
    .domain([globalMin, globalMax]);

  const xAxisG = g.append("g")
    .attr("transform", `translate(0,${innerHeight})`)
    .call(
      d3.axisBottom(x)
        .tickFormat(m => monthLabels[m - 1])
    )
    .selectAll("text")
    .attr("font-size", 11);

  const yAxisG = g.append("g");

  g.append("text")
    .attr("x", innerWidth / 2)
    .attr("y", innerHeight + 32)
    .attr("text-anchor", "middle")
    .attr("font-size", 11)
    .text("Mes");

  const yLabel = g.append("text")
    .attr("x", -innerHeight / 2)
    .attr("y", -46)
    .attr("transform", "rotate(-90)")
    .attr("text-anchor", "middle")
    .attr("font-size", 11)
    .text("Denuncias registradas");

  // Rectángulos de fondo por mes (se recolorean según la región seleccionada)
  const bgRects = g.selectAll("rect.bg-month")
    .data(months)
    .join("rect")
    .attr("class", "bg-month")
    .attr("x", m => x(m))
    .attr("width", x.bandwidth())
    .attr("y", 0)
    .attr("height", innerHeight)
    .attr("fill", "#f5f5f5")
    .attr("fill-opacity", 0.4);

  const line = d3.line()
    .x(d => (x(d.month) || 0) + x.bandwidth() / 2)
    .y(d => y(d.value))
    .curve(d3.curveMonotoneX);

  const linePath = g.append("path")
    .attr("fill", "none")
    .attr("stroke", "#0d47a1")
    .attr("stroke-width", 2);

  const pointGroup = g.append("g");

  function getSeriesByNorm(norm) {
    return series.find(s => s.norm === norm) || series[0];
  }

  function update(norm) {
    const s = getSeriesByNorm(norm);
    const vals = (s && s.values) ? s.values.slice().sort((a, b) => a.month - b.month) : [];

    const localMax = d3.max(vals, d => d.value) || globalMax || 1;
    const yMax = Math.max(localMax * 1.1, (globalMax || localMax) * 0.4);
    y.domain([0, yMax]).nice();

    yAxisG.transition().duration(400).call(d3.axisLeft(y).ticks(5));

    const byMonth = new Map(vals.map(d => [d.month, d.value]));

    bgRects
      .transition().duration(400)
      .attr("fill", m => {
        const v = byMonth.get(m);
        if (v == null) return "#f5f5f5";
        return color(v);
      })
      .attr("fill-opacity", m => (byMonth.get(m) == null ? 0.3 : 0.7));

    linePath
      .datum(vals)
      .transition().duration(450)
      .attr("d", line);

    const pts = pointGroup.selectAll("circle.point")
      .data(vals, d => d.month);

    pts.join(
      enter => enter.append("circle")
        .attr("class", "point")
        .attr("r", 3.5)
        .attr("cx", d => (x(d.month) || 0) + x.bandwidth() / 2)
        .attr("cy", d => y(d.value))
        .attr("fill", "#0d47a1"),
      update => update
        .transition().duration(450)
        .attr("cx", d => (x(d.month) || 0) + x.bandwidth() / 2)
        .attr("cy", d => y(d.value)),
      exit => exit.remove()
    );

    // Sidebar resumen
    const total = d3.sum(vals, d => d.value);
    const maxItem = vals.reduce((acc, d) => (d.value > acc.value ? d : acc), { month: null, value: -Infinity });
    const minItem = vals.reduce((acc, d) => (d.value < acc.value ? d : acc), { month: null, value: Infinity });

    const maxLabel = maxItem.month ? monthLabels[maxItem.month - 1] : "–";
    const minLabel = minItem.month ? monthLabels[minItem.month - 1] : "–";

    sidebar.innerHTML = `
      <div style="font-size:13px; margin-bottom:4px;">
        <strong>${s.region}</strong>
      </div>
      <div style="margin-bottom:3px;">
        <span style="font-size:11px; color:#666;">Total anual:</span>
        <br><strong>${total.toLocaleString("es-PE")}</strong> denuncias
      </div>
      <div style="margin-bottom:3px;">
        <span style="font-size:11px; color:#666;">Mes más crítico:</span>
        <br><strong>${maxLabel}</strong> (${maxItem.value.toLocaleString("es-PE")})
      </div>
      <div>
        <span style="font-size:11px; color:#666;">Mes más bajo:</span>
        <br><strong>${minLabel}</strong> (${minItem.value.toLocaleString("es-PE")})
      </div>
    `;
  }

  // Eventos
  select.addEventListener("change", e => {
    update(e.target.value);
  });

  const initNorm = defaultNorm || (regions[0] && regions[0].norm);
  if (initNorm) {
    select.value = initNorm;
    update(initNorm);
  } else {
    update(regions[0].norm);
  }
})();
</script>
"""

    html = template.replace("[CHART_ID]", chart_id).replace("[DATA]", data_json)
    return HTML(html)


# =========================================================
#  3) Girasol de temperatura mensual por región (clima)
# =========================================================

# dentro de src/our_library/turismo_extra_charts.py
import json
import uuid
from pathlib import Path
import pandas as pd
from IPython.display import HTML


def show_temperature_sunflower(
    csv_path: str,
    region: str | None = None,
    date_col: str = "time",
    region_col: str = "REGION",
    tmax_col: str = "temperature_2m_max (°C)",
    tmin_col: str = "temperature_2m_min (°C)",
):
    """
    Girasol térmico:
      - Vista inicial: 1 pétalo por MES (longitud = Tmax media del mes, color = intensidad de calor).
      - Al hacer click en un pétalo de mes: se abre la vista de DÍAS de ese mes (1 pétalo por día).
      - Click en el centro de la flor: vuelve a vista de meses.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"No encuentro el CSV de clima: {csv_path}")

    df = pd.read_csv(csv_path)

    # Validar columnas
    missing = [c for c in (date_col, region_col, tmax_col, tmin_col) if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas en el CSV de clima: {missing}")

    # Parsear fecha
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    # Filtro por región (case-insensitive)
    if region is not None:
        mask = df[region_col].astype(str).str.upper() == str(region).upper()
        df_reg = df[mask].copy()
        if df_reg.empty:
            raise ValueError(
                f"No hallé registros para la región '{region}' "
                f"usando la columna {region_col}."
            )
    else:
        df_reg = df.copy()

    # Normalizar nombres de columnas para enviar al JS
    df_reg["month"] = df_reg[date_col].dt.month
    df_reg["day"] = df_reg[date_col].dt.day
    df_reg["date_str"] = df_reg[date_col].dt.strftime("%Y-%m-%d")

    df_reg["tmax"] = pd.to_numeric(df_reg[tmax_col], errors="coerce")
    df_reg["tmin"] = pd.to_numeric(df_reg[tmin_col], errors="coerce")
    df_reg = df_reg.dropna(subset=["tmax", "tmin"])

    if df_reg.empty:
        raise ValueError("Después de limpiar tmax/tmin no quedó data para dibujar el girasol.")

    # --- Agregados mensuales (para vista 'mes') ---
    month_names = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
    }

    monthly = (
        df_reg.groupby("month")
        .agg(
            tmax_mean=("tmax", "mean"),
            tmin_mean=("tmin", "mean"),
            tmax_max=("tmax", "max"),
            tmin_min=("tmin", "min"),
            n_days=("tmax", "size"),
        )
        .reset_index()
    )
    monthly["month_name"] = monthly["month"].map(month_names)

    monthly_data = monthly.to_dict(orient="records")
    daily_data = df_reg[["month", "day", "date_str", "tmax", "tmin"]].to_dict(orient="records")

    region_label = str(region or df_reg[region_col].astype(str).iloc[0])

    payload = {
        "region": region_label,
        "monthly": monthly_data,
        "daily": daily_data,
    }
    data_json = json.dumps(payload, ensure_ascii=False, default=float)

    sun_id = f"sun-{uuid.uuid4().hex}"

    html = f"""
<div style="border:3px solid #ffb300; border-radius:16px; padding:10px; max-width:900px;">
  <h3 style="margin:4px 0 6px;">Clima · Girasol térmico — {region_label}</h3>
  <p style="margin:0 0 8px; font-size:12px;">
    Vista inicial: cada pétalo es un <strong>mes</strong> (longitud = temperatura máxima media,
    color = intensidad de calor).<br>
    Haz clic en un pétalo para ver los <strong>días</strong> de ese mes como pétalos individuales.
    Haz clic en el <strong>centro</strong> para volver a la vista por meses.
  </p>
  <div id="{sun_id}" style="width:100%; height:600px;"></div>
</div>

<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-scale-chromatic@3"></script>

<script>
(function(){{
  const hostId = "{sun_id}";
  const payload = {data_json};

  const container = document.getElementById(hostId);
  const W = container.clientWidth || 800;
  const H = 560;

  const svg = d3.select(container)
    .append("svg")
    .attr("width", W)
    .attr("height", H);

  const cx = W / 2;
  const cy = H / 2 - 30;
  const coreRadius = 40;

  // --------- Tallo y hojas decorativas ----------
  const stemTopY = cy + coreRadius;
  const stemHeight = 170;

  svg.append("rect")
    .attr("x", cx - 8)
    .attr("y", stemTopY)
    .attr("width", 16)
    .attr("height", stemHeight)
    .attr("rx", 8)
    .attr("fill", "#66bb6a")
    .attr("opacity", 0.9);

  // Hoja izquierda
  const leafLeftPath =
    "M " + (cx - 55) + " " + (stemTopY + 70) +
    " Q " + (cx - 110) + " " + (stemTopY + 25) + " " + (cx - 25) + " " + (stemTopY + 5) +
    " Q " + (cx - 70)  + " " + (stemTopY + 55) + " " + (cx - 20) + " " + (stemTopY + 80) +
    " Z";

  svg.append("path")
    .attr("d", leafLeftPath)
    .attr("fill", "#81c784")
    .attr("opacity", 0.9);

  // Hoja derecha (simétrica)
  const leafRightPath =
    "M " + (cx + 55) + " " + (stemTopY + 70) +
    " Q " + (cx + 110) + " " + (stemTopY + 25) + " " + (cx + 25) + " " + (stemTopY + 5) +
    " Q " + (cx + 70)  + " " + (stemTopY + 55) + " " + (cx + 20) + " " + (stemTopY + 80) +
    " Z";

  svg.append("path")
    .attr("d", leafRightPath)
    .attr("fill", "#81c784")
    .attr("opacity", 0.9);

  // --------- Centro de la flor ----------
  const core = svg.append("circle")
    .attr("cx", cx)
    .attr("cy", cy)
    .attr("r", coreRadius)
    .attr("fill", "#5d4037");

  svg.append("text")
    .attr("x", cx)
    .attr("y", cy + 4)
    .attr("text-anchor", "middle")
    .attr("font-size", 11)
    .attr("fill", "#ffe082")
    .attr("font-weight", "bold")
    .text(payload.region.toUpperCase());

  const petalGroup = svg.append("g");
  const labelGroup = svg.append("g");

  // --------- Escalas para meses (Tmax media) ----------
  const tMaxMonth = d3.max(payload.monthly, d => d.tmax_mean);
  const tMinMonth = d3.min(payload.monthly, d => d.tmax_mean);

  const lenScaleMonth = d3.scaleLinear()
    .domain([tMinMonth, tMaxMonth])
    .range([60, 150]);

  const colorScaleMonth = d3.scaleSequential(d3.interpolateYlOrRd)
    .domain([tMinMonth, tMaxMonth]); // amarillo claro -> rojo intenso

  // --------- Escalas para días ----------
  const tMaxDay = d3.max(payload.daily, d => d.tmax);
  const tMinDay = d3.min(payload.daily, d => d.tmax);

  const lenScaleDay = d3.scaleLinear()
    .domain([tMinDay, tMaxDay])
    .range([50, 160]);

  const colorScaleDay = d3.scaleSequential(d3.interpolateYlOrRd)
    .domain([tMinDay, tMaxDay]);

  let mode = "month";
  let currentMonth = null;

  // --------- Helper: path de un pétalo (curvado) ----------
  function petalPath(angle, innerR, outerR){{
    const spread = Math.PI / 36; // apertura del pétalo
    const a1 = angle - spread;
    const a2 = angle + spread;

    const x0 = cx + innerR * Math.cos(a1);
    const y0 = cy + innerR * Math.sin(a1);

    const x1 = cx + outerR * Math.cos(angle);
    const y1 = cy + outerR * Math.sin(angle);

    const x2 = cx + innerR * Math.cos(a2);
    const y2 = cy + innerR * Math.sin(a2);

    return `M ${{x0}} ${{y0}} Q ${{cx}} ${{cy}} ${{x1}} ${{y1}} Q ${{cx}} ${{cy}} ${{x2}} ${{y2}} Z`;
  }}

  // --------- Tooltip flotante ----------
  const tooltip = d3.select("body")
    .append("div")
    .style("position", "absolute")
    .style("pointer-events", "none")
    .style("background", "rgba(33,33,33,0.85)")
    .style("color", "#fffde7")
    .style("padding", "6px 8px")
    .style("border-radius", "6px")
    .style("font-size", "11px")
    .style("opacity", 0);

  // --------- Render vista mensual ----------
  function renderMonthView(){{
    mode = "month";
    currentMonth = null;

    const petals = petalGroup.selectAll("path.petal")
      .data(payload.monthly, d => d.month);

    const total = payload.monthly.length;
    const innerR = coreRadius + 10;

    petals.enter()
      .append("path")
      .attr("class", "petal")
      .attr("fill", d => colorScaleMonth(d.tmax_mean))
      .attr("stroke", "#fdd835")
      .attr("stroke-width", 1.2)
      .attr("opacity", 0.95)
      .attr("d", (d, i) => {{
        const angle = 2 * Math.PI * i / total - Math.PI / 2;
        const outR = lenScaleMonth(d.tmax_mean);
        return petalPath(angle, innerR, outR);
      }})
      .on("mouseover", function(event, d){{
        d3.select(this).attr("stroke-width", 2.2);
        tooltip
          .style("opacity", 1)
          .html(`<strong>${{d.month_name}}</strong><br/>
                 Tmax media: ${{d.tmax_mean.toFixed(1)}}°C<br/>
                 Días: ${{d.n_days}}`)
          .style("left", (event.pageX + 12) + "px")
          .style("top", (event.pageY - 28) + "px");
      }})
      .on("mousemove", function(event){{
        tooltip
          .style("left", (event.pageX + 12) + "px")
          .style("top", (event.pageY - 28) + "px");
      }})
      .on("mouseout", function(){{
        d3.select(this).attr("stroke-width", 1.2);
        tooltip.style("opacity", 0);
      }})
      .on("click", (event, d) => {{
        renderDayView(d.month);
        event.stopPropagation();
      }});

    petals.transition().duration(600)
      .attr("fill", d => colorScaleMonth(d.tmax_mean))
      .attr("stroke", "#fdd835")
      .attr("d", (d, i) => {{
        const angle = 2 * Math.PI * i / total - Math.PI / 2;
        const outR = lenScaleMonth(d.tmax_mean);
        return petalPath(angle, innerR, outR);
      }});

    petals.exit().remove();

    // Etiquetas con siglas de mes
    const labels = labelGroup.selectAll("text.month-label")
      .data(payload.monthly, d => d.month);

    labels.enter()
      .append("text")
      .attr("class", "month-label")
      .attr("text-anchor", "middle")
      .attr("font-size", 11)
      .attr("fill", "#424242")
      .merge(labels)
      .transition().duration(600)
      .attr("x", (d, i) => {{
        const angle = 2 * Math.PI * i / total - Math.PI / 2;
        const r = lenScaleMonth(d.tmax_mean) + 16;
        return cx + r * Math.cos(angle);
      }})
      .attr("y", (d, i) => {{
        const angle = 2 * Math.PI * i / total - Math.PI / 2;
        const r = lenScaleMonth(d.tmax_mean) + 16;
        return cy + r * Math.sin(angle);
      }})
      .text(d => d.month_name.substring(0, 3));

    labels.exit().remove();

    legendMonth();
  }}

  // --------- Render vista diaria de un mes ----------
  function renderDayView(month){{
    mode = "day";
    currentMonth = month;

    const days = payload.daily
      .filter(d => d.month === month)
      .sort((a, b) => d3.ascending(a.day, b.day));

    const n = days.length;
    const innerR = coreRadius + 10;

    const petals = petalGroup.selectAll("path.petal")
      .data(days, d => d.date_str);

    petals.enter()
      .append("path")
      .attr("class", "petal")
      .attr("fill", d => colorScaleDay(d.tmax))
      .attr("stroke", "#ffeb3b")
      .attr("stroke-width", 0.9)
      .attr("opacity", 0.96)
      .attr("d", (d, i) => {{
        const angle = 2 * Math.PI * i / n - Math.PI / 2;
        const outR = lenScaleDay(d.tmax);
        return petalPath(angle, innerR, outR);
      }})
      .on("mouseover", function(event, d){{
        d3.select(this).attr("stroke-width", 1.8);
        tooltip
          .style("opacity", 1)
          .html(`Día ${{d.day}} · ${{d.date_str}}<br/>
                 Tmax: ${{d.tmax.toFixed(1)}}°C<br/>
                 Tmin: ${{d.tmin.toFixed(1)}}°C`)
          .style("left", (event.pageX + 12) + "px")
          .style("top", (event.pageY - 28) + "px");
      }})
      .on("mousemove", function(event){{
        tooltip
          .style("left", (event.pageX + 12) + "px")
          .style("top", (event.pageY - 28) + "px");
      }})
      .on("mouseout", function(){{
        d3.select(this).attr("stroke-width", 0.9);
        tooltip.style("opacity", 0);
      }});

    petals.transition().duration(600)
      .attr("fill", d => colorScaleDay(d.tmax))
      .attr("stroke", "#ffeb3b")
      .attr("d", (d, i) => {{
        const angle = 2 * Math.PI * i / n - Math.PI / 2;
        const outR = lenScaleDay(d.tmax);
        return petalPath(angle, innerR, outR);
      }});

    petals.exit().remove();

    // Etiquetas: números de día
    const labels = labelGroup.selectAll("text.month-label")
      .data(days, d => d.date_str);

    labels.enter()
      .append("text")
      .attr("class", "month-label")
      .attr("text-anchor", "middle")
      .attr("font-size", 9)
      .attr("fill", "#455a64")
      .merge(labels)
      .transition().duration(600)
      .attr("x", (d, i) => {{
        const angle = 2 * Math.PI * i / n - Math.PI / 2;
        const r = lenScaleDay(d.tmax) + 10;
        return cx + r * Math.cos(angle);
      }})
      .attr("y", (d, i) => {{
        const angle = 2 * Math.PI * i / n - Math.PI / 2;
        const r = lenScaleDay(d.tmax) + 10;
        return cy + r * Math.sin(angle);
      }})
      .text(d => d.day);

    labels.exit().remove();

    legendDay(month);
  }}

  // --------- Leyendas ----------
  function legendMonth(){{
    svg.selectAll("g.legend").remove();
    const g = svg.append("g").attr("class", "legend");
    const x0 = 40;
    const y0 = 40;

    const gradId = "grad-month-" + hostId;
    const defs = svg.append("defs");
    const grad = defs.append("linearGradient")
      .attr("id", gradId)
      .attr("x1", "0%")
      .attr("y1", "0%")
      .attr("x2", "100%")
      .attr("y2", "0%");

    grad.append("stop")
      .attr("offset", "0%")
      .attr("stop-color", colorScaleMonth(tMinMonth));
    grad.append("stop")
      .attr("offset", "100%")
      .attr("stop-color", colorScaleMonth(tMaxMonth));

    g.append("text")
      .attr("x", x0)
      .attr("y", y0 - 8)
      .attr("font-size", 11)
      .attr("fill", "#424242")
      .text("Meses · Tmax media");

    g.append("rect")
      .attr("x", x0)
      .attr("y", y0)
      .attr("width", 120)
      .attr("height", 10)
      .attr("fill", `url(#${{gradId}})`);

    g.append("text")
      .attr("x", x0)
      .attr("y", y0 + 22)
      .attr("font-size", 10)
      .attr("fill", "#616161")
      .text(`${{tMinMonth.toFixed(1)}}°C`);

    g.append("text")
      .attr("x", x0 + 120)
      .attr("y", y0 + 22)
      .attr("text-anchor", "end")
      .attr("font-size", 10)
      .attr("fill", "#616161")
      .text(`${{tMaxMonth.toFixed(1)}}°C`);
  }}

  function legendDay(month){{
    svg.selectAll("g.legend").remove();
    const g = svg.append("g").attr("class", "legend");
    const x0 = 40;
    const y0 = 40;

    const gradId = "grad-day-" + hostId;
    const defs = svg.append("defs");
    const grad = defs.append("linearGradient")
      .attr("id", gradId)
      .attr("x1", "0%")
      .attr("y1", "0%")
      .attr("x2", "100%")
      .attr("y2", "0%");

    grad.append("stop")
      .attr("offset", "0%")
      .attr("stop-color", colorScaleDay(tMinDay));
    grad.append("stop")
      .attr("offset", "100%")
      .attr("stop-color", colorScaleDay(tMaxDay));

    const monthObj = payload.monthly.find(m => m.month === month) || {{}};
    const monthName = monthObj.month_name || ("Mes " + month);

    g.append("text")
      .attr("x", x0)
      .attr("y", y0 - 8)
      .attr("font-size", 11)
      .attr("fill", "#424242")
      .text("Días · " + monthName);

    g.append("rect")
      .attr("x", x0)
      .attr("y", y0)
      .attr("width", 120)
      .attr("height", 10)
      .attr("fill", `url(#${{gradId}})`);

    g.append("text")
      .attr("x", x0)
      .attr("y", y0 + 22)
      .attr("font-size", 10)
      .attr("fill", "#616161")
      .text(`${{tMinDay.toFixed(1)}}°C`);

    g.append("text")
      .attr("x", x0 + 120)
      .attr("y", y0 + 22)
      .attr("text-anchor", "end")
      .attr("font-size", 10)
      .attr("fill", "#616161")
      .text(`${{tMaxDay.toFixed(1)}}°C`);
  }}

  // --------- Click en el centro -> vuelve a meses ----------
  svg.on("click", function(event){{
    const [x, y] = d3.pointer(event, this);
    const dx = x - cx;
    const dy = y - cy;
    if (Math.sqrt(dx*dx + dy*dy) <= coreRadius + 6){{
      renderMonthView();
    }}
  }});

  // Primera renderización
  renderMonthView();
}})();
</script>
"""
    return HTML(html)






def show_region_weather_face(
    csv_path: str | Path,
    region: str,
    target_date: str | None = None,
    date_col: str = "time",
    region_col: str = "REGION",
    tmax_col: str = "temperature_2m_max (°C)",
) -> HTML:
    """
    Muestra un ícono grande de clima para una región:

      - temp >= 25  → sol con cara feliz (fondo amarillo/cálido)
      - 15 <= temp < 25 → nube con sol (fondo gris claro)
      - temp < 15   → nube (fondo azul frío)

    Si target_date es None, usa la última fecha disponible en el CSV
    para esa región.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"No encuentro el CSV de clima: {csv_path}")

    df = pd.read_csv(csv_path)

    # Validar columnas
    for col in (date_col, region_col, tmax_col):
        if col not in df.columns:
            raise ValueError(f"Falta la columna '{col}' en el CSV de clima.")

    # Parsear fecha y limpiar
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    # Filtro por región (case-insensitive)
    mask = df[region_col].astype(str).str.upper() == str(region).upper()
    df_reg = df[mask].copy()
    if df_reg.empty:
        raise ValueError(f"No hay registros para la región '{region}'.")

    # Definir la fecha objetivo
    if target_date is None:
        target = df_reg[date_col].max().normalize()
    else:
        target = pd.to_datetime(target_date).normalize()

    df_day = df_reg[df_reg[date_col].dt.normalize() == target].copy()
    if df_day.empty:
        raise ValueError(
            f"No hay registros para la región '{region}' en la fecha {str(target.date())}."
        )

    # Temperatura máxima promedio del día
    temp = float(df_day[tmax_col].mean())

    payload = {
        "region": str(region),
        "date": str(target.date()),
        "temp": temp,
    }

    data_json = json.dumps(payload, ensure_ascii=False, default=float)
    chart_id = f"weather-{uuid.uuid4().hex}"

    template = """
<div id="[CHART_ID]" style="width:100%; max-width:360px; margin:10px 0; font-family:system-ui;">
  <div id="[CHART_ID]-card"
       style="border:3px solid #ffca28; border-radius:16px; padding:10px; background:#fffde7; transition:background-color 0.3s ease;">
    <div id="[CHART_ID]-svg" style="width:100%; height:240px;"></div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script>
(function() {
  const payload = [DATA];
  const rootId = "[CHART_ID]";
  const host = document.getElementById(rootId + "-svg");
  const card = document.getElementById(rootId + "-card");
  if (!host) return;

  const W = host.clientWidth || 320;
  const H = 220;
  const cx = W / 2;
  const cy = H / 2 - 10;

  const svg = d3.select(host)
    .append("svg")
    .attr("width", W)
    .attr("height", H);

  const temp = +payload.temp;
  let mood = "cloud";
  if (temp >= 25) {
    mood = "sunny";        // sol feliz
  } else if (temp >= 15) {
    mood = "mixed";        // nube con sol
  } // temp < 15 → nube

  // ---------- fondo según mood ----------
  // sol (calor): amarillo cálido
  // intermedio: gris neutro
  // frío: azul frío
  let bgColor = "#fffde7";
  let borderColor = "#ffca28";

  if (mood === "sunny") {
    bgColor = "#fff8e1";     // amarillo muy claro
    borderColor = "#ffca28";
  } else if (mood === "mixed") {
    bgColor = "#eceff1";     // gris claro
    borderColor = "#b0bec5";
  } else { // cloud
    bgColor = "#e3f2fd";     // azulito frío
    borderColor = "#64b5f6";
  }

  if (card) {
    card.style.background = bgColor;
    card.style.borderColor = borderColor;
  }

  // ---------- helpers de dibujo ----------

  function drawCloud(g, cx, cy, scale) {
    const r = 18 * scale;

    g.append("circle")
      .attr("cx", cx - r)
      .attr("cy", cy)
      .attr("r", r);

    g.append("circle")
      .attr("cx", cx)
      .attr("cy", cy - r * 0.6)
      .attr("r", r * 1.15);

    g.append("circle")
      .attr("cx", cx + r)
      .attr("cy", cy)
      .attr("r", r * 0.9);

    g.append("rect")
      .attr("x", cx - 1.7 * r)
      .attr("y", cy)
      .attr("width", 3.4 * r)
      .attr("height", r)
      .attr("rx", r * 0.4);
  }

  function drawSunHappy(g, cx, cy, radius) {
    const rayR = radius + 16;

    // rayos
    for (let i = 0; i < 16; i++) {
      const angle = 2 * Math.PI * i / 16;
      const x1 = cx + radius * Math.cos(angle);
      const y1 = cy + radius * Math.sin(angle);
      const x2 = cx + rayR * Math.cos(angle);
      const y2 = cy + rayR * Math.sin(angle);
      g.append("line")
        .attr("x1", x1)
        .attr("y1", y1)
        .attr("x2", x2)
        .attr("y2", y2)
        .attr("stroke", "#ffb300")
        .attr("stroke-width", 2)
        .attr("stroke-linecap", "round");
    }

    // disco del sol (amarillo)
    g.append("circle")
      .attr("cx", cx)
      .attr("cy", cy)
      .attr("r", radius)
      .attr("fill", "#ffeb3b")
      .attr("stroke", "#ffb300")
      .attr("stroke-width", 2);

    // ojos
    g.append("circle")
      .attr("cx", cx - radius * 0.35)
      .attr("cy", cy - radius * 0.25)
      .attr("r", radius * 0.12)
      .attr("fill", "#5d4037");

    g.append("circle")
      .attr("cx", cx + radius * 0.35)
      .attr("cy", cy - radius * 0.25)
      .attr("r", radius * 0.12)
      .attr("fill", "#5d4037");

    // sonrisa
    const mouthPath =
      "M " + (cx - radius * 0.45) + " " + (cy + radius * 0.15) +
      " Q " + cx + " " + (cy + radius * 0.55) +
      " " + (cx + radius * 0.45) + " " + (cy + radius * 0.15);

    g.append("path")
      .attr("d", mouthPath)
      .attr("fill", "none")
      .attr("stroke", "#5d4037")
      .attr("stroke-width", 2)
      .attr("stroke-linecap", "round");
  }

  function drawMixed(g, cx, cy) {
    // sol pequeño detrás
    const sunG = g.append("g");
    drawSunHappy(sunG, cx - 35, cy - 20, 22);

    // nube delante
    const cloudG = g.append("g")
      .attr("fill", "#ffffff")
      .attr("stroke", "#b0bec5")
      .attr("stroke-width", 2);
    drawCloud(cloudG, cx + 5, cy + 5, 1.0);
  }

  function drawOnlyCloud(g, cx, cy) {
    const cloudG = g.append("g")
      .attr("fill", "#ffffff")
      .attr("stroke", "#b0bec5")
      .attr("stroke-width", 2);
    drawCloud(cloudG, cx, cy + 5, 1.1);
  }

  // ---------- dibujar según mood ----------

  const iconG = svg.append("g");

  if (mood === "sunny") {
    drawSunHappy(iconG, cx, cy, 40);
  } else if (mood === "mixed") {
    drawMixed(iconG, cx, cy);
  } else {
    drawOnlyCloud(iconG, cx, cy);
  }

  // ---------- textos ----------

  svg.append("text")
    .attr("x", cx)
    .attr("y", H - 46)
    .attr("text-anchor", "middle")
    .attr("font-size", 13)
    .attr("font-weight", "600")
    .attr("fill", "#424242")
    .text(payload.region + " · " + payload.date);

  svg.append("text")
    .attr("x", cx)
    .attr("y", H - 26)
    .attr("text-anchor", "middle")
    .attr("font-size", 12)
    .attr("fill", "#424242")
    .text(temp.toFixed(1) + " °C");
})();
</script>
"""
    html = template.replace("[CHART_ID]", chart_id).replace("[DATA]", data_json)
    return HTML(html)





def show_region_footprint(
    csv_path: str | Path,
    region: str,
    region_col: str = "Región",
    emission_level_col: str = "Nivel de Emisión",
    source_col: str = "Fuente Principal de CO2",
    context_col: str = "Dato Clave / Contexto Útil",
) -> HTML:
    """
    Visualización de huella de carbono por región (footprint):

      - El tamaño del *footprint* es proporcional al nivel de emisión (1–5).
      - El color cambia según el nivel:
            5 → rojo (Muy Alto)
            4 → naranja (Alto)
            3 → amarillo (Medio)
            2 → verde (Bajo)
            1 → azul (Muy Bajo)
      - Debajo se muestran:
            · Fuente principal de CO₂
            · Dato clave / contexto

    Soporta tanto .csv como .xlsx (Excel).
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"No encuentro el archivo de footprint: {csv_path}")

    # --- Cargar según extensión (.csv o .xlsx) ---
    suffix = csv_path.suffix.lower()
    if suffix in [".xlsx", ".xls"]:
        df = pd.read_excel(csv_path)
    else:
        df = pd.read_csv(csv_path)

    # Verificamos columnas básicas
    for col in (region_col, emission_level_col, source_col, context_col):
        if col not in df.columns:
            raise ValueError(
                f"Falta la columna '{col}' en el archivo. "
                f"Columnas disponibles: {list(df.columns)}"
            )

    # Normalizar región para comparar (reusa _normalize_region si existe)
    try:
        norm_func = _normalize_region  # definida más arriba en este módulo
    except NameError:
        def norm_func(x):
            return str(x).strip().upper()

    df["_norm_region"] = df[region_col].map(norm_func)
    target_norm = norm_func(region)

    sub = df[df["_norm_region"] == target_norm].copy()
    if sub.empty:
        raise ValueError(
            f"No encontré filas para la región '{region}'. "
            f"Asegúrate de que el nombre coincide con la columna '{region_col}'."
        )

    row = sub.iloc[0]

    raw_level = str(row[emission_level_col])

    # Extraer nivel numérico (1–5) desde textos tipo "🔴 5 - Muy Alto"
    m = re.search(r"([1-5])", raw_level)
    if m:
        level = int(m.group(1))
    else:
        level = 3  # fallback neutro

    level_labels = {
        1: "Muy Bajo",
        2: "Bajo",
        3: "Medio",
        4: "Alto",
        5: "Muy Alto",
    }
    level_label = level_labels.get(level, "Medio")

    fuente = str(row[source_col])
    contexto = str(row[context_col])
    region_label = str(row[region_col])

    payload = {
        "region": region_label,
        "level": level,
        "level_label": level_label,
        "raw_level": raw_level,
        "source": fuente,
        "context": contexto,
    }

    data_json = json.dumps(payload, ensure_ascii=False)
    chart_id = f"footprint-{uuid.uuid4().hex}"

    template = """
<div id="[CHART_ID]" style="width:100%; max-width:480px; margin:10px 0; font-family:system-ui;">
  <div id="[CHART_ID]-card"
       style="border:2px solid #cfd8dc; border-radius:18px; padding:12px 14px; background:#fafafa;
              box-shadow:0 3px 10px rgba(0,0,0,0.06); transition:background-color 0.3s ease, border-color 0.3s ease;">
    <!-- Título y subtítulo fuera del SVG para no tapar el pie -->
    <div style="text-align:center; margin-bottom:6px;">
      <div id="[CHART_ID]-title"
           style="font-size:14px; font-weight:600; color:#263238; line-height:1.3;"></div>
      <div style="font-size:11px; color:#546e7a;">
        Huella de emisiones de CO₂ (footprint)
      </div>
    </div>

    <div id="[CHART_ID]-svg"
         style="width:100%; height:230px; display:flex; align-items:center; justify-content:center;"></div>

    <div style="margin-top:10px; font-size:12px; line-height:1.45;">
      <div><strong>Fuente principal de CO₂:</strong> <span id="[CHART_ID]-source"></span></div>
      <div style="margin-top:4px;"><strong>Dato clave:</strong> <span id="[CHART_ID]-context"></span></div>
    </div>
  </div>

  <div id="[CHART_ID]-legend"
       style="margin-top:10px; font-size:11px; color:#455a64; padding:6px 8px; background:#f5f5f5; border-radius:10px;">
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script>
(function() {
  const payload = [DATA];
  const rootId = "[CHART_ID]";

  const host = document.getElementById(rootId + "-svg");
  const card = document.getElementById(rootId + "-card");
  const legendHost = document.getElementById(rootId + "-legend");
  const sourceSpan = document.getElementById(rootId + "-source");
  const contextSpan = document.getElementById(rootId + "-context");
  const titleDiv = document.getElementById(rootId + "-title");

  if (!host || !card) return;

  const W = host.clientWidth || 360;
  const H = 230;                // <- un poco más alto
  const cx = W / 2;
  const cy = H / 2 + 5;         // <- centro ligeramente más abajo

  const level = +payload.level || 3;

  // ----------------- Colores y escala por nivel -----------------
  const colorByLevel = {
    1: "#1e88e5",  // azul
    2: "#43a047",  // verde
    3: "#fbc02d",  // amarillo
    4: "#fb8c00",  // naranja
    5: "#e53935",  // rojo
  };
  const bgByLevel = {
    1: "#e3f2fd",
    2: "#e8f5e9",
    3: "#fffde7",
    4: "#fff3e0",
    5: "#ffebee",
  };
  const borderByLevel = {
    1: "#64b5f6",
    2: "#81c784",
    3: "#ffe082",
    4: "#ffb74d",
    5: "#ef5350",
  };

  const color = colorByLevel[level] || "#fbc02d";
  const bgColor = bgByLevel[level] || "#fffde7";
  const borderColor = borderByLevel[level] || "#ffe082";

  if (card) {
    card.style.background = bgColor;
    card.style.borderColor = borderColor;
  }

  // Escala ajustada para que el pie nunca se recorte
  const sizeScale = d3.scaleLinear().domain([1, 5]).range([0.6, 1.2]);
  const s = sizeScale(level);

  // ----------------- SVG y gradiente para efecto "3D" -----------------
  const svg = d3.select(host)
    .append("svg")
    .attr("width", W)
    .attr("height", H);

  const defs = svg.append("defs");

  const gradId = rootId + "-foot-grad";
  const grad = defs.append("radialGradient")
    .attr("id", gradId)
    .attr("cx", "30%")
    .attr("cy", "20%")
    .attr("r", "70%");

  grad.append("stop").attr("offset", "0%").attr("stop-color", d3.color(color).brighter(1.2));
  grad.append("stop").attr("offset", "60%").attr("stop-color", color);
  grad.append("stop").attr("offset", "100%").attr("stop-color", d3.color(color).darker(0.7));

  // Sombra bajo el pie (ajustada también)
  svg.append("ellipse")
    .attr("cx", cx + 18 * s)
    .attr("cy", cy + 52 * s)
    .attr("rx", 55 * s)
    .attr("ry", 18 * s)
    .attr("fill", "rgba(55,71,79,0.18)");

  const g = svg.append("g")
    .attr("transform", `translate(${cx},${cy})`);

  // ----------------- Forma del pie más orgánica -----------------
  function drawFootprint(g, scale) {
    const k = scale;

    const solePath = `
      M ${0 * k} ${-70 * k}
      C ${25 * k} ${-72 * k}, ${38 * k} ${-48 * k}, ${32 * k} ${-22 * k}
      C ${30 * k} ${-8 * k}, ${26 * k} ${10 * k}, ${18 * k} ${28 * k}
      C ${8 * k} ${48 * k}, ${-10 * k} ${60 * k}, ${-30 * k} ${55 * k}
      C ${-45 * k} ${50 * k}, ${-52 * k} ${32 * k}, ${-48 * k} ${10 * k}
      C ${-44 * k} ${-14 * k}, ${-35 * k} ${-42 * k}, ${-20 * k} ${-60 * k}
      C ${-12 * k} ${-70 * k}, ${-4 * k} ${-71 * k}, ${0 * k} ${-70 * k}
      Z
    `;

    g.append("path")
      .attr("d", solePath)
      .attr("fill", `url(#${gradId})`)
      .attr("stroke", "#37474f")
      .attr("stroke-width", 2);

    const toeBaseY = -76 * k;
    const toeR = 10 * k;
    const toes = [
      { x: -24 * k, y: toeBaseY + 4 * k, r: toeR * 0.8 },
      { x: -10 * k, y: toeBaseY,         r: toeR * 0.95 },
      { x:  6 * k,  y: toeBaseY - 2 * k, r: toeR },
      { x: 20 * k,  y: toeBaseY + 1 * k, r: toeR * 0.9 },
      { x: 32 * k,  y: toeBaseY + 6 * k, r: toeR * 0.8 },
    ];

    toes.forEach(t => {
      g.append("circle")
        .attr("cx", t.x)
        .attr("cy", t.y)
        .attr("r", t.r)
        .attr("fill", `url(#${gradId})`)
        .attr("stroke", "#37474f")
        .attr("stroke-width", 1.5);
    });
  }

  drawFootprint(g, s);

  // ----------------- Título y textos -----------------
  if (titleDiv) {
    titleDiv.textContent = `${payload.region.toUpperCase()} · Nivel ${payload.level} – ${payload.level_label}`;
  }

  if (sourceSpan) {
    sourceSpan.textContent = payload.source || "–";
  }
  if (contextSpan) {
    contextSpan.textContent = payload.context || "–";
  }

  // ----------------- Leyenda clara -----------------
  if (legendHost) {
    legendHost.innerHTML = "";

    const levels = [1, 2, 3, 4, 5];
    const labels = {
      1: "Muy Bajo",
      2: "Bajo",
      3: "Medio",
      4: "Alto",
      5: "Muy Alto",
    };

    const legendSvg = d3.select(legendHost)
      .append("svg")
      .attr("width", W)
      .attr("height", 70);

    legendSvg.append("text")
      .attr("x", W / 2)
      .attr("y", 14)
      .attr("text-anchor", "middle")
      .attr("font-size", 11)
      .attr("fill", "#37474f")
      .text("Leyenda · Nivel de emisión regional");

    const lw = W - 40;
    const startX = 20;
    const step = lw / (levels.length - 1);

    const sizeScaleLeg = d3.scaleLinear().domain([1, 5]).range([0.4, 0.85]);

    levels.forEach((lv, i) => {
      const lx = startX + step * i;
      const ly = 40;
      const sc = sizeScaleLeg(lv);
      const col = colorByLevel[lv];

      const defId = rootId + "-leg-grad-" + lv;
      const gdefs = legendSvg.append("defs");
      const lg = gdefs.append("radialGradient")
        .attr("id", defId)
        .attr("cx", "30%")
        .attr("cy", "20%")
        .attr("r", "70%");
      lg.append("stop").attr("offset", "0%").attr("stop-color", d3.color(col).brighter(1.1));
      lg.append("stop").attr("offset", "60%").attr("stop-color", col);
      lg.append("stop").attr("offset", "100%").attr("stop-color", d3.color(col).darker(0.6));

      const gFoot = legendSvg.append("g")
        .attr("transform", `translate(${lx},${ly})`);

      const soleSmall = `
        M 0 ${-18*sc}
        C ${7*sc} ${-19*sc}, ${11*sc} ${-13*sc}, ${9*sc} ${-6*sc}
        C ${8*sc} ${-2*sc}, ${7*sc} ${3*sc}, ${5*sc} ${8*sc}
        C ${2*sc} ${14*sc}, ${-4*sc} ${17*sc}, ${-9*sc} ${16*sc}
        C ${-13*sc} ${15*sc}, ${-15*sc} ${9*sc}, ${-14*sc} ${3*sc}
        C ${-13*sc} ${-4*sc}, ${-10*sc} ${-12*sc}, ${-6*sc} ${-17*sc}
        C ${-4*sc} ${-19*sc}, ${-1*sc} ${-19*sc}, 0 ${-18*sc}
        Z
      `;
      gFoot.append("path")
        .attr("d", soleSmall)
        .attr("fill", `url(#${defId})`)
        .attr("stroke", "#37474f")
        .attr("stroke-width", 1);

      legendSvg.append("text")
        .attr("x", lx)
        .attr("y", 62)
        .attr("text-anchor", "middle")
        .attr("font-size", 10)
        .attr("fill", "#37474f")
        .text(`${lv} ${labels[lv]}`);
    });
  }
})();
</script>
"""
    html = template.replace("[CHART_ID]", chart_id).replace("[DATA]", data_json)
    return HTML(html)