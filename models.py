"""Tipos de datos compartidos para manos, bloques y resultados"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Hand(str, Enum):
    """Identifica la mano izquierda o derecha del jugador"""

    LEFT = "left"
    RIGHT = "right"

    @property
    def other(self) -> "Hand":
        """Devuelve la mano opuesta a la actual

        Returns:
            Hand: Mano derecha si es izquierda, o izquierda si es derecha
        """
        return Hand.RIGHT if self is Hand.LEFT else Hand.LEFT


@dataclass(frozen=True)
class HandPosition:
    """Posicion normalizada de una mano en pantalla

    Attributes:
        x (float): Coordenada horizontal normalizada entre 0 y 1
        y (float): Coordenada vertical normalizada entre 0 y 1
        valid (bool): Indica si la posicion es valida y visible
    """

    x: float = 0.0
    y: float = 0.0
    valid: bool = False


@dataclass(frozen=True)
class HandsFrame:
    """Posicion de ambas manos y ancho de hombros en un instante dado

    Attributes:
        left (HandPosition): Estado de la mano izquierda
        right (HandPosition): Estado de la mano derecha
        timestamp (float): Marca de tiempo monotonica en segundos
        shoulder_width (float): Distancia normalizada entre hombros o 0 si se desconoce
    """

    left: HandPosition
    right: HandPosition
    timestamp: float
    shoulder_width: float = 0.0

    def get(self, hand: Hand) -> HandPosition:
        """Obtiene la posicion correspondiente a la mano indicada

        Args:
            hand (Hand): Mano a consultar

        Returns:
            HandPosition: Estado de la mano solicitada
        """
        return self.left if hand is Hand.LEFT else self.right

    @classmethod
    def empty(cls, timestamp: float = 0.0) -> "HandsFrame":
        """Crea un frame vacio con manos no validas

        Args:
            timestamp (float): Marca de tiempo asignada al frame

        Returns:
            HandsFrame: Frame inicializado sin deteccion valida
        """
        return cls(HandPosition(), HandPosition(), timestamp)


@dataclass(frozen=True)
class ChartNote:
    """Define un bloque objetivo dentro de un patron de juego

    Attributes:
        time (float): Instante en segundos en que debe golpearse el bloque
        hand (Hand): Mano requerida para golpearlo
        col (int): Columna de la rejilla
        row (int): Fila de la rejilla
    """

    time: float
    hand: Hand
    col: int
    row: int


@dataclass
class Chart:
    """Representa un patron completo con sus bloques y tempo

    Attributes:
        title (str): Titulo del chart
        bpm (float): Pulsaciones por minuto del patron
        notes (list[ChartNote]): Lista de bloques del chart
        duration (float): Duracion total estimada en segundos segun el ultimo bloque
    """

    title: str
    bpm: float
    notes: list[ChartNote]

    @property
    def duration(self) -> float:
        """Devuelve el instante del ultimo bloque o cero si no hay bloques

        Returns:
            float: Duracion en segundos hasta la ultima nota
        """
        return max((n.time for n in self.notes), default=0.0)


class Judgement(str, Enum):
    """Clasificacion del resultado al evaluar un bloque o golpe"""

    PERFECT = "perfect"
    GOOD = "good"
    OK = "ok"
    MISS = "miss"
    WRONG_HAND = "wrong_hand"


HIT_JUDGEMENTS = (Judgement.PERFECT, Judgement.GOOD, Judgement.OK)


class MatchState(Enum):
    """Estados posibles del flujo de una partida"""

    COUNTDOWN = "countdown"
    PLAYING = "playing"
    FINISHED = "finished"


@dataclass(frozen=True)
class GameEvent:
    """Registra el resultado de evaluar un bloque o un golpe con otra mano

    Attributes:
        note (ChartNote): Bloque asociado al evento
        judgement (Judgement): Evaluacion obtenida
        time_error (Optional[float]): Diferencia de tiempo en segundos respecto al objetivo
        hand_speed (Optional[float]): Velocidad de la mano al golpear
        score (int): Puntuacion acumulada tras el evento
        combo (int): Racha actual de aciertos tras el evento
    """

    note: ChartNote
    judgement: Judgement
    time_error: Optional[float]
    hand_speed: Optional[float]
    score: int
    combo: int
    