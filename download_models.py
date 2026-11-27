"""Descarga los modelos de MediaPipe Pose Landmarker"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://storage.googleapis.com/mediapipe-models/pose_landmarker"
MODELS = {
    "pose_landmarker_full.task": f"{BASE}/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
    "pose_landmarker_lite.task": f"{BASE}/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
    "pose_landmarker_heavy.task": f"{BASE}/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task",
}
TARGET_DIR = Path(__file__).resolve().parent / "detection_models"


def download(name: str, url: str) -> bool:
    """Descarga un archivo de modelo si no existe previamente en el directorio destino

    Args:
        name (str): Nombre del archivo de modelo a guardar
        url (str): Direccion URL desde donde descargar el modelo

    Returns:
        bool: Verdadero si el archivo esta disponible o se descargo con exito
    """
    dest = TARGET_DIR / name
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[ok] {name} ya existe, se omite la descarga.")
        return True
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    print(f"Descargando {name} ...")
    try:
        with urllib.request.urlopen(url, timeout=30) as resp, tmp.open("wb") as out:
            total = int(resp.headers.get("Content-Length", 0))
            done = 0
            while chunk := resp.read(1 << 16):
                out.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {done / 1e6:5.1f} / {total / 1e6:.1f} MB", end="", flush=True)
        tmp.replace(dest)
        print(f"\n[ok] guardado en {dest}")
        return True
    except (urllib.error.URLError, OSError) as exc:
        tmp.unlink(missing_ok=True)
        print(f"\n[error] no se pudo descargar {name}: {exc}", file=sys.stderr)
        print(f"        Descárgalo a mano de {url}\n        y guárdalo en {dest}", file=sys.stderr)
        return False


def main() -> int:
    """Procesa los argumentos de entrada y ejecuta la descarga de modelos

    Returns:
        int: Cero si todas las descargas fueron exitosas o uno en caso de error
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true", help="descargar también lite y heavy")
    args = parser.parse_args()
    names = list(MODELS) if args.all else ["pose_landmarker_full.task"]
    return 0 if all([download(n, MODELS[n]) for n in names]) else 1


if __name__ == "__main__":
    sys.exit(main())