"""Lectura de patrones de bloques y sincronización temporal.

Formato de un chart (JSON) en ``assets/charts/``::

    {"title": "Demo", "bpm": 100, "offset": 0.0, "audio": "cancion.ogg",
     "notes": [{"beat": 4, "hand": "right", "col": 1, "row": 2}, ...]}

* ``beat`` (o ``time`` en segundos) indica cuándo debe golpearse el bloque.
* ``hand`` es ``left`` o ``right``; ``col`` 0-3 y ``row`` 0-2 son la celda.
* ``audio`` es opcional. Sin audio, suena un metrónomo sencillo.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from config import DEFAULT_CONFIG, DEFAULT_LEVEL, LEVEL_CHARTS, Config
from models import Chart, ChartNote, Hand


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
def chart_from_dict(data: dict) -> Chart:
    bpm = float(data["bpm"])
    offset = float(data.get("offset", 0.0))
    beat = 60.0 / bpm
    notes = []
    for n in data["notes"]:
        t = float(n["time"]) if "time" in n else offset + float(n["beat"]) * beat
        notes.append(ChartNote(t, Hand(n["hand"]), int(n["col"]), int(n["row"])))
    notes.sort(key=lambda n: n.time)
    return Chart(str(data.get("title", "Sin título")), bpm, notes, data.get("audio"), offset)


def chart_to_dict(chart: Chart) -> dict:
    return {
        "title": chart.title,
        "bpm": chart.bpm,
        "offset": chart.offset,
        "audio": chart.audio,
        "notes": [
            {
                "beat": round((n.time - chart.offset) / chart.beat_duration, 4),
                "hand": n.hand.value,
                "col": n.col,
                "row": n.row,
            }
            for n in chart.notes
        ],
    }


def load_chart(path: Path) -> Chart:
    return chart_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def save_chart(chart: Chart, path: Path) -> None:
    Path(path).write_text(json.dumps(chart_to_dict(chart), indent=1), encoding="utf-8")


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


# --------------------------------------------------------------------------
# Conductor: reloj de la canción, música y metrónomo
# --------------------------------------------------------------------------
def _make_tone(freq: float, ms: int = 45, volume: float = 0.35):
    import pygame

    rate, _fmt, channels = pygame.mixer.get_init()
    n = int(rate * ms / 1000)
    t = np.arange(n) / rate
    wave = (np.sin(2 * np.pi * freq * t) * np.exp(-t * 70) * volume * 32767).astype(np.int16)
    if channels == 2:
        wave = np.column_stack([wave, wave])
    return pygame.sndarray.make_sound(np.ascontiguousarray(wave))


class Conductor:
    """Reloj maestro: ``song_time`` es negativo durante la cuenta atrás y 0 al sonar la música."""

    def __init__(
        self,
        chart: Chart,
        config: Config = DEFAULT_CONFIG,
        clock: Callable[[], float] = time.monotonic,
        audio: bool = True,
    ):
        self.chart = chart
        self.cfg = config
        self._clock = clock
        self._t0 = 0.0
        self._paused_at: Optional[float] = None
        self._music = False
        self._music_started = False
        self._clicks: Optional[tuple] = None
        self._next_beat = 0
        if audio:
            self._init_audio()

    def _init_audio(self) -> None:
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init()
            audio_path = self.cfg.audio_dir / self.chart.audio if self.chart.audio else None
            if audio_path is not None and audio_path.exists():
                pygame.mixer.music.load(str(audio_path))
                self._music = True
            elif pygame.mixer.get_init()[1] == -16:
                self._clicks = (_make_tone(1500), _make_tone(1000))  # acento, normal
        except Exception as exc:  # sin audio el juego sigue funcionando
            print(f"[audio] desactivado: {exc}")

    # -- control ------------------------------------------------------------
    def start(self) -> None:
        self._t0 = self._clock()
        self._paused_at = None
        self._music_started = False
        self._next_beat = 0

    def song_time(self) -> float:
        ref = self._paused_at if self._paused_at is not None else self._clock()
        return ref - self._t0 - self.cfg.countdown

    def update(self) -> float:
        """Avanza el audio y devuelve el instante actual de la canción."""
        t = self.song_time()
        if self._paused_at is not None or t < 0:
            return t
        if self._music and not self._music_started:
            import pygame

            pygame.mixer.music.play()
            self._music_started = True
        elif self._clicks and not self._music:
            beat = self.chart.beat_duration
            while True:
                beat_time = self.chart.offset + self._next_beat * beat
                if beat_time > t or beat_time > self.chart.duration + beat:
                    break
                if t - beat_time < 0.1:  # no recuperar clics muy atrasados
                    self._clicks[0 if self._next_beat % 4 == 0 else 1].play()
                self._next_beat += 1
        return t

    def pause(self) -> None:
        if self._paused_at is None:
            self._paused_at = self._clock()
            if self._music_started:
                import pygame

                pygame.mixer.music.pause()

    def resume(self) -> None:
        if self._paused_at is not None:
            self._t0 += self._clock() - self._paused_at
            self._paused_at = None
            if self._music_started:
                import pygame

                pygame.mixer.music.unpause()

    @property
    def paused(self) -> bool:
        return self._paused_at is not None

    def stop(self) -> None:
        if self._music_started:
            import pygame

            pygame.mixer.music.stop()


def chart_for_level(level: str = DEFAULT_LEVEL, config: Config = DEFAULT_CONFIG) -> Chart:
    """Chart del nivel: ``assets/charts/<nivel>.json`` si existe; si no, se genera."""
    path = config.charts_dir / f"{level}.json"
    if path.exists():
        return load_chart(path)
    return generate_demo_chart(title=f"Demo {level}", **LEVEL_CHARTS[level])


if __name__ == "__main__":  # python rhythm.py -> regenera assets/charts/<nivel>.json
    DEFAULT_CONFIG.charts_dir.mkdir(parents=True, exist_ok=True)
    for lvl, params in LEVEL_CHARTS.items():
        target = DEFAULT_CONFIG.charts_dir / f"{lvl}.json"
        save_chart(generate_demo_chart(title=f"Demo {lvl}", **params), target)
        print(f"Chart del nivel '{lvl}' escrito en {target}")
