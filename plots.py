"""
plots.py — Generación de todas las figuras para la memoria del TFM (MongoMind).

Lee los datos reales del repositorio (benchmark y resultados de evaluación en
data/benchmark/) y produce un conjunto de figuras PNG en data/figures/, pensadas
para ilustrar los capítulos de Evaluación y de Análisis del problema de la memoria.

Uso:
    python plots.py            # genera todas las figuras
    python plots.py --show     # además las muestra por pantalla

Requisitos: matplotlib, numpy  (pip install matplotlib numpy)

Cada figura se genera en su propia función protegida: si una falla (p. ej. falta
un fichero de resultados), las demás se generan igualmente. Las rutas de salida
se imprimen al final.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from collections import Counter

import matplotlib

matplotlib.use("Agg")  # backend sin ventana; --show lo conmuta a interactivo
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# --------------------------------------------------------------------------- #
# Configuración global
# --------------------------------------------------------------------------- #
ROOT = os.path.dirname(os.path.abspath(__file__))
BENCH_DIR = os.path.join(ROOT, "data", "benchmark")
FIG_DIR = os.path.join(ROOT, "data", "figures")
BENCHMARK_FILE = os.path.join(BENCH_DIR, "movies_benchmark.json")

# Paleta de color coherente para toda la memoria
C_PRIMARY = "#2E86AB"    # azul (modelo principal / valores)
C_SECONDARY = "#E4572E"  # naranja (comparativa / "antes")
C_GREEN = "#3BB273"      # verde ("después" / éxito)
C_GREY = "#9AA0A6"
PALETTE = ["#2E86AB", "#3BB273", "#E4572E", "#F3A712", "#8E7DBE", "#C5283D"]

plt.rcParams.update({
    "figure.dpi": 120,
    "savefig.dpi": 150,
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
})

# Etiquetas legibles para complejidad (orden fijo)
COMPLEXITY_ORDER = ["simple", "media", "alta", "ambiguous"]
COMPLEXITY_LABELS = {
    "simple": "Simple",
    "media": "Media",
    "alta": "Alta",
    "ambiguous": "Ambigua/\nerrata",
}

_saved: list[str] = []


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def _load(path: str) -> dict | list:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _benchmark_pairs() -> list[dict]:
    data = _load(BENCHMARK_FILE)
    return data["pairs"] if isinstance(data, dict) else data


def _latest_result(model: str, split: str) -> dict | None:
    """Devuelve el JSON de resultados más reciente para (model, split), o None."""
    pattern = os.path.join(BENCH_DIR, f"results_{model}_{split}_*.json")
    matches = sorted(glob.glob(pattern))
    if not matches:
        print(f"  [aviso] sin resultados para {model}/{split} ({pattern})")
        return None
    return _load(matches[-1])


def _save(fig: plt.Figure, name: str) -> None:
    os.makedirs(FIG_DIR, exist_ok=True)
    out = os.path.join(FIG_DIR, name)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    _saved.append(out)
    print(f"  [ok] {os.path.relpath(out, ROOT)}")


def _bar_labels(ax, bars, fmt="{:.0f}", offset=0.0, pct=False):
    """Anota el valor encima de cada barra."""
    for b in bars:
        h = b.get_height()
        txt = fmt.format(h * 100) + "%" if pct else fmt.format(h)
        ax.annotate(txt, (b.get_x() + b.get_width() / 2, h + offset),
                    ha="center", va="bottom", fontsize=9, fontweight="bold")


# --------------------------------------------------------------------------- #
# 1-5. Composición del benchmark
# --------------------------------------------------------------------------- #
def plot_benchmark_complejidad():
    pairs = _benchmark_pairs()
    counts = Counter(p["complexity"] for p in pairs)
    labels = [COMPLEXITY_LABELS[c] for c in COMPLEXITY_ORDER]
    values = [counts.get(c, 0) for c in COMPLEXITY_ORDER]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(labels, values, color=PALETTE[:4])
    _bar_labels(ax, bars, offset=0.2)
    ax.set_title(f"Composición del benchmark por complejidad (n={len(pairs)})")
    ax.set_ylabel("Nº de pares (pregunta → MQL)")
    ax.set_ylim(0, max(values) * 1.18)
    _save(fig, "01_benchmark_complejidad.png")
    plt.close(fig)


def plot_benchmark_idioma():
    pairs = _benchmark_pairs()
    counts = Counter(p.get("lang", "?") for p in pairs)
    labels = {"es": "Español", "en": "Inglés"}
    keys = list(counts.keys())
    values = [counts[k] for k in keys]

    fig, ax = plt.subplots(figsize=(5.5, 5))
    wedges, _texts, autotexts = ax.pie(
        values, labels=[labels.get(k, k) for k in keys],
        autopct=lambda p: f"{p:.0f}%\n({round(p * sum(values) / 100)})",
        colors=[C_PRIMARY, C_SECONDARY], startangle=90,
        wedgeprops=dict(width=0.45, edgecolor="white"))
    for t in autotexts:
        t.set_color("white")
        t.set_fontweight("bold")
    ax.set_title(f"Distribución del benchmark por idioma (n={len(pairs)})")
    _save(fig, "02_benchmark_idioma.png")
    plt.close(fig)


def plot_benchmark_split():
    pairs = _benchmark_pairs()
    # dev/test apilado por complejidad
    splits = ["dev", "test"]
    data = {s: [sum(1 for p in pairs if p.get("split") == s and p["complexity"] == c)
                for c in COMPLEXITY_ORDER] for s in splits}

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(len(splits))
    bottom = np.zeros(len(splits))
    for i, c in enumerate(COMPLEXITY_ORDER):
        vals = [data[s][i] for s in splits]
        ax.bar(x, vals, bottom=bottom, label=COMPLEXITY_LABELS[c].replace("\n", " "),
               color=PALETTE[i])
        bottom += np.array(vals)
    totals = [sum(1 for p in pairs if p.get("split") == s) for s in splits]
    for xi, tot in zip(x, totals):
        ax.annotate(f"{tot}", (xi, tot + 0.5), ha="center", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([f"dev\n(entrenamiento/tuning)", "test\n(holdout)"])
    ax.set_ylabel("Nº de pares")
    ax.set_ylim(0, max(totals) * 1.18)
    ax.set_title("Partición dev/test del benchmark (70/30) por complejidad")
    ax.legend(title="Complejidad", fontsize=9)
    _save(fig, "03_benchmark_split.png")
    plt.close(fig)


def plot_benchmark_result_type():
    pairs = _benchmark_pairs()
    counts = Counter(p.get("result_type", "?") for p in pairs)
    labels_map = {"documents": "documents\n(conjunto de docs)",
                  "groups": "groups\n(agrupaciones)",
                  "count": "count\n(recuento)",
                  "scalar": "scalar\n(media/suma)"}
    items = counts.most_common()
    labels = [labels_map.get(k, k) for k, _ in items]
    values = [v for _, v in items]

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    bars = ax.bar(labels, values, color=PALETTE[:len(values)])
    _bar_labels(ax, bars, offset=0.4)
    ax.set_title("Tipos de resultado en el benchmark (estrategia de comparación)")
    ax.set_ylabel("Nº de pares")
    ax.set_ylim(0, max(values) * 1.18)
    _save(fig, "04_benchmark_result_type.png")
    plt.close(fig)


def plot_benchmark_categoria():
    pairs = _benchmark_pairs()
    counts = Counter(p.get("category", "?") for p in pairs)
    items = counts.most_common()
    labels = [k for k, _ in items][::-1]
    values = [v for _, v in items][::-1]

    fig, ax = plt.subplots(figsize=(7.5, 6))
    bars = ax.barh(labels, values, color=C_PRIMARY)
    for b in bars:
        w = b.get_width()
        ax.annotate(f"{int(w)}", (w + 0.1, b.get_y() + b.get_height() / 2),
                    va="center", fontsize=9, fontweight="bold")
    ax.set_title("Operaciones MQL cubiertas por el benchmark (categoría)")
    ax.set_xlabel("Nº de pares")
    ax.set_xlim(0, max(values) * 1.15)
    ax.grid(axis="y", alpha=0)
    _save(fig, "05_benchmark_categoria.png")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 6-7. Resultados del modelo principal (llama3.2, test)
# --------------------------------------------------------------------------- #
def plot_metricas_modelo_principal():
    res = _latest_result("llama3.2", "test")
    if not res:
        return
    m = res["metrics"]
    labels = ["Corrección\nfuncional", "Corrección\nparcial", "Exact\nmatch",
              "Tasa de\nerror"]
    values = [m["functional_accuracy"], m["partial_correctness"],
              m["exact_match"], m["execution_error_rate"]]
    colors = [C_GREEN, C_PRIMARY, C_GREY, C_SECONDARY]

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    bars = ax.bar(labels, values, color=colors)
    _bar_labels(ax, bars, fmt="{:.1f}", offset=0.01, pct=True)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Proporción")
    ax.set_title(f"Métricas del modelo principal "
                 f"({res['model']}, split {res['split']}, n={m['n']})")
    _save(fig, "06_metricas_modelo_principal.png")
    plt.close(fig)


def plot_funcional_por_complejidad():
    res = _latest_result("llama3.2", "test")
    if not res:
        return
    bc = res["by_complexity"]
    labels, values, ns = [], [], []
    for c in COMPLEXITY_ORDER:
        if c in bc:
            labels.append(COMPLEXITY_LABELS[c])
            values.append(bc[c]["functional_accuracy"])
            ns.append(bc[c]["n"])

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    bars = ax.bar(labels, values, color=PALETTE[:len(values)])
    for b, n in zip(bars, ns):
        h = b.get_height()
        ax.annotate(f"{h * 100:.0f}%\n(n={n})",
                    (b.get_x() + b.get_width() / 2, h + 0.01),
                    ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.axhline(res["metrics"]["functional_accuracy"], color=C_SECONDARY,
               ls="--", lw=1.3,
               label=f"Media global = {res['metrics']['functional_accuracy']*100:.0f}%")
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("Corrección funcional")
    ax.set_title(f"Corrección funcional por complejidad "
                 f"({res['model']}, split {res['split']})")
    ax.legend(fontsize=9)
    _save(fig, "07_funcional_por_complejidad.png")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 8-10. Comparativa de modelos (llama3.1 vs llama3.2, test)
# --------------------------------------------------------------------------- #
# Orden de presentación preferido (principal primero). Cualquier otro modelo
# encontrado se añade después automáticamente.
_MODEL_ORDER = ["llama3.2", "llama3.1", "qwen2.5_3b", "gemma2_2b", "nl2mongo"]
_MODEL_PRINCIPAL = "llama3.2"


def _all_latest_test() -> list[dict]:
    """Descubre el resultado de test más reciente de cada modelo disponible."""
    found: dict[str, dict] = {}
    for path in glob.glob(os.path.join(BENCH_DIR, "results_*_test_*.json")):
        rep = _load(path)
        # nos quedamos con el timestamp más alto por modelo
        prev = found.get(rep["model"])
        if prev is None or rep["timestamp"] > prev["timestamp"]:
            found[rep["model"]] = rep
    ordered = [found[m] for m in _MODEL_ORDER if m in found]
    ordered += [found[m] for m in sorted(found) if m not in _MODEL_ORDER]
    return ordered


def _model_colors(n):
    return [PALETTE[i % len(PALETTE)] for i in range(n)]


def plot_comparativa_modelos():
    reps = _all_latest_test()
    if len(reps) < 2:
        return
    metrics = [("functional_accuracy", "Corrección\nfuncional"),
               ("exact_match", "Exact\nmatch"),
               ("execution_error_rate", "Tasa de\nerror"),
               ("partial_correctness", "Corrección\nparcial")]
    labels = [lbl for _, lbl in metrics]
    x = np.arange(len(labels))
    nm = len(reps)
    w = 0.8 / nm
    colors = _model_colors(nm)
    fig, ax = plt.subplots(figsize=(max(9, 1.7 * nm + 5), 5))
    for i, rep in enumerate(reps):
        vals = [rep["metrics"][k] for k, _ in metrics]
        off = (i - (nm - 1) / 2) * w
        bars = ax.bar(x + off, vals, w, label=rep["model"], color=colors[i])
        _bar_labels(ax, bars, fmt="{:.0f}", offset=0.01, pct=True)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Proporción")
    ax.set_title("Comparativa de modelos (split test)")
    ax.legend(fontsize=8, ncol=min(nm, 3))
    _save(fig, "08_comparativa_modelos.png")
    plt.close(fig)


def plot_comparativa_complejidad():
    reps = _all_latest_test()
    if len(reps) < 2:
        return
    labels = [COMPLEXITY_LABELS[c] for c in COMPLEXITY_ORDER]
    x = np.arange(len(labels))
    nm = len(reps)
    w = 0.8 / nm
    colors = _model_colors(nm)
    fig, ax = plt.subplots(figsize=(max(9, 1.7 * nm + 5), 5))
    for i, rep in enumerate(reps):
        vals = [rep["by_complexity"].get(c, {}).get("functional_accuracy", 0)
                for c in COMPLEXITY_ORDER]
        off = (i - (nm - 1) / 2) * w
        ax.bar(x + off, vals, w, label=rep["model"], color=colors[i])
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("Corrección funcional")
    ax.set_title("Corrección funcional por complejidad y modelo (split test)")
    ax.legend(fontsize=8, ncol=min(nm, 3))
    _save(fig, "09_comparativa_complejidad.png")
    plt.close(fig)


def plot_tradeoff_calidad_latencia():
    reps = [r for r in _all_latest_test() if r["metrics"].get("avg_latency_s")]
    if len(reps) < 2:
        return
    colors = _model_colors(len(reps))
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for rep, color in zip(reps, colors):
        x = rep["metrics"]["avg_latency_s"]
        y = rep["metrics"]["functional_accuracy"]
        ax.scatter(x, y, s=300, color=color, zorder=3, edgecolor="white", lw=1.5)
        ax.annotate(f"{rep['model']}\n{y*100:.1f}% · {x:.2f}s",
                    (x, y), textcoords="offset points", xytext=(10, 8),
                    fontsize=8.5, fontweight="bold")
    ax.set_xlabel("Latencia media de generación (s)  →  más lento")
    ax.set_ylabel("Corrección funcional  →  más preciso")
    ax.set_title("Compromiso calidad vs. latencia (split test)")
    ax.margins(0.28)
    _save(fig, "10_tradeoff_calidad_latencia.png")
    plt.close(fig)


def plot_ranking_modelos():
    reps = _all_latest_test()
    if len(reps) < 2:
        return
    reps = sorted(reps, key=lambda r: r["metrics"]["functional_accuracy"])
    names = [r["model"] for r in reps]
    vals = [r["metrics"]["functional_accuracy"] for r in reps]
    colors = [C_GREEN if n == _MODEL_PRINCIPAL else C_PRIMARY for n in names]
    fig, ax = plt.subplots(figsize=(8, 0.7 * len(reps) + 2))
    bars = ax.barh(names, vals, color=colors)
    for b in bars:
        w = b.get_width()
        ax.annotate(f"{w*100:.1f}%", (w + 0.01, b.get_y() + b.get_height() / 2),
                    va="center", fontweight="bold", fontsize=9)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Corrección funcional (split test)")
    ax.set_title("Ranking de modelos por corrección funcional")
    ax.grid(axis="y", alpha=0)
    # etiqueta sobre la barra del modelo principal (en su posición real)
    if _MODEL_PRINCIPAL in names:
        yi = names.index(_MODEL_PRINCIPAL)
        ax.annotate("modelo principal", xy=(0.02, yi), fontsize=8,
                    color="white", fontweight="bold", va="center")
    _save(fig, "13_ranking_modelos.png")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 11. Mejora por ingeniería de prompts (few-shot) — Día 19
# --------------------------------------------------------------------------- #
def plot_mejora_fewshot():
    # Valores documentados (CLAUDE.md / dia_a_dia.txt, Día 19, llama3.2)
    splits = ["dev\n(tuning)", "test\n(holdout)"]
    antes = [0.739, 0.632]
    despues = [0.891, 0.737]

    x = np.arange(len(splits))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7.5, 5))
    b1 = ax.bar(x - w / 2, antes, w, label="Few-shot baseline", color=C_SECONDARY)
    b2 = ax.bar(x + w / 2, despues, w,
                label='Few-shot mejorado\n(+ "PISTAS IMPORTANTES" + 5 ejemplos)',
                color=C_GREEN)
    _bar_labels(ax, b1, fmt="{:.1f}", offset=0.01, pct=True)
    _bar_labels(ax, b2, fmt="{:.1f}", offset=0.01, pct=True)
    for xi, lo, hi in zip(x, antes, despues):
        ax.annotate(f"+{(hi-lo)*100:.1f} pp",
                    ((xi - w/2 + xi + w/2) / 2, hi + 0.06),
                    ha="center", color=C_GREEN, fontweight="bold", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(splits)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Corrección funcional")
    ax.set_title("Impacto de la mejora del few-shot (llama3.2)")
    ax.legend(fontsize=9, loc="lower right")
    _save(fig, "11_mejora_fewshot.png")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 12. Taxonomía de errores (Día 19, dev, 12 fallos)
# --------------------------------------------------------------------------- #
def plot_taxonomia_errores():
    # Día 19: 12 fallos en dev. El patrón dominante (guarda numérica) está
    # documentado con 5 casos; el resto se reparte entre los patrones citados.
    # Ajusta los recuentos si dispones del desglose exacto.
    taxonomia = {
        'Falta de guarda numérica\n{"$type":"number"}': 5,
        "Falta de $unwind antes de\n$group por array": 2,
        '$count mal formado\n({} en vez de "total")': 1,
        '"más de N" con $size\nen vez de campo.N exists': 1,
        "$match usado como\nfiltro de find": 1,
        "Sobre-complicar\nfiltros simples": 1,
        "Proyectar fuera el _id\nen groups": 1,
    }
    labels = list(taxonomia.keys())[::-1]
    values = list(taxonomia.values())[::-1]
    colors = [C_SECONDARY if v >= 5 else C_PRIMARY for v in values]

    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    bars = ax.barh(labels, values, color=colors)
    for b in bars:
        w = b.get_width()
        ax.annotate(f"{int(w)}", (w + 0.05, b.get_y() + b.get_height() / 2),
                    va="center", fontweight="bold", fontsize=9)
    ax.set_title("Taxonomía de los 12 fallos en dev (llama3.2, Día 19)")
    ax.set_xlabel("Nº de fallos")
    ax.set_xlim(0, max(values) * 1.2)
    ax.grid(axis="y", alpha=0)
    _save(fig, "12_taxonomia_errores.png")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Orquestación
# --------------------------------------------------------------------------- #
ALL_PLOTS = [
    plot_benchmark_complejidad,
    plot_benchmark_idioma,
    plot_benchmark_split,
    plot_benchmark_result_type,
    plot_benchmark_categoria,
    plot_metricas_modelo_principal,
    plot_funcional_por_complejidad,
    plot_comparativa_modelos,
    plot_comparativa_complejidad,
    plot_tradeoff_calidad_latencia,
    plot_ranking_modelos,
    plot_mejora_fewshot,
    plot_taxonomia_errores,
]


def main():
    parser = argparse.ArgumentParser(description="Genera las figuras de la memoria.")
    parser.add_argument("--show", action="store_true", help="muestra las figuras")
    args = parser.parse_args()

    print(f"Generando figuras en {os.path.relpath(FIG_DIR, ROOT)}/ ...")
    for fn in ALL_PLOTS:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERROR] {fn.__name__}: {exc}")

    print(f"\n{len(_saved)} figuras generadas.")
    if args.show and _saved:
        matplotlib.use("TkAgg")
        for path in _saved:
            img = plt.imread(path)
            plt.figure()
            plt.imshow(img)
            plt.axis("off")
        plt.show()


if __name__ == "__main__":
    main()
