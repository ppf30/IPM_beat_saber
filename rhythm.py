"""Patrones de bloques (charts) y reloj de la partida. El juego no tiene sonido.

Un chart propio es un JSON que se usa con ``python main.py --chart ruta.json``::

    {"title": "Mi patrón", "bpm": 100,
     "notes": [{"beat": 4, "hand": "right", "col": 1, "row": 2}, ...]}

* ``beat``: cuándo debe golpearse el bloque (el beat 0 es el inicio de la partida).
* ``hand``: ``left`` o ``right``.  ``col`` (0-3) y ``row`` (0-2): celda de la rejilla.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Callable, Optional

from config import DEFAULT_LEVEL, LEVEL_CHARTS
from models import Chart, ChartNote, Hand


def load_chart(path: Path) -> Chart:
    """Lee un chart JSON. Lanza ``ValueError`` si el archivo no tiene el formato esperado."""
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


def generate_demo_chart(
    bpm: float = 100.0, bars: int = 16, seed: int = 7, title: str = "Demo"
) -> Chart:
    """Chart de demostración con dificultad creciente en cuatro tramos.

    1. Un bloque cada 2 beats, alternando manos.
    2. Un bloque por beat, alternando manos.
    3. Igual, con golpes simultáneos con ambas manos al inicio de cada compás.
    4. Un bloque por beat más "semi-beats" en los tiempos 2 y 4.
    """
    rng = random.Random(seed)
    beat = 60.0 / bpm
    cols = {Hand.LEFT: (0, 1, 2), Hand.RIGHT: (1, 2, 3)}  # cada mano cubre "su" lado
    last: dict[Hand, Optional[tuple[int, int]]] = {Hand.LEFT: None, Hand.RIGHT: None}
    notes: list[ChartNote] = []

    def add(beat_pos: float, hand: Hand, avoid: Optional[tuple[int, int]] = None) -> tuple[int, int]:
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
            pos = 4 + bar * 4 + b  # el primer compás queda libre
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
    """Chart generado para el nivel indicado (tempo y duración según ``LEVEL_CHARTS``)."""
    return generate_demo_chart(title=f"Demo {level}", **LEVEL_CHARTS[level])


class SongClock:
    """Tiempo de la partida: negativo durante la cuenta atrás y 0 cuando aparece el primer compás."""

    def __init__(self, countdown: float, clock: Callable[[], float] = time.monotonic):
        self._countdown = countdown
        self._clock = clock
        self._t0 = clock()
        self._paused_at: Optional[float] = None

    def start(self) -> None:
        self._t0 = self._clock()
        self._paused_at = None

    def song_time(self) -> float:
        now = self._paused_at if self._paused_at is not None else self._clock()
        return now - self._t0 - self._countdown

    @property
    def paused(self) -> bool:
        return self._paused_at is not None

    def pause(self) -> None:
        if self._paused_at is None:
            self._paused_at = self._clock()

    def resume(self) -> None:
        if self._paused_at is not None:
            self._t0 += self._clock() - self._paused_at
            self._paused_at = None
