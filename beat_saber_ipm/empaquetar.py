"""Crea el .zip de la entrega con el nombre pedido en el enunciado.

Uso (desde la raíz del repositorio o desde esta carpeta):

    python empaquetar.py nombre_apellido1_apellido2_nombre_apellido1_apellido2

Genera ``<nombre>.zip`` con el juego, sin entornos, cachés, resultados ni
calibraciones personales. Si ya descargaste el modelo (download_models.py) se
incluye, para que el juego funcione también sin conexión.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXCLUDED_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", ".mypy_cache"}
EXCLUDED_NAMES = {"calibration.json", "empaquetar.py"}  # empaquetar.py no hace falta en la entrega


def should_include(path: Path) -> bool:
    rel = path.relative_to(HERE)
    if any(part in EXCLUDED_DIRS for part in rel.parts) or path.name in EXCLUDED_NAMES:
        return False
    if rel.parts[0] == "results" and path.suffix == ".csv":
        return False
    return path.is_file()


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    name = sys.argv[1].removesuffix(".zip")
    out = HERE.parent / f"{name}.zip"
    root = Path(name)  # carpeta raíz dentro del zip
    files = sorted(p for p in HERE.rglob("*") if should_include(p))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, root / p.relative_to(HERE))
    has_model = any(p.suffix == ".task" for p in files)
    print(f"Creado {out}  ({len(files)} archivos, modelo incluido: {'sí' if has_model else 'no'})")
    if not has_model:
        print("Aviso: sin modelo en el zip; se descargará al ejecutar setup / download_models.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
