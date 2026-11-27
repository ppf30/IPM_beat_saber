"""Patrones de bloques y reloj de la partida"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Callable, Optional

from config import DEFAULT_LEVEL, LEVEL_CHARTS
from models import Chart, ChartNote, Hand


def load_chart(path: Path) -> Chart:
    """Lee un chart JSON y devuelve la estructura con las notas ordenadas por tiempo

    Args:
        path (Path): Ruta del archivo JSON del chart

    Returns:
        Chart: Objeto con titulo, bpm y lista de notas

    Raises:
        ValueError: Si el archivo no tiene el formato esperado
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        beat = 60.0 / float(data["bpm"])
        notes = [
            ChartNote(float(n["beat"]) * beat, Hand(n["hand"]), int(n["col"]), int(n["row"]))
            for n in data["notes"]
        ]
    except (KeyError, TypeError, ZeroDivisionError) as exc:
        raise ValueError(f"Chart no válido ({path}): {exc!r}") from exc
    notes.sort(key=lambda n: n.time)
    return Chart(str(data.get("title", "Sin título")), float(data["bpm"]), notes)


def generate_demo_chart(bpm: float = 100.0, bars: int = 16, seed: int = 7, title: str = "Demo") -> Chart:
    """Genera un chart de demostracion con dificultad progresiva en cuatro tramos

    Reglas para que el juego sea comodo y las manos no se estorben:
    cada mano trabaja solo en su mitad de la rejilla (izquierda: columnas 0-1, derecha:
    columnas 2-3), cada nota aparece en una celda contigua a la anterior de esa mano y
    una misma mano nunca tiene dos bloques con menos de 2 beats de separacion.

    Tramos: 1) un bloque cada 2 beats; 2) un bloque por beat alternando manos;
    3) igual, y cada dos compases un golpe doble (ambas manos a la vez);
    4) golpe doble en todos los compases

    Args:
        bpm (float): Pulsaciones por minuto del patron
        bars (int): Cantidad de compases a generar
        seed (int): Semilla para el generador aleatorio
        title (str): Titulo asignado al chart

    Returns:
        Chart: Chart generado y ordenado por tiempo de aparicion
    """
    rng = random.Random(seed)
    beat = 60.0 / bpm
    cols = {Hand.LEFT: (0, 1), Hand.RIGHT: (2, 3)}
    last_cell: dict[Hand, Optional[tuple[int, int]]] = {Hand.LEFT: None, Hand.RIGHT: None}
    last_pos = {Hand.LEFT: -10.0, Hand.RIGHT: -10.0}
    notes: list[ChartNote] = []

    def can_play(hand: Hand, pos: float) -> bool:
        """Indica si la mano lleva al menos 2 beats sin tener un bloque"""
        return pos - last_pos[hand] >= 2

    def add(pos: float, hand: Hand) -> None:
        """Agrega una nota en la mitad de la mano, en una celda contigua a su ultima nota"""
        prev = last_cell[hand]
        options = [
            (c, r) for c in cols[hand] for r in range(3)
            if (c, r) != prev and (prev is None or (abs(c - prev[0]) <= 1 and abs(r - prev[1]) <= 1))
        ]
        cell = rng.choice(options)
        last_cell[hand] = cell
        last_pos[hand] = pos
        notes.append(ChartNote(pos * beat, hand, *cell))

    def add_single(pos: float) -> None:
        """Agrega un bloque a la mano que lleva mas tiempo sin tocar (la derecha si empatan)"""
        hand = min((Hand.RIGHT, Hand.LEFT), key=lambda h: last_pos[h])
        if can_play(hand, pos):
            add(pos, hand)

    def add_double(pos: float) -> None:
        """Agrega un golpe doble, una nota por mano, si ambas llevan 2 beats sin tocar"""
        if can_play(Hand.LEFT, pos) and can_play(Hand.RIGHT, pos):
            add(pos, Hand.RIGHT)
            add(pos, Hand.LEFT)

    stage_len = max(bars // 4, 1)
    for bar in range(bars):
        stage = min(bar // stage_len, 3)
        with_double = stage == 3 or (stage == 2 and bar % 2 == 0)
        for b in range(4):
            pos = 4 + bar * 4 + b
            if stage == 0:
                if b % 2 == 0:
                    add_single(pos)
            elif with_double:
                if b == 0:
                    add_single(pos)
                elif b == 2:
                    add_double(pos)
            else:
                add_single(pos)
    notes.sort(key=lambda x: x.time)
    return Chart(title, bpm, notes)


def chart_for_level(level: str = DEFAULT_LEVEL) -> Chart:
    """Devuelve el chart de demostracion correspondiente al nivel indicado

    Args:
        level (str): Clave del nivel dentro de LEVEL_CHARTS

    Returns:
        Chart: Chart configurado para el nivel solicitado
    """
    return generate_demo_chart(title=f"Demo {level}", **LEVEL_CHARTS[level])


class SongClock:
    """Controla el tiempo de la partida con soporte para cuenta atras y pausa

    Attributes:
        paused (bool): Indica si el reloj esta pausado en este momento
    """

    def __init__(self, countdown: float, clock: Callable[[], float] = time.monotonic):
        """Inicializa el reloj de la cancion con su cuenta atras inicial

        Args:
            countdown (float): Duracion de la cuenta atras en segundos
            clock (Callable): Funcion que devuelve el tiempo actual en segundos
        """
        self._countdown = countdown
        self._clock = clock
        self._t0 = clock()
        self._paused_at: Optional[float] = None

    def start(self) -> None:
        """Reinicia el tiempo inicial y limpia el estado de pausa"""
        self._t0 = self._clock()
        self._paused_at = None

    def song_time(self) -> float:
        """Devuelve el tiempo transcurrido de la partida descontando la cuenta atras

        Returns:
            float: Tiempo actual en segundos relativo al inicio del primer compas
        """
        now = self._paused_at if self._paused_at is not None else self._clock()
        return now - self._t0 - self._countdown

    @property
    def paused(self) -> bool:
        """Indica si el reloj se encuentra pausado

        Returns:
            bool: Verdadero si esta pausado y falso en caso contrario
        """
        return self._paused_at is not None

    def pause(self) -> None:
        """Guarda el instante en que se pausa el reloj"""
        if self._paused_at is None:
            self._paused_at = self._clock()

    def resume(self) -> None:
        """Reanuda el reloj ajustando el inicio con el tiempo pausado"""
        if self._paused_at is not None:
            self._t0 += self._clock() - self._paused_at
            self._paused_at = None

            