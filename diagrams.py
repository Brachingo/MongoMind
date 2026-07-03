"""
diagrams.py — Esquemas de arquitectura/pipeline para la memoria del TFM (MongoMind).

Dibuja diagramas de bloques (cajas + flechas) con matplotlib, sin dependencias
extra (no requiere graphviz). Genera PNGs en data/figures/ con prefijo "diag_".

Diagramas:
  1. Pipeline principal NL -> MQL -> ejecución -> respuesta.
  2. Seguridad y robustez (defensa en profundidad).
  3. Construcción del prompt few-shot (plantilla estática vs esquema inferido).
  4. Detección de colección y routing multi-dataset.
  5. Flujo de evaluación funcional del benchmark.

Uso:
    python diagrams.py
"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
FIG_DIR = os.path.join(ROOT, "data", "figures")

# Paleta categórica validada (skill dataviz — references/palette.md), asignada
# por rol semántico y comprobada con scripts/validate_palette.js (light, #ffffff):
# CVD peor-caso adyacente ΔE 25.0, contraste OK salvo C_DB (WARN, mitigado por
# las etiquetas de texto directas que ya lleva cada caja).
C_INPUT = "#eb6834"     # naranja — entrada / usuario
C_CORE = "#2a78d6"      # azul — módulos del core
C_LLM = "#4a3aa7"       # violeta — LLM
C_DB = "#1baf7a"        # aqua — base de datos
C_SEC = "#e34948"       # rojo — seguridad
C_OUT = "#52514e"       # gris oscuro (ink secundario) — salida
C_NEUTRAL = "#898781"   # gris (ink muted) — neutral

plt.rcParams.update({"savefig.dpi": 150, "font.size": 10})

_saved: list[str] = []


# --------------------------------------------------------------------------- #
# Toolkit de dibujo
# --------------------------------------------------------------------------- #
def _new_ax(w=12.0, h=7.0):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def box(ax, cx, cy, w, h, text, color=C_CORE, fc=None, text_color="white",
        fontsize=10, fontweight="bold", style="round", alpha=1.0):
    """Caja centrada en (cx, cy) con texto."""
    fc = fc if fc is not None else color
    pad = 0.02
    boxstyle = "round,pad=0.3,rounding_size=2" if style == "round" else "square,pad=0.3"
    patch = FancyBboxPatch(
        (cx - w / 2, cy - h / 2), w, h,
        boxstyle=boxstyle, linewidth=1.5,
        edgecolor=color, facecolor=fc, alpha=alpha, mutation_scale=1)
    ax.add_patch(patch)
    ax.text(cx, cy, text, ha="center", va="center", color=text_color,
            fontsize=fontsize, fontweight=fontweight, wrap=True, zorder=5)
    return (cx, cy, w, h)


def arrow(ax, p1, p2, color="#444444", style="-|>", lw=1.8, ls="-",
          rad=0.0, label=None, label_pos=0.5, label_color="#444444"):
    """Flecha entre dos puntos (x, y)."""
    a = FancyArrowPatch(
        p1, p2, arrowstyle=style, mutation_scale=16,
        color=color, lw=lw, linestyle=ls,
        connectionstyle=f"arc3,rad={rad}", zorder=1)
    ax.add_patch(a)
    if label:
        mx = p1[0] + (p2[0] - p1[0]) * label_pos
        my = p1[1] + (p2[1] - p1[1]) * label_pos
        ax.text(mx, my, label, ha="center", va="center", fontsize=8,
                color=label_color, style="italic",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))


def right(b):
    cx, cy, w, h = b
    return (cx + w / 2, cy)


def left(b):
    cx, cy, w, h = b
    return (cx - w / 2, cy)


def top(b):
    cx, cy, w, h = b
    return (cx, cy + h / 2)


def bottom(b):
    cx, cy, w, h = b
    return (cx, cy - h / 2)


def title(ax, text):
    ax.text(50, 97, text, ha="center", va="top", fontsize=14, fontweight="bold")


def save(fig, name):
    os.makedirs(FIG_DIR, exist_ok=True)
    out = os.path.join(FIG_DIR, name)
    fig.savefig(out, bbox_inches="tight")
    _saved.append(out)
    print(f"  [ok] {os.path.relpath(out, ROOT)}")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 1. Pipeline principal NL -> MQL
# --------------------------------------------------------------------------- #
def diagram_pipeline():
    fig, ax = _new_ax(13, 6.5)
    title(ax, "Pipeline NL → MQL → ejecución → respuesta")

    y = 62
    bw, bh = 17, 13
    b_user = box(ax, 11, y, 15, bh, "Pregunta NL\n(ES / EN)", C_INPUT)
    b_san = box(ax, 32, y, bw, bh, "sanitizer\nnormaliza + acota\n(2–500 car.)", C_CORE)
    b_nlp = box(ax, 54, y, bw, bh, "nlp / datasets\ndetecta colección\n(keywords)", C_CORE)
    b_gen = box(ax, 78, y, bw, bh, "mql_generator\nprompt few-shot\n+ LLM (Ollama)", C_LLM)

    y2 = 28
    b_val = box(ax, 78, y2, bw, bh, "validación\nJSON válido +\nsin escrituras", C_SEC)
    b_db = box(ax, 54, y2, bw, bh, "db_connector\nPyMongo →\nAtlas (solo lec.)", C_DB)
    b_app = box(ax, 30, y2, bw, bh, "app (FastAPI)\nformatea\nresultado + MQL", C_OUT)
    b_resp = box(ax, 9, y2, 14, bh, "Respuesta\nal usuario", C_INPUT)

    arrow(ax, right(b_user), left(b_san))
    arrow(ax, right(b_san), left(b_nlp))
    arrow(ax, right(b_nlp), left(b_gen))
    arrow(ax, bottom(b_gen), top(b_val), label="MQL (texto LLM)")
    arrow(ax, left(b_val), right(b_db), label="MQL validada")
    arrow(ax, left(b_db), right(b_app), label="documentos")
    arrow(ax, left(b_app), right(b_resp))

    # log de auditoría
    b_log = box(ax, 54, 8, 26, 8, "query_logger →\nlogs/queries.log (auditoría)",
                C_NEUTRAL, fontsize=7.5)
    arrow(ax, bottom(b_db), top(b_log), color=C_NEUTRAL, ls="--", lw=1.2)

    # memoria conversacional
    b_mem = box(ax, 76, 86, 30, 9,
                "Memoria conversacional\n(5 turnos) → resuelve anáforas",
                C_NEUTRAL, fontsize=7.5)
    arrow(ax, bottom(b_mem), top(b_gen), color=C_NEUTRAL, ls="--", lw=1.2)

    save(fig, "diag_01_pipeline.png")


# --------------------------------------------------------------------------- #
# 2. Seguridad y robustez (defensa en profundidad)
# --------------------------------------------------------------------------- #
def diagram_seguridad():
    fig, ax = _new_ax(11, 8)
    title(ax, "Seguridad y robustez: defensa en profundidad")

    steps = [
        ("Pregunta del usuario (texto libre)", C_INPUT, "white"),
        ("1 · sanitize_question()\nnormaliza Unicode, quita control,\nacota longitud (2–500)", C_CORE, "white"),
        ("2 · RateLimiter\n20 req/min por IP  →  HTTP 429", C_CORE, "white"),
        ("3 · generate(): MQL como JSON\nparseo + _repair_json (reintento)", C_LLM, "white"),
        ("4 · _check_no_writes()\nrechaza insert/update/delete/drop,\n$out, $merge  →  ValueError", C_SEC, "white"),
        ("5 · Conexión MongoDB de SOLO LECTURA\n(barrera última a nivel de BD)", C_DB, "white"),
        ("6 · log_query() → auditoría JSONL", C_NEUTRAL, "white"),
    ]
    n = len(steps)
    top_y, bot_y = 86, 8
    gap = (top_y - bot_y) / (n - 1)
    bw, bh = 62, 9
    prev = None
    for i, (text, color, tc) in enumerate(steps):
        cy = top_y - i * gap
        b = box(ax, 50, cy, bw, bh, text, color, text_color=tc,
                fontsize=9 if i else 10)
        if prev:
            arrow(ax, bottom(prev), top(b))
        prev = b

    # anotación lateral
    ax.text(88, 47, "Cada capa es\nindependiente:\nsi una falla,\nlas demás\nsiguen\nprotegiendo",
            ha="center", va="center", fontsize=9, style="italic", color=C_SEC,
            bbox=dict(boxstyle="round,pad=0.4", fc="#FBE9E7", ec=C_SEC))
    save(fig, "diag_02_seguridad.png")


# --------------------------------------------------------------------------- #
# 3. Construcción del prompt few-shot
# --------------------------------------------------------------------------- #
def diagram_prompt():
    fig, ax = _new_ax(13, 7.5)
    title(ax, "Construcción del prompt few-shot (_build_messages)")

    # Rama A: plantilla estática
    b_tpl = box(ax, 20, 80, 30, 11,
                "Plantilla .txt por colección\n(rol + esquema + 8–10 ejemplos\nNL→MQL verificados)",
                C_CORE, fontsize=8.5)
    # Rama B: esquema inferido
    b_inf = box(ax, 20, 55, 30, 11,
                "schema_inferrer\n(muestrea ~50–100 docs →\nplantilla dinámica)",
                C_DB, fontsize=8.5)
    ax.text(20, 67, "¿existe .txt?", ha="center", fontsize=8, style="italic",
            color="#444")
    ax.text(4, 80, "sí", ha="center", fontsize=8, color=C_CORE, fontweight="bold")
    ax.text(4, 55, "no", ha="center", fontsize=8, color=C_DB, fontweight="bold")

    b_split = box(ax, 55, 67, 22, 12,
                  'Split en\n"Ahora responde…"',
                  C_NEUTRAL, fontsize=9)
    arrow(ax, right(b_tpl), (b_split[0] - b_split[2] / 2, b_split[1] + 3), rad=-0.15)
    arrow(ax, right(b_inf), (b_split[0] - b_split[2] / 2, b_split[1] - 3), rad=0.15)

    b_sys = box(ax, 85, 80, 24, 10, "system message\n(rol + esquema + ejemplos)",
                C_CORE, fontsize=8.5)
    b_hist = box(ax, 85, 60, 24, 10, "history turns\n(memoria, 5 turnos)",
                 C_NEUTRAL, fontsize=8.5)
    b_q = box(ax, 85, 40, 24, 10, "user turn\n(pregunta sanitizada)",
              C_INPUT, fontsize=8.5)
    arrow(ax, top(b_split), left(b_sys), rad=-0.2)
    arrow(ax, right(b_split), left(b_hist), rad=0)
    arrow(ax, bottom(b_split), left(b_q), rad=0.2)

    b_msgs = box(ax, 55, 22, 36, 11, "messages = [system, …history…, user]",
                 C_LLM, fontsize=8.5)
    arrow(ax, bottom(b_sys), (b_msgs[0] + 8, b_msgs[1] + b_msgs[3] / 2), rad=0.2)
    arrow(ax, bottom(b_hist), top(b_msgs), rad=0.1)
    arrow(ax, bottom(b_q), (b_msgs[0] + 13, b_msgs[1] + b_msgs[3] / 2), rad=-0.1)

    b_llm = box(ax, 55, 7, 36, 8, "ollama.chat (temperature=0.1) → MQL",
                C_LLM, fontsize=8.5)
    arrow(ax, bottom(b_msgs), top(b_llm))

    save(fig, "diag_03_prompt_fewshot.png")


# --------------------------------------------------------------------------- #
# 4. Routing multi-dataset
# --------------------------------------------------------------------------- #
def diagram_routing():
    fig, ax = _new_ax(13, 7)
    title(ax, "Detección de colección y routing multi-dataset")

    b_q = box(ax, 12, 75, 18, 11, "Pregunta NL\n+ dataset\nseleccionado", C_INPUT,
              fontsize=9)
    b_reg = box(ax, 40, 75, 26, 13,
                "Registro CERRADO de datasets\nsample_mflix · sample_airbnb ·\nsample_analytics",
                C_CORE, fontsize=8.5)
    arrow(ax, right(b_q), left(b_reg))

    b_detect = box(ax, 75, 75, 22, 13,
                   "detect_collection()\npuntúa keywords por\ncolección del dataset",
                   C_CORE, fontsize=8.5)
    arrow(ax, right(b_reg), left(b_detect))

    # colecciones candidatas (ejemplo mflix)
    cols = ["movies", "comments", "theaters", "users"]
    for i, c in enumerate(cols):
        cx = 22 + i * 19
        b = box(ax, cx, 47, 15, 8, c, C_NEUTRAL, fontsize=9)
        arrow(ax, bottom(b_detect), top(b), color=C_NEUTRAL, lw=1.2, rad=0.0)
    ax.text(80, 47, "score máx.\n(o 'previous'\nen follow-ups)", ha="center",
            fontsize=8, style="italic", color="#444")

    b_sel = box(ax, 22, 26, 18, 10, "Colección\nseleccionada", C_DB, fontsize=9)
    arrow(ax, (22, 43), top(b_sel), color=C_DB)

    b_tpl = box(ax, 50, 26, 26, 10,
                "Selección de esquema/plantilla\n(.txt o dinámica), cache por\n(database, collection)",
                C_CORE, fontsize=8.5)
    arrow(ax, right(b_sel), left(b_tpl))

    b_gen = box(ax, 82, 26, 20, 10, "mql_generator\n.generate(\n…, database=)", C_LLM,
                fontsize=8.5)
    arrow(ax, right(b_tpl), left(b_gen))

    ax.text(50, 9,
            "Cambiar de dataset reinicia la memoria conversacional "
            "(la anáfora entre datasets no es válida)",
            ha="center", fontsize=9, style="italic", color=C_SEC,
            bbox=dict(boxstyle="round,pad=0.4", fc="#FBE9E7", ec=C_SEC))
    save(fig, "diag_04_routing.png")


# --------------------------------------------------------------------------- #
# 5. Flujo de evaluación funcional
# --------------------------------------------------------------------------- #
def diagram_eval():
    fig, ax = _new_ax(13, 7)
    title(ax, "Evaluación funcional del benchmark (tests/eval.py)")

    b_pair = box(ax, 14, 78, 22, 12, "Par del benchmark\n(pregunta,\nexpected_mql)", C_INPUT,
                 fontsize=9)
    b_gen = box(ax, 45, 86, 26, 10, "Modelo (Ollama) →\nMQL generada", C_LLM, fontsize=9)
    b_ref = box(ax, 45, 70, 26, 10, "MQL de referencia\n(expected_mql)", C_NEUTRAL,
                fontsize=9)
    arrow(ax, top(b_pair), left(b_gen), rad=-0.15)
    arrow(ax, bottom(b_pair), left(b_ref), rad=0.15)

    b_exg = box(ax, 76, 86, 20, 10, "Ejecuta en Atlas\n(EVAL_LIMIT=1000)", C_DB,
                fontsize=8.5)
    b_exr = box(ax, 76, 70, 20, 10, "Ejecuta en Atlas\n(EVAL_LIMIT=1000)", C_DB,
                fontsize=8.5)
    arrow(ax, right(b_gen), left(b_exg))
    arrow(ax, right(b_ref), left(b_exr))

    b_cmp = box(ax, 76, 48, 24, 12,
                "Comparación FUNCIONAL\nsegún result_type",
                C_SEC, fontsize=9)
    arrow(ax, bottom(b_exg), (b_cmp[0], b_cmp[1] + b_cmp[3] / 2), rad=0.1)
    arrow(ax, bottom(b_exr), (b_cmp[0], b_cmp[1] + b_cmp[3] / 2), rad=-0.1)

    # tipos de comparación
    types = [
        ("count\n(valor numérico)", 16),
        ("scalar\n(tol. relativa)", 35),
        ("documents\n(conjunto títulos\n/ Jaccard)", 54),
        ("groups\n({_id: métrica})", 73),
    ]
    for text, cx in types:
        b = box(ax, cx, 27, 17, 11, text, C_CORE, fontsize=8)
        arrow(ax, left(b_cmp) if cx == 73 else (b_cmp[0] - 2, b_cmp[1] - b_cmp[3] / 2),
              top(b), color=C_CORE, lw=1.2, rad=0.0)

    b_metrics = box(ax, 44.5, 8, 64, 9,
                    "Métricas: funcional · exact · error · parcial · latencia\n"
                    "(+ desglose por complejidad)", C_OUT, fontsize=8.5)
    for _, cx in types:
        arrow(ax, (cx, 27 - 5.5), (cx, b_metrics[1] + 4.5), color=C_OUT, lw=1.0)

    save(fig, "diag_05_eval.png")


# --------------------------------------------------------------------------- #
# 6. Fundamentos del LLM: Transformer + few-shot (in-context learning)
# --------------------------------------------------------------------------- #
def diagram_llm_fewshot():
    fig, ax = _new_ax(13, 7)
    title(ax, "El LLM en MongoMind: Transformer + few-shot (in-context learning)")

    # Entradas que componen el contexto (prompt)
    b_schema = box(ax, 16, 80, 26, 11,
                   "Esquema de la colección\n(estático o inferido)", C_DB,
                   fontsize=8.5)
    b_shots = box(ax, 16, 60, 26, 11,
                  "Ejemplos few-shot\nNL → MQL (8–10 verificados)", C_CORE,
                  fontsize=8.5)
    b_q = box(ax, 16, 40, 26, 11, "Pregunta del usuario\n(ES / EN)", C_INPUT,
              fontsize=8.5)
    ax.text(16, 92, "CONTEXTO (prompt)", ha="center", fontsize=9,
            fontweight="bold", color="#444")

    # El modelo: Transformer
    b_llm = box(ax, 53, 60, 28, 40,
                "LLM (Transformer)\n\n· tokenización\n· atención (self-attention)\n"
                "· N capas apiladas\n· predicción autoregresiva\n"
                "  del siguiente token", C_LLM, fontsize=9.5, style="round")

    for b in (b_schema, b_shots, b_q):
        arrow(ax, right(b), (b_llm[0] - b_llm[2] / 2, b[1]), rad=0.0)

    # Salida
    b_out = box(ax, 87, 60, 20, 14, "MQL generado\n(JSON: find /\naggregation)", C_OUT,
                fontsize=9)
    arrow(ax, right(b_llm), left(b_out), label="token a token", label_pos=0.55)

    # Pesos congelados
    ax.text(53, 33, "pesos del modelo CONGELADOS", ha="center", fontsize=8.5,
            fontweight="bold", color=C_SEC,
            bbox=dict(boxstyle="round,pad=0.3", fc="#FBE9E7", ec=C_SEC))

    # Mensaje clave
    ax.text(50, 12,
            "In-context learning: el modelo se adapta a la colección a partir de los "
            "ejemplos del propio prompt,\nSIN reentrenamiento. La salida es un muestreo "
            "probabilístico → hay que validarla y repararla.",
            ha="center", fontsize=8.5, style="italic", color="#444",
            bbox=dict(boxstyle="round,pad=0.4", fc="#EEF3F7", ec=C_CORE))

    save(fig, "diag_06_llm_fewshot.png")


# --------------------------------------------------------------------------- #
ALL = [diagram_pipeline, diagram_seguridad, diagram_prompt,
       diagram_routing, diagram_eval, diagram_llm_fewshot]


def main():
    print(f"Generando diagramas en {os.path.relpath(FIG_DIR, ROOT)}/ ...")
    for fn in ALL:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERROR] {fn.__name__}: {exc}")
    print(f"\n{len(_saved)} diagramas generados.")


if __name__ == "__main__":
    main()
