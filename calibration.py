"""Adaptación de coordenadas y zona de movimiento.

El jugador mueve los brazos al máximo alcance cómodo durante unos segundos; la
caja que recorren las muñecas se convierte en la "zona de movimiento", que se
estira para cubrir toda la pantalla de juego. Así el juego se adapta a la
altura, la distancia a la cámara y la movilidad de cada persona.
"""
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
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


@dataclass(frozen=True)
class MovementZone:
    """Rectángulo (en coordenadas de cámara normalizadas) mapeado a toda la pantalla."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    MIN_SIZE = 0.10

    def to_screen(self, x: float, y: float) -> tuple[float, float]:
        w = max(self.x_max - self.x_min, self.MIN_SIZE)
        h = max(self.y_max - self.y_min, self.MIN_SIZE)
        return _clamp01((x - self.x_min) / w), _clamp01((y - self.y_min) / h)

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.x_min, self.y_min, self.x_max, self.y_max)


IDENTITY_ZONE = MovementZone(0.0, 0.0, 1.0, 1.0)


class Calibration:
    """Transforma un ``HandsFrame`` de cámara en uno en coordenadas de pantalla."""

    def __init__(self, zone: MovementZone, shoulder_width: float = 0.0):
        self.zone = zone
        self.shoulder_width = shoulder_width  # fracción del ancho de imagen; 0 = desconocida

    def range_of_motion(self, aspect: float = 0.75) -> Optional[tuple[float, float]]:
        """Amplitud de movimiento (horizontal, vertical) en anchos de hombro.

        Normalizar por el ancho de hombros hace la medida independiente de la
        distancia a la cámara. ``aspect`` = alto/ancho de la imagen de cámara.
        Es una estimación orientativa en 2D, no una medida clínica.
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
        return cls(IDENTITY_ZONE)

    @classmethod
    def default(cls, config: Config = DEFAULT_CONFIG) -> "Calibration":
        return cls(MovementZone(*config.default_zone))

    def apply(self, frame: HandsFrame) -> HandsFrame:
        def map_hand(p: HandPosition) -> HandPosition:
            if not p.valid:
                return p
            return HandPosition(*self.zone.to_screen(p.x, p.y), True)

        return HandsFrame(map_hand(frame.left), map_hand(frame.right), frame.timestamp)

    # -- persistencia -------------------------------------------------------
    def save(self, path: Path) -> None:
        data = {"zone": self.zone.as_tuple(), "shoulder_width": self.shoulder_width}
        Path(path).write_text(json.dumps(data), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Optional["Calibration"]:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return cls(MovementZone(*map(float, data["zone"])), float(data.get("shoulder_width", 0.0)))
        except (OSError, ValueError, KeyError, TypeError):
            return None


class Calibrator:
    """Recoge posiciones de las muñecas durante ``duration`` s y calcula la zona."""

    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.cfg = config
        self._xs: list[float] = []
        self._ys: list[float] = []
        self._shoulders: list[float] = []
        self._start: Optional[float] = None

    def start(self, now: float) -> None:
        self._xs.clear()
        self._ys.clear()
        self._shoulders.clear()
        self._start = now

    @property
    def running(self) -> bool:
        return self._start is not None

    @property
    def n_samples(self) -> int:
        return len(self._xs)

    def progress(self, now: float) -> float:
        if self._start is None:
            return 0.0
        return min((now - self._start) / self.cfg.calibration_duration, 1.0)

    def finished(self, now: float) -> bool:
        return self.running and self.progress(now) >= 1.0

    def add(self, frame: HandsFrame) -> None:
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
        """Zona calculada con las muestras actuales (``None`` si hay pocas)."""
        if len(self._xs) < self.cfg.calibration_min_samples:
            return None
        x_lo, x_hi = np.percentile(self._xs, [3, 97])
        y_lo, y_hi = np.percentile(self._ys, [3, 97])
        # Se recorta un poco el rango para que los bordes de la pantalla sean alcanzables.
        sx = (x_hi - x_lo) * self.cfg.calibration_shrink
        sy = (y_hi - y_lo) * self.cfg.calibration_shrink
        return MovementZone(
            float(x_lo + sx), float(y_lo + sy), float(x_hi - sx), float(y_hi - sy)
        )

    def result(self) -> Optional[Calibration]:
        zone = self.current_zone()
        if zone is None:
            return None
        shoulder = statistics.median(self._shoulders) if self._shoulders else 0.0
        return Calibration(zone, shoulder)


class HandSmoother:
    """Suavizado exponencial y tolerancia a pérdidas breves de detección."""

    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.cfg = config
        self._last: dict[Hand, Optional[tuple[float, float, float]]] = {
            Hand.LEFT: None, Hand.RIGHT: None
        }  # (x, y, instante de la última detección válida)
        self._last_input_ts: Optional[float] = None
        self._last_output: Optional[HandsFrame] = None

    def apply(self, frame: HandsFrame) -> HandsFrame:
        # El juego va a 60 fps y la cámara a ~30: no se re-suaviza el mismo dato.
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
                out[hand] = HandPosition(prev[0], prev[1], True)  # mantiene la última posición
            else:
                self._last[hand] = None
                out[hand] = HandPosition()
        result = HandsFrame(out[Hand.LEFT], out[Hand.RIGHT], frame.timestamp)
        self._last_input_ts = frame.timestamp
        self._last_output = result
        return result
