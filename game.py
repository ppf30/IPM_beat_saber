"""Reglas, colisiones, puntuación y estados de partida.

``Game`` no sabe nada de pantalla ni cámara: recibe el tiempo de la
canción y la posición de las manos (ya calibradas) y devuelve eventos. Eso lo
hace fácil de probar con datos sintéticos.
"""
from __future__ import annotations

import math
from typing import Optional

from config import DEFAULT_CONFIG, Config
from models import (
    HIT_JUDGEMENTS,
    Chart,
    ChartNote,
    GameEvent,
    Hand,
    HandsFrame,
    Judgement,
    MatchState,
)

_SPEED_SMOOTHING = 0.5


class _NoteState:
    __slots__ = ("note", "done", "wrong_reported")

    def __init__(self, note: ChartNote):
        self.note = note
        self.done = False
        self.wrong_reported = False


class Game:
    def __init__(self, chart: Chart, config: Config = DEFAULT_CONFIG):
        self.chart = chart
        self.cfg = config
        self._notes = [_NoteState(n) for n in sorted(chart.notes, key=lambda n: n.time)]
        self._cursor = 0  # primer bloque aún sin resolver
        self.state = MatchState.COUNTDOWN
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.wrong_hand_count = 0
        self.results: list[GameEvent] = []  # un evento final (acierto o fallo) por bloque
        self.frames_total = 0
        self.frames_lost = {Hand.LEFT: 0, Hand.RIGHT: 0}
        self.end_time = chart.duration + config.end_padding
        self._speed = {Hand.LEFT: 0.0, Hand.RIGHT: 0.0}  # px/s
        self._prev: dict[Hand, Optional[tuple[tuple[float, float], float]]] = {
            Hand.LEFT: None, Hand.RIGHT: None
        }
        self._last_ts: Optional[float] = None

    # -- consultas ----------------------------------------------------------
    @property
    def total_notes(self) -> int:
        return len(self._notes)

    @property
    def hits(self) -> int:
        return sum(1 for r in self.results if r.judgement in HIT_JUDGEMENTS)

    @property
    def accuracy(self) -> float:
        return self.hits / self.total_notes if self.total_notes else 0.0

    def progress(self, song_time: float) -> float:
        return min(max(song_time / self.end_time, 0.0), 1.0) if self.end_time > 0 else 1.0

    def visible_notes(self, song_time: float) -> list[tuple[ChartNote, float]]:
        """Bloques por dibujar y su ``progress`` (1 = acaba de aparecer, 0 = momento de golpear)."""
        out = []
        for ns in self._notes[self._cursor:]:
            ahead = ns.note.time - song_time
            if ahead > self.cfg.approach_time:
                break
            if not ns.done:
                out.append((ns.note, ahead / self.cfg.approach_time))
        return out

    # -- bucle principal ----------------------------------------------------
    def update(self, song_time: float, hands: HandsFrame) -> list[GameEvent]:
        events: list[GameEvent] = []
        if self.state is MatchState.FINISHED:
            return events
        if song_time < 0:
            self.state = MatchState.COUNTDOWN
            return events
        self.state = MatchState.PLAYING

        self._track_hands(hands)
        self.frames_total += 1
        for hand in (Hand.LEFT, Hand.RIGHT):
            if not hands.get(hand).valid:
                self.frames_lost[hand] += 1

        window = self.cfg.ok_window
        for ns in self._notes[self._cursor:]:
            note = ns.note
            if note.time - song_time > window:
                break  # los siguientes aún están lejos
            if ns.done:
                continue
            error = song_time - note.time  # > 0: tarde
            if error > window:
                events.append(self._resolve(ns, Judgement.MISS, None, None, 0))
                continue
            if self._touching(note, note.hand, hands):
                events.append(self._hit(ns, error))
            elif not ns.wrong_reported and self._touching(note, note.hand.other, hands):
                ns.wrong_reported = True
                self.wrong_hand_count += 1
                self.combo = 0
                events.append(
                    GameEvent(note, Judgement.WRONG_HAND, error, self._speed[note.hand.other], 0, 0)
                )

        while self._cursor < len(self._notes) and self._notes[self._cursor].done:
            self._cursor += 1
        if song_time >= self.end_time:
            self.state = MatchState.FINISHED
        return events

    # -- internos -----------------------------------------------------------
    def _to_px(self, x: float, y: float) -> tuple[float, float]:
        w, h = self.cfg.window_size
        return x * w, y * h

    def _track_hands(self, hands: HandsFrame) -> None:
        """Velocidad de cada mano en px/s (suavizada). Ignora fotogramas repetidos."""
        if hands.timestamp == self._last_ts:
            return
        self._last_ts = hands.timestamp
        for hand in (Hand.LEFT, Hand.RIGHT):
            p = hands.get(hand)
            if not p.valid:
                self._prev[hand] = None
                self._speed[hand] = 0.0
                continue
            cur = self._to_px(p.x, p.y)
            prev = self._prev[hand]
            if prev is not None and hands.timestamp > prev[1]:
                inst = math.dist(cur, prev[0]) / (hands.timestamp - prev[1])
                self._speed[hand] = (
                    _SPEED_SMOOTHING * self._speed[hand] + (1 - _SPEED_SMOOTHING) * inst
                )
            self._prev[hand] = (cur, hands.timestamp)

    def _touching(self, note: ChartNote, hand: Hand, hands: HandsFrame) -> bool:
        p = hands.get(hand)
        if not p.valid:
            return False
        reach = self.cfg.block_radius + self.cfg.saber_radius
        if math.dist(self._to_px(p.x, p.y), self.cfg.cell_center(note.col, note.row)) > reach:
            return False
        return self._speed[hand] >= self.cfg.min_swing_speed

    def _hit(self, ns: _NoteState, error: float) -> GameEvent:
        cfg = self.cfg
        a = abs(error)
        if a <= cfg.perfect_window:
            judgement, base = Judgement.PERFECT, cfg.points_perfect
        elif a <= cfg.good_window:
            judgement, base = Judgement.GOOD, cfg.points_good
        else:
            judgement, base = Judgement.OK, cfg.points_ok
        multiplier = min(1 + self.combo // cfg.combo_step, cfg.max_multiplier)
        return self._resolve(
            ns, judgement, error, self._speed[ns.note.hand], base * multiplier
        )

    def _resolve(
        self,
        ns: _NoteState,
        judgement: Judgement,
        error: Optional[float],
        speed: Optional[float],
        score: int,
    ) -> GameEvent:
        ns.done = True
        if judgement is Judgement.MISS:
            self.combo = 0
        else:
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
        self.score += score
        event = GameEvent(ns.note, judgement, error, speed, score, self.combo)
        self.results.append(event)
        return event
