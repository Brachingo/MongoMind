"""
Día 18 — Comparativa de modelos.

Carga los JSON exportados por tests/eval.py y construye una tabla comparativa
(modelo · corrección funcional · exact match · tasa de error · corrección parcial ·
latencia media) más un desglose de corrección funcional por complejidad.

Por defecto toma el resultado MÁS RECIENTE de cada modelo para el split indicado.
Imprime la tabla en texto y, con --md, en formato Markdown listo para la memoria.

NO requiere red. No es un test de pytest.

Uso:
    python tests/compare_results.py                 # split test, todos los modelos
    python tests/compare_results.py --split dev
    python tests/compare_results.py --md            # salida Markdown
    python tests/compare_results.py f1.json f2.json # ficheros concretos
"""
import argparse
import glob
import json
from pathlib import Path

RESULTS_DIR = Path(__file__).parent.parent / "data" / "benchmark"
COMPLEXITY_ORDER = ("simple", "media", "alta", "ambiguous")


def _latest_per_model(split: str) -> list[Path]:
    """Devuelve el fichero más reciente (por nombre/timestamp) de cada modelo."""
    files = sorted(RESULTS_DIR.glob(f"results_*_{split}_*.json"))
    by_model: dict[str, Path] = {}
    for f in files:
        report = json.loads(f.read_text(encoding="utf-8"))
        by_model[report["model"]] = f  # sorted asc -> el último gana (más reciente)
    return list(by_model.values())


def _load(paths: list[Path]) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in paths]


def _pct(x) -> str:
    return f"{x*100:.1f}%" if isinstance(x, (int, float)) else "-"


def _print_text(reports: list[dict]):
    print(f"\n{'='*92}")
    print(f"  COMPARATIVA DE MODELOS  (split={reports[0]['split']}, n={reports[0]['metrics']['n']})")
    print(f"{'='*92}")
    h = f"  {'Modelo':<16}{'Funcional':>11}{'Exact':>9}{'Error':>9}{'Parcial':>10}{'Latencia':>11}"
    print(h)
    print(f"  {'-'*86}")
    for r in sorted(reports, key=lambda r: r["metrics"]["functional_accuracy"], reverse=True):
        m = r["metrics"]
        lat = f"{m['avg_latency_s']}s" if m.get("avg_latency_s") is not None else "-"
        print(f"  {r['model']:<16}{_pct(m['functional_accuracy']):>11}{_pct(m['exact_match']):>9}"
              f"{_pct(m['execution_error_rate']):>9}{_pct(m['partial_correctness']):>10}{lat:>11}")

    print(f"\n  Corrección funcional por complejidad:")
    head = f"  {'Modelo':<16}" + "".join(f"{c:>12}" for c in COMPLEXITY_ORDER)
    print(head)
    print(f"  {'-'*(16+12*len(COMPLEXITY_ORDER))}")
    for r in sorted(reports, key=lambda r: r["metrics"]["functional_accuracy"], reverse=True):
        cells = ""
        for c in COMPLEXITY_ORDER:
            v = r["by_complexity"].get(c)
            cells += f"{_pct(v['functional_accuracy']) if v else '-':>12}"
        print(f"  {r['model']:<16}{cells}")
    print(f"{'='*92}\n")


def _print_md(reports: list[dict]):
    reports = sorted(reports, key=lambda r: r["metrics"]["functional_accuracy"], reverse=True)
    print(f"\n### Comparativa de modelos (split {reports[0]['split']}, n={reports[0]['metrics']['n']})\n")
    print("| Modelo | Funcional | Exact match | Tasa error | Parcial | Latencia |")
    print("|---|---|---|---|---|---|")
    for r in reports:
        m = r["metrics"]
        lat = f"{m['avg_latency_s']}s" if m.get("avg_latency_s") is not None else "-"
        print(f"| {r['model']} | {_pct(m['functional_accuracy'])} | {_pct(m['exact_match'])} "
              f"| {_pct(m['execution_error_rate'])} | {_pct(m['partial_correctness'])} | {lat} |")

    print(f"\n**Corrección funcional por complejidad**\n")
    print("| Modelo | " + " | ".join(COMPLEXITY_ORDER) + " |")
    print("|---|" + "---|" * len(COMPLEXITY_ORDER))
    for r in reports:
        cells = " | ".join(
            _pct(r["by_complexity"][c]["functional_accuracy"]) if c in r["by_complexity"] else "-"
            for c in COMPLEXITY_ORDER
        )
        print(f"| {r['model']} | {cells} |")
    print()


def main():
    ap = argparse.ArgumentParser(description="Comparativa de modelos del benchmark")
    ap.add_argument("files", nargs="*", help="Ficheros results_*.json concretos (opcional)")
    ap.add_argument("--split", default="test", choices=["dev", "test", "all"],
                    help="Split a comparar si no se pasan ficheros (def. test)")
    ap.add_argument("--md", action="store_true", help="Salida en Markdown")
    args = ap.parse_args()

    paths = [Path(f) for f in args.files] if args.files else _latest_per_model(args.split)
    if not paths:
        raise SystemExit(f"No hay resultados para el split '{args.split}' en {RESULTS_DIR}")

    reports = _load(paths)
    (_print_md if args.md else _print_text)(reports)


if __name__ == "__main__":
    main()
