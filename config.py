"""Configuracion general del juego y niveles de dificultad"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Config:
    """Almacena todos los parametros ajustables de ventana, camara, calibracion y juego

    Attributes:
        window_size (tuple[int, int]): Resolucion de la ventana en pixeles
        fps (int): Cuadros por segundo objetivo del bucle principal
        camera_index (int): Indice del dispositivo de camara
        camera_size (tuple[int, int]): Resolucion de captura solicitada a la camara
        pose_model_path (Path): Ruta al archivo del modelo de MediaPipe
        min_visibility (float): Visibilidad minima requerida para validar un punto
        results_dir (Path): Carpeta donde se guardan los archivos CSV de resultados
        calibration_path (Path): Archivo donde se persiste la calibracion
        smoothing_alpha (float): Factor de suavizado exponencial para las manos
        max_tracking_gap (float): Tiempo maximo en segundos para mantener posicion perdida
        calibration_duration (float): Duracion en segundos de la captura de calibracion
        calibration_min_samples (int): Cantidad minima de muestras validas para calibrar
        calibration_shrink (float): Margen de ajuste aplicado al rango capturado
        default_zone (tuple[float, float, float, float]): Zona de movimiento por defecto
        grid_cols (int): Numero de columnas de la rejilla de bloques
        grid_rows (int): Numero de filas de la rejilla de bloques
        play_area (tuple[float, float, float, float]): Area normalizada ocupada por la rejilla
        block_radius (float): Radio visual y de colision de cada bloque en pixeles
        saber_radius (float): Radio de colision de cada mano o sable en pixeles
        approach_time (float): Tiempo en segundos de antelacion con que aparece cada bloque
        perfect_window (float): Margen temporal en segundos para evaluacion perfecta
        good_window (float): Margen temporal en segundos para evaluacion buena
        ok_window (float): Margen temporal en segundos para evaluacion aceptable
        min_swing_speed (float): Velocidad minima de golpeo en pixeles por segundo
        points_perfect (int): Puntos base por un golpe perfecto
        points_good (int): Puntos base por un golpe bueno
        points_ok (int): Puntos base por un golpe aceptable
        combo_step (int): Cantidad de aciertos consecutivos para subir el multiplicador
        max_multiplier (int): Multiplicador maximo de puntuacion permitido
        countdown (float): Duracion de la cuenta atras inicial en segundos
        end_padding (float): Tiempo adicional en segundos tras el ultimo bloque
    """

    window_size: tuple[int, int] = (1280, 720)
    fps: int = 60

    camera_index: int = 0
    camera_size: tuple[int, int] = (640, 480)
    pose_model_path: Path = BASE_DIR / "detection_models" / "pose_landmarker_full.task"
    min_visibility: float = 0.5

    results_dir: Path = BASE_DIR / "results"
    calibration_path: Path = BASE_DIR / "calibration.json"

    smoothing_alpha: float = 0.6
    max_tracking_gap: float = 0.15

    calibration_duration: float = 8.0
    calibration_min_samples: int = 60
    calibration_shrink: float = 0.05
    default_zone: tuple[float, float, float, float] = (0.15, 0.10, 0.85, 0.90)

    grid_cols: int = 4
    grid_rows: int = 3
    play_area: tuple[float, float, float, float] = (0.15, 0.20, 0.85, 0.80)
    block_radius: float = 50.0
    saber_radius: float = 22.0
    approach_time: float = 1.5

    perfect_window: float = 0.10
    good_window: float = 0.20
    ok_window: float = 0.30
    min_swing_speed: float = 150.0
    points_perfect: int = 100
    points_good: int = 70
    points_ok: int = 40
    combo_step: int = 10
    max_multiplier: int = 4

    countdown: float = 3.0
    end_padding: float = 1.5

    def cell_center(self, col: int, row: int) -> tuple[float, float]:
        """Calcula las coordenadas en pixeles del centro de una celda de la rejilla

        Args:
            col (int): Indice de columna de la celda
            row (int): Indice de fila de la celda

        Returns:
            tuple[float, float]: Coordenadas (x, y) en pixeles del centro de la celda
        """
        w, h = self.window_size
        x0, y0, x1, y1 = self.play_area
        x = (x0 + (col + 0.5) / self.grid_cols * (x1 - x0)) * w
        y = (y0 + (row + 0.5) / self.grid_rows * (y1 - y0)) * h
        return x, y


DEFAULT_CONFIG = Config()

LEVELS: dict[str, dict] = {
    "suave": dict(
        perfect_window=0.14, good_window=0.24, ok_window=0.38,
        approach_time=2.0, min_swing_speed=100.0, block_radius=58.0,
    ),
    "normal": {},
    "intenso": dict(
        perfect_window=0.08, good_window=0.15, ok_window=0.24,
        approach_time=1.2, min_swing_speed=220.0,),}

LEVEL_CHARTS: dict[str, dict] = {
    "suave": dict(bpm=60.0, bars=12),
    "normal": dict(bpm=80.0, bars=16),
    "intenso": dict(bpm=100.0, bars=20),}

DEFAULT_LEVEL = "normal"


def level_config(base: Config, level: str) -> Config:
    """Crea una copia de configuracion aplicando los ajustes del nivel indicado

    Args:
        base (Config): Configuracion base de partida
        level (str): Nombre del nivel definido en LEVELS

    Returns:
        Config: Nueva configuracion con los parametros del nivel
    """
    return replace(base, **LEVELS[level])