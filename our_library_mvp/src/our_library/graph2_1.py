# src/our_library/graph.py
import json, uuid, math, base64
from datetime import datetime 
from pathlib import Path
from IPython.display import HTML
# mylib/dashboard.py
from flask import Flask, request, jsonify
from threading import Thread

# en graph2_1.py (y exportar en __init__.py)

# ============================================================
#  Colab / Flask bridge for JS → Python (update_node)
# ============================================================

try:
    from google.colab import output as _colab_output
    _IN_COLAB = True
except Exception:  # pragma: no cover
    _IN_COLAB = False

global_node_ = None
global_clicks_ = []
global_click_history_ = []
app = Flask(__name__)


def enable_colab_bridge():
    """
    Registra el callback JS→Python en Colab para que el dashboard
    pueda enviar el nodo clicado a Python.
    """
    if not _IN_COLAB:
        return False

    def _cb(click_data):
        global global_node_, global_clicks_, global_click_history_  # <-- AÑADIR global_click_history_
        global_node_ = click_data
        
        # Agregar timestamp si no viene
        if "__ts" not in click_data:
            click_data["__ts"] = datetime.now().isoformat()
        
        global_clicks_.append(global_node_)
        global_click_history_.append(click_data)  # <-- AÑADIR esta línea
        
        print(f"Click capturado desde {click_data.get('__src', 'unknown')}: {click_data.get('id', 'unknown')}")
        
        return {"status": "ok", "received": click_data}

    _colab_output.register_callback("ourlib.update_node", _cb)
    return True



@app.route("/update_node", methods=["POST"])
def update_node():
    """Endpoint HTTP para que el JS notifique a Python el nodo clicado."""
    global global_node_, global_clicks_, global_click_history_  # <-- AÑADIR global_click_history_
    data = request.get_json() or {}
    click_data = data.get("node", {})
    
    global_node_ = click_data
    
    # Agregar timestamp si no viene
    if "__ts" not in click_data:
        click_data["__ts"] = datetime.now().isoformat()
    
    if global_node_ is not None:
        global_clicks_.append(global_node_)
        global_click_history_.append(click_data)  # <-- AÑADIR esta línea
    
    print(f"Click recibido via HTTP desde {click_data.get('__src', 'unknown')}: {click_data.get('id', 'unknown')}")
    
    return jsonify({"status": "ok", "node": global_node_})

def start_server(port: int = 5000):
    """
    Levanta un pequeño servidor Flask en un thread aparte para que
    el JS del notebook pueda hacer POST a /update_node.
    """
    thread = Thread(
        target=lambda: app.run(port=port, debug=False, use_reloader=False)
    )
    thread.daemon = True
    thread.start()

# ============================================================
#  Funciones para obtener el historial de clicks
# ============================================================

def get_current_node():
    """Devuelve el último nodo recibido desde JS (o None)."""
    return global_node_

def get_click_history(clear: bool = False):
    """Devuelve el historial completo de clicks con metadata."""
    global global_click_history_
    hist = list(global_click_history_)
    if clear:
        global_click_history_.clear()
    return hist

def get_simple_click_history(clear: bool = False):
    """Devuelve solo los nodos clicados (compatibilidad hacia atrás)."""
    global global_clicks_
    hist = list(global_clicks_)
    if clear:
        global_clicks_.clear()
    return hist

def clear_click_history():
    """Limpia el historial de clics."""
    global global_clicks_, global_click_history_
    global_clicks_.clear()
    global_click_history_.clear()

def get_clicks_by_source(source: str = None):
    """Filtra el historial por fuente (graph, map, score, etc.)"""
    history = get_click_history()
    if source:
        return [click for click in history if click.get('__src') == source]
    return history

def print_click_summary():
    """Imprime un resumen del historial de clicks."""
    history = get_click_history()
    if not history:
        print("No hay clicks registrados")
        return
    
    print(f"\n=== RESUMEN DE CLICKS ({len(history)} total) ===")
    
    by_source = {}
    for click in history:
        source = click.get('__src', 'unknown')
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(click)
    
    for source, clicks in by_source.items():
        print(f"\n{source.upper()}: {len(clicks)} clicks")
        for click in clicks[-5:]:  # últimos 5 de cada fuente
            node_id = click.get('id', 'unknown')
            name = click.get('name', 'sin nombre')
            timestamp = click.get('timestamp', 'sin timestamp')
            print(f"  - {node_id}: {name} ({timestamp})")

def print_click_summary():
    """Imprime un resumen del historial de clicks como DataFrame."""
    history = get_click_history()
    if not history:
        print("No hay clicks registrados")
        return None
    
    # Crear DataFrame
    import pandas as pd
    
    # Preparar datos para el DataFrame
    data = []
    for click in history:
        row = {
            'timestamp': click.get('__ts', ''),
            'source': click.get('__src', 'unknown'),
            'chart': click.get('__chart', 'unknown'),
            'id': click.get('id', ''),
            'name': click.get('name', ''),
            'region': click.get('region', ''),
            'SCORE': click.get('SCORE', None),
            'interaction': click.get('__interaction', 'click')
        }
        
        # Para brush selections, mostrar información adicional
        if click.get('__interaction') == 'brush':
            row['selected_count'] = click.get('selected_count', 0)
            row['selected_ids'] = str(click.get('selected_ids', []))[:50] + "..." if len(str(click.get('selected_ids', []))) > 50 else str(click.get('selected_ids', []))
        
        data.append(row)
    
    df = pd.DataFrame(data)
    
    # Mostrar resumen
    print(f"=== RESUMEN DE CLICKS ({len(history)} total) ===")
    print(f"Por gráfico:")
    print(df['source'].value_counts())
    
    print(f"\n=== DATAFRAME COMPLETO ===")
    # Mostrar todas las filas sin truncar
    with pd.option_context('display.max_rows', None, 
                          'display.max_columns', None, 
                          'display.width', None,
                          'display.max_colwidth', 50):
        print(df)
    
    return df

# Función adicional para obtener directamente como DataFrame
def get_click_dataframe():
    """Devuelve el historial de clicks como DataFrame de pandas."""
    history = get_click_history()
    if not history:
        print("No hay clicks registrados")
        return None
    
    import pandas as pd
    
    data = []
    for click in history:
        row = {
            'timestamp': click.get('__ts', ''),
            'source': click.get('__src', 'unknown'),
            'chart': click.get('__chart', 'unknown'),
            'id': click.get('id', ''),
            'name': click.get('name', ''),
            'region': click.get('region', ''),
            'SCORE': click.get('SCORE', None),
            'lat': click.get('lat', None),
            'lon': click.get('lon', None),
            'interaction': click.get('__interaction', 'click'),
            'selected_count': click.get('selected_count', None)
        }
        data.append(row)
    
    df = pd.DataFrame(data)
    return df


# ============================================================
# python -> js


def show_click_timecurve(click_df, width: int = 900, height: int = 420):
    """
    Visualiza el historial de clicks como una "time curve":

      - Cada fila del DataFrame es un nodo.
      - El orden inicial es por timestamp (temporal).
      - Color de nodo según `source` (force/map/score/...).
      - Línea suave (curva) que conecta todos los puntos en orden temporal.
      - Itinerario manual:
          * Click en un nodo: lo agrega/quita del itinerario.
          * El itinerario se dibuja como otra curva más gruesa.
          * Panel inferior con la lista ordenada del itinerario.
          * Botón para limpiar el itinerario.
    """
    import pandas as pd

    if click_df is None or len(click_df) == 0:
        return HTML("<em>No hay clicks en el historial para dibujar la time curve.</em>")

    df = click_df.copy()

    # Aseguramos columnas mínimas
    for col in ["timestamp", "source", "chart", "id", "name", "region"]:
        if col not in df.columns:
            df[col] = ""

    # Parsear timestamp para ordenar (si se puede)
    if "timestamp" in df.columns:
        df["_ts"] = pd.to_datetime(df["timestamp"], errors="coerce")
    else:
        df["_ts"] = pd.NaT

    # Ordenar:
    # - si hay algún timestamp válido → ordenar por tiempo
    # - si no → usamos el índice tal cual
    if df["_ts"].notna().any():
        df = df.sort_values("_ts").reset_index(drop=True)
    else:
        df = df.reset_index(drop=True)

    # _order = posición en la secuencia (0, 1, 2, ...)
    df["_order"] = df.index.astype(float)

    # Asegurar SCORE como numérico (para tooltips)
    if "SCORE" in df.columns:
        df["SCORE"] = pd.to_numeric(df["SCORE"], errors="coerce")
    else:
        df["SCORE"] = None

    # Build records for JS
    records = df[
        [
            "timestamp",
            "source",
            "chart",
            "id",
            "name",
            "region",
            "SCORE",
            "_order",
        ]
    ].to_dict(orient="records")

    data_json = json.dumps(records, default=str, ensure_ascii=False)
    chart_id = f"timecurve-{uuid.uuid4().hex}"

    html = f"""
<div id="{chart_id}" style="width:100%; max-width:{width}px; margin:10px 0; font-family:system-ui;">
  <div style="border:2px solid #cfd8dc; border-radius:16px; padding:10px 12px; background:#fafafa;
              box-shadow:0 2px 8px rgba(0,0,0,0.05);">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
      <div>
        <div style="font-size:14px; font-weight:600; color:#263238;">Time curve · Itinerario interactivo</div>
        <div style="font-size:11px; color:#607d8b;">
          Cada punto es un click en el dashboard (orden temporal). Construye tu itinerario haciendo click sobre los puntos.
        </div>
      </div>
      <button id="{chart_id}-clear"
              style="font-size:11px; padding:4px 8px; border-radius:10px; border:1px solid #b0bec5;
                     background:#eceff1; cursor:pointer;">
        Limpiar itinerario
      </button>
    </div>
    <div id="{chart_id}-svg" style="width:100%; height:{height}px;"></div>
  </div>

  <div id="{chart_id}-itinerary"
       style="margin-top:8px; font-size:11px; color:#37474f; background:#f5f5f5; border-radius:10px; padding:6px 8px;">
    <strong>Itinerario:</strong> <span id="{chart_id}-itinerary-text"><em>haz click en los puntos para construirlo</em></span>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script>
(function() {{
  const data = {data_json};
  const rootId = "{chart_id}";
  const svgHost = document.getElementById(rootId + "-svg");
  const clearBtn = document.getElementById(rootId + "-clear");
  const itinBox = document.getElementById(rootId + "-itinerary-text");

  if (!svgHost) return;

  const width = svgHost.clientWidth || {width};
  const height = {height};
  const margin = {{ top: 24, right: 24, bottom: 28, left: 24 }};
  const innerWidth  = width  - margin.left - margin.right;
  const innerHeight = height - margin.top  - margin.bottom;

  const svg = d3.select(svgHost)
    .append("svg")
    .attr("width", width)
    .attr("height", height);

  const g = svg.append("g")
    .attr("transform", `translate(${{margin.left}},${{margin.top}})`);

  // Orden temporal
  const n = data.length;
  const x = d3.scaleLinear()
    .domain(d3.extent(data, d => +d._order))
    .range([0, innerWidth]);

  const yBase = innerHeight / 2;

  // Pequeño jitter vertical según source para que no sea línea totalmente recta
  const sources = Array.from(new Set(data.map(d => d.source || "other")));
  const sourceIndex = new Map(sources.map((s, i) => [s, i]));
  const sourceCount = Math.max(1, sources.length);
  const yOffsetScale = d3.scaleLinear()
    .domain([0, sourceCount - 1])
    .range([-innerHeight * 0.2, innerHeight * 0.2]);

  data.forEach((d, i) => {{
    const idx = sourceIndex.get(d.source || "other") ?? 0;
    d.x = x(+d._order);
    d.y = yBase + yOffsetScale(idx) * 0.4;  // jitter suave
    d.idx = i;
  }});

  // Colores por source
  const color = d3.scaleOrdinal()
    .domain(sources)
    .range(["#1e88e5","#43a047","#fb8c00","#8e24aa","#f4511e","#6d4c41","#00897b"]);

  // ----------------- Línea base (time curve) -----------------
  const line = d3.line()
    .x(d => d.x)
    .y(d => d.y)
    .curve(d3.curveCatmullRom.alpha(0.8));

  g.append("path")
    .datum(data)
    .attr("fill", "none")
    .attr("stroke", "#b0bec5")
    .attr("stroke-width", 2)
    .attr("stroke-opacity", 0.8)
    .attr("d", line);

  // ----------------- Estado del itinerario -----------------
  let itinerary = [];  // array de índices (idx)

  function updateItineraryText() {{
    if (!itinBox) return;
    if (!itinerary.length) {{
      itinBox.innerHTML = "<em>haz click en los puntos para construirlo</em>";
      return;
    }}
    const items = itinerary.map((idx, i) => {{
      const d = data[idx];
      const name = d.name || d.id || ("Punto " + (idx+1));
      const region = d.region || "";
      return `<span style="margin-right:6px;"><strong>${{i+1}}.</strong> ${{name}}${{region ? " · " + region : ""}}</span>`;
    }}).join("");
    itinBox.innerHTML = items;
  }}

  function toggleInItinerary(d) {{
    const pos = itinerary.indexOf(d.idx);
    if (pos > -1) {{
      itinerary.splice(pos, 1);
    }} else {{
      itinerary.push(d.idx);
    }}
    updateItinerary();
  }}

  function clearItinerary() {{
    itinerary = [];
    updateItinerary();
  }}

  // ----------------- Curva de itinerario -----------------
  const itinLayer = g.append("g").attr("class", "itin-layer");

  function updateItinerary() {{
    updateItineraryText();

    const itinNodes = itinerary.map(idx => data[idx]);

    // actualizar estilo de nodos (seleccionados vs no)
    nodeSel
      .attr("stroke-width", d => itinerary.includes(d.idx) ? 2.8 : 1.4)
      .attr("stroke", d => itinerary.includes(d.idx) ? "#263238" : "#ffffff")
      .attr("opacity", d => itinerary.length ? (itinerary.includes(d.idx) ? 1.0 : 0.35) : 1.0);

    // actualizar curva
    const sel = itinLayer.selectAll("path.itin")
      .data(itinNodes.length >= 2 ? [itinNodes] : []);

    sel.join(
      enter => enter
        .append("path")
        .attr("class", "itin")
        .attr("fill", "none")
        .attr("stroke", "#d32f2f")
        .attr("stroke-width", 3)
        .attr("stroke-opacity", 0.9)
        .attr("d", line),
      update => update
        .transition().duration(300)
        .attr("d", line),
      exit => exit.remove()
    );
  }}

  // ----------------- Nodos -----------------
  const nodeG = g.append("g").attr("class", "nodes");

  const nodeSel = nodeG.selectAll("circle.node")
    .data(data)
    .join("circle")
    .attr("class", "node")
    .attr("cx", d => d.x)
    .attr("cy", d => d.y)
    .attr("r", 6)
    .attr("fill", d => color(d.source || "other"))
    .attr("stroke", "#ffffff")
    .attr("stroke-width", 1.4)
    .style("cursor", "pointer");

  // tooltips sencillos con <title>
  nodeSel.append("title")
    .text(d => {{
      const t = d.timestamp || "";
      const name = d.name || d.id || "";
      const src = d.source || "";
      const rg = d.region || "";
      const score = (d.SCORE != null && !isNaN(d.SCORE)) ? " · SCORE " + (+d.SCORE).toFixed(2) : "";
      return `${{t}}\\n${{name}}${{rg ? " · " + rg : ""}}\\nsource: ${{src}}${{score}}`;
    }});

  nodeSel.on("click", (event, d) => {{
    toggleInItinerary(d);
    event.stopPropagation();
  }});

  // ----------------- Botón limpiar -----------------
  if (clearBtn) {{
    clearBtn.addEventListener("click", () => {{
      clearItinerary();
    }});
  }}

  svg.on("click", function(event) {{
    const target = event.target;
    if (target.tagName.toLowerCase() === "svg") {{
      // opcional: clearItinerary();
    }}
  }});

  // Inicializar
  updateItinerary();
}})();
</script>
"""
    return HTML(html)



def show_click_timecurve_from_history(width: int = 900, height: int = 420):
    """
    Atajo: toma el historial global de clicks (get_click_dataframe)
    y dibuja la time curve sin que tengas que pasar el DataFrame a mano.
    """
    df = get_click_dataframe()
    return show_click_timecurve(df, width=width, height=height)








# ============================================================
#  Main dashboard: Graph + Map + SCORE bars + Selection panel
# ============================================================


def show_dashboard_map_force_radar_linked(
    nodes, links, width: int = 1200, height: int = 900, grid_cols: int = 2, grid_rows: int = 2
):
    """
    Dashboard linkeado para recomendaciones de turismo:

    - Graph (force) con top-3 aristas de similaridad por nodo.
    - Map de Perú con puntos (lat, lon) y brush de selección.
    - Panel de SCORE (barras horizontales por recomendación).
    - Panel de Selection con la lista de recursos seleccionados.
    - En cada click se manda un payload a Python (Colab o Flask).

    Espera que cada nodo tenga al menos:
      { "id", "name", "region", "lat", "lon", "SCORE", "want_to_go" }

    Y cada enlace:
      { "source", "target", "similarity" }.
    """
    dash_id = "dash-" + uuid.uuid4().hex
    force_id = "force-" + uuid.uuid4().hex
    map_id = "map-" + uuid.uuid4().hex
    radar_id = "radar-" + uuid.uuid4().hex  # ahora SCORE bars
    info_id = "info-" + uuid.uuid4().hex

    data_json = json.dumps({"nodes": nodes, "links": links}, default=str)

    # ---- Filtramos Top-3 conexiones por nodo para el Graph ----
    filtered_links = []
    for node in nodes:
        nid = node.get("id")
        outgoing = [l for l in links if l.get("source") == nid]
        incoming = [l for l in links if l.get("target") == nid]
        top3 = sorted(
            outgoing + incoming,
            key=lambda x: x.get("similarity", 0),
            reverse=True,
        )[:3]
        filtered_links.extend(top3)

    # Quitamos duplicados (pueden salir si la arista aparece desde source y target)
    filtered_links = list(
        {json.dumps(l, sort_keys=True): l for l in filtered_links}.values()
    )

    html = f"""
<div id="{dash_id}" style="
  width:{width}px; font-family:system-ui;
  display:grid; grid-template-columns:repeat({grid_cols}, 1fr);
  grid-template-rows:repeat({grid_rows}, 1fr);
  gap:18px; align-items:start;">

  <!-- Graph -->
  <div style="border:3px solid #d32f2f; border-radius:12px; padding:10px; min-height:450px;">
    <h3 style="margin:0 0 6px;">Graph</h3>
    <div style="font-size:11px; margin-bottom:5px; display:flex; flex-direction:column; align-items:flex-start; gap:4px;">
      <span>Conexiones: Top 3. <strong>Grosor y color</strong> = Nivel de similaridad</span>
      <span style="font-size:10px; white-space:nowrap;">(Menos
        <span style="display:inline-block; width:30px; height:5px; background:linear-gradient(to right, #f7fbff, #08306b); border:1px solid #ccc; vertical-align:middle;"></span>
      Más)</span>
    </div>
    <div id="{force_id}" style="width:100%; height:450px; border:1px solid #ccc;"></div>
  </div>

  <!-- Map -->
  <div style="border:3px solid #2e7d32; border-radius:12px; padding:10px; min-height:450px;">
    <h3 style="margin:0 0 6px;">Map</h3>
    <div id="{map_id}" style="width:100%; height:450px; border:1px solid #ccc;"></div>
    <div style="display:flex; gap:15px; margin-top:10px; font-size:12px;">
      <span><span style="color:#fbc02d; font-size:1.2em; -webkit-text-stroke: 1px #ccc;">●</span> Costa</span>
      <span><span style="color:#8D6E63; font-size:1.2em; -webkit-text-stroke: 1px #ccc;">●</span> Sierra</span>
      <span><span style="color:#4CAF50; font-size:1.2em; -webkit-text-stroke: 1px #ccc;">●</span> Selva</span>
    </div>
  </div>

  <!-- SCORE bars -->
  <div style="border:3px solid #1976d2; border-radius:12px; padding:10px; min-height:420px;">
    <h3 style="margin:0 0 6px;">Ranking · SCORE</h3>
    <div id="{radar_id}" style="width:100%; height:420px; border:1px solid #ccc;"></div>
    <div style="margin-top:10px;">
      <p style="font-size:12px;">
        Barra horizontal = <strong>SCORE</strong> de recomendación ·
        Color = región geográfica (igual que en el mapa)
      </p>
    </div>
  </div>

  <!-- Selection -->
  <div style="border:3px solid #7b1fa2; border-radius:12px; padding:10px; min-height:420px;">
    <h3 style="margin:0 0 6px;">Selection</h3>
    <div id="{info_id}" style="min-height:420px; background:#f8f9fa; padding:10px; overflow:auto;">
      <em>Haz click en el Graph, en las barras de SCORE o usa el brush en el mapa…</em>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script src="https://cdn.jsdelivr.net/npm/topojson-client@3"></script>

<script>
(function() {{
  const data = {data_json};
  const filteredLinks = {json.dumps(filtered_links, default=str)};

  // =================== JS → Python bridge ====================
  function _sendToPython(payload) {{
    try {{
      const inColab = !!(window.google && google.colab && google.colab.kernel && google.colab.kernel.invokeFunction);
      if (inColab) {{
        google.colab.kernel.invokeFunction('ourlib.update_node', [payload], {{}})
          .catch(err => console.warn('Colab bridge error:', err));
      }} else {{
        const body = JSON.stringify({{ node: payload }});
        fetch('http://127.0.0.1:5000/update_node', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body
        }}).catch(() => {{
          fetch('/proxy/5000/update_node', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body
          }}).catch(err => console.warn('Fetch bridge failed:', err));
        }});
      }}
    }} catch(e) {{
      console.warn('sendToPython failed:', e);
    }}
  }}
  const sendToPython = _sendToPython;
  window.sendToPython = _sendToPython;

  // =================== Estado compartido =====================
  const bus   = new EventTarget();
  const state = {{ selected: [] }};  // array para preservar orden
  const byId  = new Map((data.nodes || []).map(d => [String(d.id), d]));

  // Región → Costa/Sierra/Selva
  const zoneMap = {{
    // Costa
    "LIMA":       {{ zone: "Costa",  scale: d3.scaleSequential(d3.interpolateRgb("#fff9c4", "#fbc02d")).domain([0,1]) }},
    "ICA":        {{ zone: "Costa",  scale: d3.scaleSequential(d3.interpolateRgb("#fff9c4", "#fbc02d")).domain([0,1]) }},
    "LALIBERTAD": {{ zone: "Costa",  scale: d3.scaleSequential(d3.interpolateRgb("#fff9c4", "#fbc02d")).domain([0,1]) }},
    "LAMBAYEQUE": {{ zone: "Costa",  scale: d3.scaleSequential(d3.interpolateRgb("#fff9c4", "#fbc02d")).domain([0,1]) }},
    "PIURA":      {{ zone: "Costa",  scale: d3.scaleSequential(d3.interpolateRgb("#fff9c4", "#fbc02d")).domain([0,1]) }},
    // Sierra
    "ANCASH":     {{ zone: "Sierra", scale: d3.scaleSequential(d3.interpolateRgb("#d7ccc8", "#8D6E63")).domain([0,1]) }},
    "AREQUIPA":   {{ zone: "Sierra", scale: d3.scaleSequential(d3.interpolateRgb("#d7ccc8", "#8D6E63")).domain([0,1]) }},
    "PUNO":       {{ zone: "Sierra", scale: d3.scaleSequential(d3.interpolateRgb("#d7ccc8", "#8D6E63")).domain([0,1]) }},
    "CUSCO":      {{ zone: "Sierra", scale: d3.scaleSequential(d3.interpolateRgb("#d7ccc8", "#8D6E63")).domain([0,1]) }},
    // Selva
    "LORETO":       {{ zone: "Selva", scale: d3.scaleSequential(d3.interpolateRgb("#c8e6c9", "#4CAF50")).domain([0,1]) }},
    "AMAZONAS":     {{ zone: "Selva", scale: d3.scaleSequential(d3.interpolateRgb("#c8e6c9", "#4CAF50")).domain([0,1]) }},
    "MADREDEDIOS":  {{ zone: "Selva", scale: d3.scaleSequential(d3.interpolateRgb("#c8e6c9", "#4CAF50")).domain([0,1]) }},
    // Fallback
    "DEFAULT":    {{ zone: "Other", scale: d3.scaleSequential(d3.interpolateGreys).domain([0,1]) }}
  }};

  function getNodeColor(d) {{
    const mapping = zoneMap[d.region] || zoneMap["DEFAULT"];
    const val = (+d.want_to_go - 4) / 5;  // normaliza (4–9) a (0–1)
    return mapping.scale(isFinite(val) ? val : 0.5);
  }}

  const radarColors = d3.scaleOrdinal(d3.schemeCategory10);

  function setSelection(ids, src) {{
    const unique = [];
    const seen = new Set();
    ids.map(String).forEach(id => {{
      if (!seen.has(id)) {{
        seen.add(id);
        unique.push(id);
      }}
    }});
    state.selected = unique;
    bus.dispatchEvent(new CustomEvent("selection", {{ detail: {{ ids: state.selected, src }} }}));
  }}

  function toggleOne(id, src) {{
    const sid = String(id);
    const current = state.selected.slice();
    const idx = current.indexOf(sid);
    if (idx > -1) {{
      current.splice(idx, 1);
    }} else {{
      current.push(sid);
    }}
    setSelection(current, src);
  }}

  // =================== Panel Selection =======================
  function renderInfo(ids) {{
    const box = document.getElementById("{info_id}");
    if (!ids.length) {{
      box.innerHTML = "<em>Sin selección</em>";
      return;
    }}
    const items = ids.map(id => byId.get(String(id))).filter(Boolean);
    const lis = items.map(n => {{
      const nm = n.name || n.id;
      const reg = n.region || "";
      const color = radarColors(n.id);
      const swatch = `<span style="color:${{color}}; font-size:1.2em; -webkit-text-stroke: 1px #ccc;">●</span> `;
      const link = n.url
        ? `<a href="${{n.url}}" target="_blank" rel="noopener noreferrer">${{nm}}</a>`
        : nm;
      return `<li>${{swatch}}<strong>${{link}}</strong>${{reg ? " · " + reg : ""}}</li>`;
    }}).join("");
    box.innerHTML = `<p><strong>${{ids.length}}</strong> seleccionado(s):</p><ul>${{lis}}</ul>`;
  }}

  bus.addEventListener("selection", e => {{
    renderInfo(e.detail.ids);
  }});

  // =================== FORCE graph ===========================
  (function initForce() {{
    const host = document.getElementById("{force_id}");
    const W = host.clientWidth;
    const H = 450;
    const svg = d3.select(host).append("svg").attr("width", W).attr("height", H);
    const g   = svg.append("g");

    const simExtent = d3.extent(filteredLinks, d => +d.similarity || 0);
    const linkWidth = d3.scaleLinear().domain(simExtent).range([1, 4]);
    const linkColor = d3.scaleSequential(d3.interpolateBlues).domain(simExtent);

    const simNodes = data.nodes.map(d => Object.assign({{}}, d));
    const sim = d3.forceSimulation(simNodes)
      .force("link", d3.forceLink(filteredLinks).id(d => String(d.id)).distance(70))
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(W / 2, H / 2));

    const link = g.append("g")
      .attr("stroke-opacity", 0.4)
      .selectAll("line")
      .data(filteredLinks)
      .join("line")
      .attr("stroke-width", d => linkWidth(+d.similarity || 0))
      .attr("stroke", d => linkColor(+d.similarity || 0));

    link.append("title").text(d => `Similaridad: ${{(+d.similarity || 0).toFixed(2)}}`);

    const nodeG = g.append("g")
      .selectAll("g")
      .data(sim.nodes())
      .join("g")
      .style("cursor", "pointer");

    nodeG.append("circle")
      .attr("r", 8)
      .attr("fill", d => getNodeColor(d))
      .attr("stroke", "#fff")
      .attr("stroke-width", 2)
      .call(
        d3.drag()
          .on("start", (event, d) => {{
            if (!event.active) sim.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          }})
          .on("drag", (event, d) => {{
            d.fx = event.x;
            d.fy = event.y;
          }})
          .on("end", (event, d) => {{
            if (!event.active) sim.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }})
      )

      .on("click", (event, d) => {{
        if (event.metaKey || event.ctrlKey) {{
          toggleOne(d.id, "force");
        }} else {{
          setSelection([d.id], "force");
        }}
          const clickData = {{
            id: d.id,
            name: d.name,
            region: d.region,
            SCORE: d.SCORE,
            lat: d.lat,
            lon: d.lon,
            __ts: new Date().toISOString(),
            __src: "force",
            __chart: "graph"
          }};

        
        sendToPython(clickData);
        event.stopPropagation();
      }});

    nodeG.append("text")
      .attr("x", 12)
      .attr("y", 4)
      .attr("font-size", "11px")
      .attr("fill", "#222")
      .style("paint-order", "stroke")
      .style("stroke", "white")
      .style("stroke-width", "3px")
      .text(d => d.name || d.id);

    sim.on("tick", () => {{
      link
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);

      nodeG.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
    }});

    bus.addEventListener("selection", e => {{
      const sel = new Set(e.detail.ids);
      const has = sel.size > 0;

      nodeG.select("circle")
        .attr("opacity", d => !has || sel.has(String(d.id)) ? 1.0 : 0.25)
        .attr("stroke",  d => sel.has(String(d.id)) ? "#d32f2f" : "#fff")
        .attr("stroke-width", d => sel.has(String(d.id)) ? 3 : 2);

      link
        .attr("stroke-opacity", d => {{
          if (!has) return 0.25;
          const s = String(d.source.id || d.source);
          const t = String(d.target.id || d.target);
          return sel.has(s) || sel.has(t) ? 0.6 : 0.08;
        }})
        .attr("stroke-width", d => {{
          const base = linkWidth(+d.similarity || 0);
          if (!has) return base;
          const s = String(d.source.id || d.source);
          const t = String(d.target.id || d.target);
          return sel.has(s) || sel.has(t) ? base * 1.5 : base;
        }});
    }});
  }})();

  // =================== Mapa de Perú ==========================
  (function initMap() {{
    const host = document.getElementById("{map_id}");
    const W = host.clientWidth;
    const H = 450;
    const svg = d3.select(host).append("svg").attr("width", W).attr("height", H);
    const gMap = svg.append("g");

    d3.json("https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json").then(world => {{
      const countries = topojson.feature(world, world.objects.countries);
      const peru =
        countries.features.find(f => f.id === "604") ||
        countries.features.find(f => (f.properties && f.properties.name === "Peru"));

      const proj = d3.geoMercator().fitExtent([[20, 20], [W - 20, H - 20]], peru);
      const path = d3.geoPath(proj);

      const lineGen = d3.line()
        .x(d => proj([+d.lon, +d.lat])[0])
        .y(d => proj([+d.lon, +d.lat])[1]);

      // Fondo
      gMap.append("path")
        .datum(peru)
        .attr("d", path)
        .attr("fill", "#f3f6ff")
        .attr("stroke", "#9db2ff")
        .attr("stroke-width", 1.0);

      // Ruta
      const routePath = gMap.append("path")
        .attr("fill", "none")
        .attr("stroke", "#d32f2f")
        .attr("stroke-width", 2.5)
        .attr("stroke-dasharray", "5 5")
        .style("pointer-events", "none");

      const pts = data.nodes.filter(
        d => Number.isFinite(+d.lat) && Number.isFinite(+d.lon)
      );

      const nodeG = gMap.append("g")
        .selectAll("g")
        .data(pts, d => d.id)
        .join("g")
        .attr("transform", d => `translate(${{proj([+d.lon, +d.lat])[0]}},${{proj([+d.lon, +d.lat])[1]}})`)
        .style("cursor", "pointer")
        
        .on("click", (event, d) => {{
          if (event.metaKey || event.ctrlKey) {{
            toggleOne(d.id, "map-click");
          }} else {{
            setSelection([d.id], "map-click");
          }}

          const clickData = {{
            id: d.id,
            name: d.name, 
            region: d.region,
            SCORE: d.SCORE,
            lat: d.lat,
            lon: d.lon,
            __ts: new Date().toISOString(),
            __src: "map",
            __chart: "map"
          }};

          sendToPython(clickData);
          event.stopPropagation();
        }});

      nodeG.append("circle")
        .attr("r", 6)
        .attr("fill", d => getNodeColor(d))
        .attr("stroke", "#fff")
        .attr("stroke-width", 1.5);

      nodeG.append("text")
        .attr("x", 9)
        .attr("y", 4)
        .attr("font-size", "10px")
        .attr("fill", "#222")
        .style("paint-order", "stroke")
        .style("stroke", "white")
        .style("stroke-width", "3px")
        .style("display", "none")
        .text(d => d.name || d.id);

      nodeG.append("title").text(d => d.name || d.id);

      const brush = d3.brush()
        .extent([[0, 0], [W, H]])
        .on("brush end", event => {{
          const sel = event.selection;
          if (!sel) {{
            setSelection([], "map-brush");
            return;
          }}
          const [[x0, y0], [x1, y1]] = sel;
          const ids = pts
            .filter(d => {{
              const p = proj([+d.lon, +d.lat]);
              return x0 <= p[0] && p[0] <= x1 && y0 <= p[1] && p[1] <= y1;
            }})
            .map(d => String(d.id));

            if (event.type === "end" && ids.length > 0) {{
                  const brushData = {{
                    __ts: new Date().toISOString(),
                    __src: "map", 
                    __chart: "map",
                    __interaction: "brush",
                    selected_ids: ids,
                    selected_count: ids.length
                  }};
                  sendToPython(brushData);
                }}


          setSelection(ids, "map-brush");
        }});

      gMap.append("g").attr("class", "brush").call(brush);

      bus.addEventListener("selection", e => {{
        const ids = e.detail.ids;
        const sel = new Set(ids);
        const has = sel.size > 0;

        nodeG.attr("opacity", d => (!has || sel.has(String(d.id)) ? 1.0 : 0.25));

        nodeG.select("circle")
          .attr("stroke", d => (sel.has(String(d.id)) ? "#d32f2f" : "#fff"))
          .attr("stroke-width", d => (sel.has(String(d.id)) ? 3 : 1.5));

        nodeG.select("text")
          .style("display", d => (sel.has(String(d.id)) ? "inline" : "none"));

        const routePoints = ids
          .map(id => byId.get(String(id)))
          .filter(d => d && Number.isFinite(+d.lat) && Number.isFinite(+d.lon));

        if (routePoints.length < 2) {{
          routePath.attr("d", null);
        }} else {{
          routePath.datum(routePoints).attr("d", lineGen);
        }}
      }});
    }});
  }})();

  // =================== SCORE bars ============================
  (function initScoreBars() {{
    const host = document.getElementById("{radar_id}");
    const W = host.clientWidth;
    const H = 420;
    const margin = {{ top: 20, right: 20, bottom: 30, left: 160 }};
    const width  = W - margin.left - margin.right;
    const height = H - margin.top - margin.bottom;

    const svg = d3.select(host)
      .append("svg")
      .attr("width", W)
      .attr("height", H);

    const g = svg.append("g")
      .attr("transform", `translate(${{margin.left}},${{margin.top}})`);

    const items = data.nodes.filter(
      d => typeof d.SCORE === "number" && !isNaN(d.SCORE)
    );

    if (!items.length) {{
      g.append("text")
        .attr("x", 0)
        .attr("y", 20)
        .attr("fill", "#666")
        .text("No SCORE data available.");
      return;
    }}

    items.sort((a, b) => d3.descending(a.SCORE, b.SCORE));

    const x = d3.scaleLinear()
      .domain([0, d3.max(items, d => d.SCORE)])
      .nice()
      .range([0, width]);

    const y = d3.scaleBand()
      .domain(items.map(d => String(d.id)))
      .range([0, height])
      .padding(0.2);

    const bars = g.selectAll("rect.bar")
      .data(items)
      .enter()
      .append("rect")
      .attr("class", "bar")
      .attr("x", 0)
      .attr("y", d => y(String(d.id)))
      .attr("height", y.bandwidth())
      .attr("width", d => x(d.SCORE))
      .attr("fill", d => getNodeColor(d))
      .style("cursor", "pointer")
      .on("click", (event, d) => {{
        if (event.metaKey || event.ctrlKey) {{
          toggleOne(d.id, "score");
        }} else {{
          setSelection([d.id], "score");
        }}
        const clickData = {{
            id: d.id,
            name: d.name,
            SCORE: d.SCORE,
            region: d.region,
            __ts: new Date().toISOString(),
            __src: "score", 
            __chart: "ranking_score"
          }};
        sendToPython(clickData);
        event.stopPropagation();
      }});

    g.selectAll("text.label")
      .data(items)
      .enter()
      .append("text")
      .attr("class", "label")
      .attr("x", -6)
      .attr("y", d => y(String(d.id)) + y.bandwidth() / 2)
      .attr("dy", "0.35em")
      .attr("text-anchor", "end")
      .attr("font-size", "10px")
      .text(d => d.name || d.id);

    g.selectAll("text.value")
      .data(items)
      .enter()
      .append("text")
      .attr("class", "value")
      .attr("x", d => x(d.SCORE) + 4)
      .attr("y", d => y(String(d.id)) + y.bandwidth() / 2)
      .attr("dy", "0.35em")
      .attr("font-size", "10px")
      .attr("fill", "#444")
      .text(d => d.SCORE.toFixed(2));

    g.append("g")
      .attr("transform", `translate(0,${{height}})`)
      .call(d3.axisBottom(x).ticks(4));

    g.append("text")
      .attr("x", width / 2)
      .attr("y", height + 26)
      .attr("text-anchor", "middle")
      .attr("font-size", "11px")
      .attr("fill", "#333")
      .text("SCORE de recomendación");

    bus.addEventListener("selection", e => {{
      const sel = new Set(e.detail.ids);
      const has = sel.size > 0;
      bars
        .attr("opacity", d => (!has || sel.has(String(d.id)) ? 1.0 : 0.25))
        .attr("stroke", d => (sel.has(String(d.id)) ? "#7b1fa2" : "none"))
        .attr("stroke-width", d => (sel.has(String(d.id)) ? 2 : 0));
    }});
  }})();
}})();
</script>
"""
    return HTML(html)