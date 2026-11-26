"""Tipos de datos compartidos para manos, bloques y resultados.

Convención de coordenadas (acordada en el README): ``x`` e ``y`` normalizadas
entre 0 y 1, con la imagen en modo espejo y las manos vistas desde la
perspectiva del jugador (``left`` es la mano izquierda del jugador).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Hand(str, Enum):
    LEFT = "left"
    RIGHT = "right"

    @property
    def other(self) -> "Hand":
        return Hand.RIGHT if self is Hand.LEFT else Hand.LEFT


@dataclass(frozen=True)
class HandPosition:
    x: float = 0.0
    y: float = 0.0
    valid: bool = False


@dataclass(frozen=True)
class HandsFrame:
    """Posición de ambas manos en un instante (``timestamp`` en segundos, monotónico)."""

    left: HandPosition
    right: HandPosition
    timestamp: float
    shoulder_width: float = 0.0  # distancia entre hombros (fracción del ancho de imagen); 0 = desconocida

    def get(self, hand: Hand) -> HandPosition:
        return self.left if hand is Hand.LEFT else self.right

    @classmethod
    def empty(cls, timestamp: float = 0.0) -> "HandsFrame":
        return cls(HandPosition(), HandPosition(), timestamp)


@dataclass(frozen=True)
class ChartNote:
    """Un bloque: instante (s) en el que debe golpearse, mano y celda de la rejilla."""

    time: float
    hand: Hand
    col: int
    row: int


@dataclass
class Chart:
    title: str
    bpm: float
    notes: list[ChartNote]
    audio: Optional[str] = None  # nombre de archivo dentro de assets/audio/
    offset: float = 0.0          # instante (s) del beat 0

    @property
    def beat_duration(self) -> float:
        return 60.0 / self.bpm

    @property
    def duration(self) -> float:
        return max((n.time for n in self.notes), default=0.0)


class Judgement(str, Enum):
    PERFECT = "perfect"
    GOOD = "good"
    OK = "ok"
    MISS = "miss"
    WRONG_HAND = "wrong_hand"


HIT_JUDGEMENTS = (Judgement.PERFECT, Judgement.GOOD, Judgement.OK)


class MatchState(Enum):
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    FINISHED = "finished"


@dataclass(frozen=True)
class GameEvent:
    """Resultado de un bloque (acierto/fallo) o un aviso de mano equivocada.

    ``time_error`` > 0 significa golpe tardío; < 0, anticipado (en segundos).
    """

    note: ChartNote
    judgement: Judgement
    time_error: Optional[float]
    hand_speed: Optional[float]
    score: int
    combo: int
