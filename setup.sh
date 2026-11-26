#!/usr/bin/env bash
# Despliegue en Linux/macOS con Miniconda: crea el entorno y descarga el modelo.
set -euo pipefail
cd "$(dirname "$0")"
ENV_NAME="IPM_beat_saber"

if ! command -v conda >/dev/null 2>&1; then
  echo "No se encuentra 'conda'. Instala Miniconda:" >&2
  echo "  https://www.anaconda.com/docs/getting-started/miniconda/install" >&2
  echo "y abre una terminal nueva (o ejecuta 'conda init')." >&2
  exit 1
fi

if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "El entorno $ENV_NAME ya existe: se actualiza."
  conda env update -n "$ENV_NAME" -f environment.yml --prune
else
  conda env create -f environment.yml
fi

conda run -n "$ENV_NAME" --no-capture-output python download_models.py

echo
echo "Listo. Para jugar:"
echo "  conda activate $ENV_NAME"
echo "  python main.py"
