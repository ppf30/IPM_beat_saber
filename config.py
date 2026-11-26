"""Configuración general del juego.

Todos los parámetros ajustables están aquí, de modo que el resto de módulos no
contiene "números mágicos". Se puede crear una variante con
``dataclasses.replace(DEFAULT_CONFIG, approach_time=1.5)``.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Config:
    # --- Ventana ---------------------------------------------------------
    window_size: tuple[int, int] = (1280, 720)
    fps: int = 60

    # --- Cámara y detección ---------------------------------------------
    camera_index: int = 0
    camera_size: tuple[int, int] = (640, 480)
    pose_model_path: Path = BASE_DIR / "detection_models" / "pose_landmarker_full.task"
    min_visibility: float = 0.5  # confianza mínima para dar una muñeca por válida

    # --- Rutas -----------------------------------------------------------
    charts_dir: Path = BASE_DIR / "assets" / "charts"
    audio_dir: Path = BASE_DIR / "assets" / "audio"
    results_dir: Path = BASE_DIR / "results"
    calibration_path: Path = BASE_DIR / "calibration.json"

    # --- Suavizado de la detección --------------------------------------
    smoothing_alpha: float = 0.6   # 1.0 = sin suavizado
    max_tracking_gap: float = 0.15  # s que se mantiene la última posición si se pierde la mano

    # --- Calibración -----------------------------------------------------
    calibration_duration: float = 8.0
    calibration_min_samples: int = 60
    calibration_shrink: float = 0.05  # recorta el rango observado para llegar a los bordes
    default_zone: tuple[float, float, float, float] = (0.15, 0.10, 0.85, 0.90)

    # --- Rejilla de bloques (en fracciones de la ventana) ---------------
    grid_cols: int = 4
    grid_rows: int = 3
    play_area: tuple[float, float, float, float] = (0.15, 0.20, 0.85, 0.80)
    block_radius: float = 46.0   # px
    saber_radius: float = 22.0   # px
    approach_time: float = 1.2   # s que el bloque es visible antes de su momento

    # --- Reglas de golpeo -----------------------------------------------
    perfect_window: float = 0.08  # s
    good_window: float = 0.16
    ok_window: float = 0.25
    min_swing_speed: float = 200.0  # px/s; 0 desactiva el requisito de "corte"
    points_perfect: int = 100
    points_good: int = 70
    points_ok: int = 40
    combo_step: int = 10
    max_multiplier: int = 4

    # --- Partida ---------------------------------------------------------
    countdown: float = 3.0
    end_padding: float = 1.5

    def cell_center(self, col: int, row: int) -> tuple[float, float]:
        """Centro (en px) de una celda de la rejilla."""
        w, h = self.window_size
        x0, y0, x1, y1 = self.play_area
        x = (x0 + (col + 0.5) / self.grid_cols * (x1 - x0)) * w
        y = (y0 + (row + 0.5) / self.grid_rows * (y1 - y0)) * h
        return x, y


DEFAULT_CONFIG = Config()

# --- Niveles de dificultad -------------------------------------------------
# Pensados para adaptar el juego a personas con distinta movilidad o forma física
# (p. ej. rehabilitación o personas mayores frente a un uso más deportivo).
LEVELS: dict[str, dict] = {
    "suave": dict(
        perfect_window=0.12, good_window=0.22, ok_window=0.35,
        approach_time=1.8, min_swing_speed=120.0, block_radius=56.0,
    ),
    "normal": {},
    "intenso": dict(
        perfect_window=0.07, good_window=0.13, ok_window=0.20,
        approach_time=1.0, min_swing_speed=300.0,
    ),
}
# Parámetros del chart generado para cada nivel (tempo y duración en compases).
LEVEL_CHARTS: dict[str, dict] = {
    "suave": dict(bpm=70.0, bars=12),
    "normal": dict(bpm=100.0, bars=16),
    "intenso": dict(bpm=120.0, bars=20),
}
DEFAULT_LEVEL = "normal"


def level_config(base: Config, level: str) -> Config:
    """Config con los parámetros de jugabilidad del nivel indicado."""
    return replace(base, **LEVELS[level])
