"""Adaptacion de coordenadas y zona de movimiento"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from config import DEFAULT_CONFIG, Config
from models import Hand, HandPosition, HandsFrame


def _clamp01(v: float) -> float:
    """Limita un valor flotante al intervalo cerrado entre 0 y 1

    Args:
        v (float): Valor numerico de entrada

    Returns:
        float: Valor acotado dentro del rango de 0 a 1
    """
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


@dataclass(frozen=True)
class MovementZone:
    """Rectangulo en coordenadas normalizadas mapeado a toda la pantalla

    Attributes:
        x_min (float): Limite izquierdo normalizado de la zona
        y_min (float): Limite superior normalizado de la zona
        x_max (float): Limite derecho normalizado de la zona
        y_max (float): Limite inferior normalizado de la zona
        MIN_SIZE (float): Tamanyo minimo permitido para el ancho o alto de la zona
    """

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    MIN_SIZE = 0.10

    def to_screen(self, x: float, y: float) -> tuple[float, float]:
        """Transforma coordenadas de entrada a coordenadas normalizadas de pantalla

        Args:
            x (float): Coordenada horizontal normalizada de entrada
            y (float): Coordenada vertical normalizada de entrada

        Returns:
            tuple[float, float]: Coordenadas normalizadas mapeadas a la pantalla
        """
        w = max(self.x_max - self.x_min, self.MIN_SIZE)
        h = max(self.y_max - self.y_min, self.MIN_SIZE)
        return _clamp01((x - self.x_min) / w), _clamp01((y - self.y_min) / h)

    def as_tuple(self) -> tuple[float, float, float, float]:
        """Devuelve los limites de la zona como una tupla de cuatro flotantes

        Returns:
            tuple[float, float, float, float]: Tupla con x_min, y_min, x_max y y_max
        """
        return (self.x_min, self.y_min, self.x_max, self.y_max)


IDENTITY_ZONE = MovementZone(0.0, 0.0, 1.0, 1.0)


class Calibration:
    """Transforma un frame de camara en coordenadas normalizadas de pantalla

    Attributes:
        zone (MovementZone): Zona de movimiento activa
        shoulder_width (float): Ancho de hombros normalizado o cero si se desconoce
    """

    def __init__(self, zone: MovementZone, shoulder_width: float = 0.0):
        """Inicializa la calibracion con una zona y un ancho de hombros opcional

        Args:
            zone (MovementZone): Zona de movimiento mapeada a pantalla
            shoulder_width (float): Fraccion del ancho de imagen entre hombros
        """
        self.zone = zone
        self.shoulder_width = shoulder_width

    def range_of_motion(self, aspect: float = 0.75) -> Optional[tuple[float, float]]:
        """Calcula el rango de movimiento horizontal y vertical en anchos de hombro

        Args:
            aspect (float): Relacion alto entre ancho de la imagen de camara

        Returns:
            Optional[tuple[float, float]]: Amplitud en x e y en anchos de hombro o None
        """
        if self.shoulder_width <= 0:
            return None
        z = self.zone
        return (
            (z.x_max - z.x_min) / self.shoulder_width,
            (z.y_max - z.y_min) * aspect / self.shoulder_width,
        )

    @classmethod
    def identity(cls) -> "Calibration":
        """Crea una calibracion sin transformacion usando la zona completa

        Returns:
            Calibration: Instancia configurada con IDENTITY_ZONE
        """
        return cls(IDENTITY_ZONE)

    @classmethod
    def default(cls, config: Config = DEFAULT_CONFIG) -> "Calibration":
        """Crea una calibracion inicial a partir de la zona por defecto de la configuracion

        Args:
            config (Config): Configuracion con la zona por defecto

        Returns:
            Calibration: Instancia inicializada con default_zone
        """
        return cls(MovementZone(*config.default_zone))

    def apply(self, frame: HandsFrame) -> HandsFrame:
        """Aplica la calibracion a las posiciones validas de un frame de manos

        Args:
            frame (HandsFrame): Frame de entrada con posiciones de ambas manos

        Returns:
            HandsFrame: Nuevo frame con coordenadas transformadas a pantalla
        """
        def map_hand(p: HandPosition) -> HandPosition:
            if not p.valid:
                return p
            return HandPosition(*self.zone.to_screen(p.x, p.y), True)

        return HandsFrame(map_hand(frame.left), map_hand(frame.right), frame.timestamp)

    def save(self, path: Path) -> None:
        """Guarda la zona y el ancho de hombros en un archivo JSON

        Args:
            path (Path): Ruta del archivo destino
        """
        data = {"zone": self.zone.as_tuple(), "shoulder_width": self.shoulder_width}
        Path(path).write_text(json.dumps(data), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Optional["Calibration"]:
        """Carga una calibracion desde un archivo JSON si es valido

        Args:
            path (Path): Ruta del archivo JSON a leer

        Returns:
            Optional[Calibration]: Calibracion cargada o None si falla la lectura
        """
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return cls(MovementZone(*map(float, data["zone"])), float(data.get("shoulder_width", 0.0)))
        except (OSError, ValueError, KeyError, TypeError):
            return None


class Calibrator:
    """Captura muestras de munyecas durante un tiempo y calcula la zona de movimiento

    Attributes:
        cfg (Config): Configuracion de duracion, muestras minimas y recorte
        running (bool): Indica si la captura esta activa
        n_samples (int): Numero de coordenadas registradas hasta el momento
    """

    def __init__(self, config: Config = DEFAULT_CONFIG):
        """Inicializa el calibrador con la configuracion indicada

        Args:
            config (Config): Parametros de calibracion
        """
        self.cfg = config
        self._xs: list[float] = []
        self._ys: list[float] = []
        self._shoulders: list[float] = []
        self._start: Optional[float] = None

    def start(self, now: float) -> None:
        """Limpia las muestras anteriores e inicia el periodo de captura

        Args:
            now (float): Marca de tiempo de inicio en segundos
        """
        self._xs.clear()
        self._ys.clear()
        self._shoulders.clear()
        self._start = now

    @property
    def running(self) -> bool:
        """Indica si el proceso de calibracion ha comenzado

        Returns:
            bool: Verdadero si esta en curso y falso en caso contrario
        """
        return self._start is not None

    @property
    def n_samples(self) -> int:
        """Devuelve la cantidad de muestras de posicion acumuladas

        Returns:
            int: Numero total de coordenadas almacenadas
        """
        return len(self._xs)

    def progress(self, now: float) -> float:
        """Calcula el porcentaje de avance temporal de la calibracion

        Args:
            now (float): Marca de tiempo actual en segundos

        Returns:
            float: Progreso acotado entre 0 y 1
        """
        if self._start is None:
            return 0.0
        return min((now - self._start) / self.cfg.calibration_duration, 1.0)

    def finished(self, now: float) -> bool:
        """Indica si se cumplio la duracion configurada para la calibracion

        Args:
            now (float): Marca de tiempo actual en segundos

        Returns:
            bool: Verdadero si la captura llego a su fin
        """
        return self.running and self.progress(now) >= 1.0

    def add(self, frame: HandsFrame) -> None:
        """Registra las posiciones validas de las manos y el ancho de hombros del frame

        Args:
            frame (HandsFrame): Frame capturado durante la calibracion
        """
        if not self.running:
            return
        if frame.shoulder_width > 0:
            self._shoulders.append(frame.shoulder_width)
        for hand in (Hand.LEFT, Hand.RIGHT):
            p = frame.get(hand)
            if p.valid:
                self._xs.append(p.x)
                self._ys.append(p.y)

    def current_zone(self) -> Optional[MovementZone]:
        """Calcula la zona de movimiento a partir de las muestras recolectadas

        Returns:
            Optional[MovementZone]: Zona ajustada o None si no hay muestras suficientes
        """
        if len(self._xs) < self.cfg.calibration_min_samples:
            return None
        x_lo, x_hi = np.percentile(self._xs, [3, 97])
        y_lo, y_hi = np.percentile(self._ys, [3, 97])
        sx = (x_hi - x_lo) * self.cfg.calibration_shrink
        sy = (y_hi - y_lo) * self.cfg.calibration_shrink
        return MovementZone(
            float(x_lo + sx), float(y_lo + sy), float(x_hi - sx), float(y_hi - sy)
        )

    def result(self) -> Optional[Calibration]:
        """Construye el objeto Calibration final a partir de los datos capturados

        Returns:
            Optional[Calibration]: Calibracion resultante o None si no es valida
        """
        zone = self.current_zone()
        if zone is None:
            return None
        shoulder = statistics.median(self._shoulders) if self._shoulders else 0.0
        return Calibration(zone, shoulder)


class HandSmoother:
    """Aplica suavizado exponencial y mantiene posiciones ante perdidas breves

    Attributes:
        cfg (Config): Configuracion de suavizado y tiempo maximo de retencion
    """

    def __init__(self, config: Config = DEFAULT_CONFIG):
        """Inicializa el suavizador de posiciones de manos

        Args:
            config (Config): Parametros de suavizado y seguimiento
        """
        self.cfg = config
        self._last: dict[Hand, Optional[tuple[float, float, float]]] = {
            Hand.LEFT: None, Hand.RIGHT: None
        }
        self._last_input_ts: Optional[float] = None
        self._last_output: Optional[HandsFrame] = None

    def apply(self, frame: HandsFrame) -> HandsFrame:
        """Devuelve un frame suavizado para ambas manos en el instante dado

        Args:
            frame (HandsFrame): Frame de entrada con posiciones actuales

        Returns:
            HandsFrame: Frame suavizado o retenido segun la configuracion
        """
        if frame.timestamp == self._last_input_ts and self._last_output is not None:
            return self._last_output
        a = self.cfg.smoothing_alpha
        out: dict[Hand, HandPosition] = {}
        for hand in (Hand.LEFT, Hand.RIGHT):
            p = frame.get(hand)
            prev = self._last[hand]
            if p.valid:
                if prev is not None:
                    x = a * p.x + (1 - a) * prev[0]
                    y = a * p.y + (1 - a) * prev[1]
                else:
                    x, y = p.x, p.y
                self._last[hand] = (x, y, frame.timestamp)
                out[hand] = HandPosition(x, y, True)
            elif prev is not None and frame.timestamp - prev[2] <= self.cfg.max_tracking_gap:
                out[hand] = HandPosition(prev[0], prev[1], True)
            else:
                self._last[hand] = None
                out[hand] = HandPosition()
        result = HandsFrame(out[Hand.LEFT], out[Hand.RIGHT], frame.timestamp)
        self._last_input_ts = frame.timestamp
        self._last_output = result
        return result

    