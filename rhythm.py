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
    cols = {Hand.LEFT: (0, 1, 2), Hand.RIGHT: (1, 2, 3)}
    last: dict[Hand, Optional[tuple[int, int]]] = {Hand.LEFT: None, Hand.RIGHT: None}
    notes: list[ChartNote] = []

    def add(beat_pos: float, hand: Hand, avoid: Optional[tuple[int, int]] = None) -> tuple[int, int]:
        """Agrega una nota aleatoria evitando repetir celda o coincidir con otra mano"""
        options = [
            (c, r) for c in cols[hand] for r in range(3)
            if (c, r) != last[hand] and (c, r) != avoid
        ]
        cell = rng.choice(options)
        last[hand] = cell
        notes.append(ChartNote(beat_pos * beat, hand, *cell))
        return cell

    stage_len = max(bars // 4, 1)
    hand_order = [Hand.RIGHT, Hand.LEFT]
    n = 0
    for bar in range(bars):
        stage = min(bar // stage_len, 3)
        for b in range(4):
            pos = 4 + bar * 4 + b
            if stage == 0 and b % 2 == 1:
                continue
            if stage == 2 and b == 0:
                cell = add(pos, Hand.RIGHT)
                add(pos, Hand.LEFT, avoid=cell)
            else:
                add(pos, hand_order[n % 2])
                n += 1
            if stage == 3 and b in (1, 3):
                add(pos + 0.5, hand_order[n % 2])
                n += 1
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

            