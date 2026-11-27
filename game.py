"""Reglas, colisiones, puntuacion y estados de partida"""

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
    """Almacena el estado de resolucion de un bloque durante la partida

    Attributes:
        note (ChartNote): Bloque objetivo asociado
        done (bool): Indica si el bloque ya fue resuelto
        wrong_reported (bool): Indica si ya se registro un golpe con otra mano
    """

    __slots__ = ("note", "done", "wrong_reported")

    def __init__(self, note: ChartNote):
        """Inicializa el estado de seguimiento para un bloque

        Args:
            note (ChartNote): Bloque de la partida
        """
        self.note = note
        self.done = False
        self.wrong_reported = False


class Game:
    """Gestiona la logica de juego, colisiones, puntuacion y metricas de frames

    Attributes:
        chart (Chart): Patron de bloques de la partida
        cfg (Config): Parametros de jugabilidad y ventanas de tiempo
        state (MatchState): Estado actual de la partida
        score (int): Puntuacion acumulada
        combo (int): Racha actual de golpes validos
        max_combo (int): Racha maxima alcanzada en la partida
        wrong_hand_count (int): Numero de veces que se toco con la mano incorrecta
        results (list[GameEvent]): Eventos finales registrados para cada bloque
        frames_total (int): Total de fotogramas procesados durante la partida
        frames_lost (dict[Hand, int]): Cantidad de fotogramas sin deteccion por mano
        end_time (float): Instante en segundos en que finaliza la partida
        total_notes (int): Cantidad total de bloques del chart
        hits (int): Cantidad de bloques golpeados con exito
        accuracy (float): Proporcion de aciertos respecto al total de bloques
    """

    def __init__(self, chart: Chart, config: Config = DEFAULT_CONFIG):
        """Inicializa una partida nueva a partir de un chart y una configuracion

        Args:
            chart (Chart): Patron de bloques a jugar
            config (Config): Configuracion de colisiones, puntuacion y tiempos
        """
        self.chart = chart
        self.cfg = config
        self._notes = [_NoteState(n) for n in sorted(chart.notes, key=lambda n: n.time)]
        self._cursor = 0
        self.state = MatchState.COUNTDOWN
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.wrong_hand_count = 0
        self.results: list[GameEvent] = []
        self.frames_total = 0
        self.frames_lost = {Hand.LEFT: 0, Hand.RIGHT: 0}
        self.end_time = chart.duration + config.end_padding
        self._speed = {Hand.LEFT: 0.0, Hand.RIGHT: 0.0}
        self._prev: dict[Hand, Optional[tuple[tuple[float, float], float]]] = {
            Hand.LEFT: None, Hand.RIGHT: None
        }
        self._last_ts: Optional[float] = None

    @property
    def total_notes(self) -> int:
        """Devuelve el numero total de bloques en la partida

        Returns:
            int: Cantidad de bloques del chart
        """
        return len(self._notes)

    @property
    def hits(self) -> int:
        """Devuelve la cantidad de bloques golpeados con evaluacion valida

        Returns:
            int: Total de aciertos registrados
        """
        return sum(1 for r in self.results if r.judgement in HIT_JUDGEMENTS)

    @property
    def accuracy(self) -> float:
        """Calcula la precision actual como aciertos entre bloques totales

        Returns:
            float: Proporcion de aciertos entre 0 y 1
        """
        return self.hits / self.total_notes if self.total_notes else 0.0

    def progress(self, song_time: float) -> float:
        """Calcula el avance normalizado de la partida en el tiempo indicado

        Args:
            song_time (float): Tiempo actual de la partida en segundos

        Returns:
            float: Progreso acotado entre 0 y 1
        """
        return min(max(song_time / self.end_time, 0.0), 1.0) if self.end_time > 0 else 1.0

    def visible_notes(self, song_time: float) -> list[tuple[ChartNote, float]]:
        """Devuelve los bloques visibles y su progreso de aproximacion

        Args:
            song_time (float): Tiempo actual de la partida en segundos

        Returns:
            list[tuple[ChartNote, float]]: Tuplas de bloque y progreso restante normalizado
        """
        out = []
        for ns in self._notes[self._cursor:]:
            ahead = ns.note.time - song_time
            if ahead > self.cfg.approach_time:
                break
            if not ns.done:
                out.append((ns.note, ahead / self.cfg.approach_time))
        return out

    def update(self, song_time: float, hands: HandsFrame) -> list[GameEvent]:
        """Avanza el estado de la partida y evalua colisiones y fallos

        Args:
            song_time (float): Tiempo actual de la cancion en segundos
            hands (HandsFrame): Posiciones calibradas de ambas manos

        Returns:
            list[GameEvent]: Eventos generados en este fotograma
        """
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
                break
            if ns.done:
                continue
            error = song_time - note.time
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

    def _to_px(self, x: float, y: float) -> tuple[float, float]:
        """Convierte coordenadas normalizadas a pixeles segun el tamanyo de ventana

        Args:
            x (float): Coordenada horizontal normalizada
            y (float): Coordenada vertical normalizada

        Returns:
            tuple[float, float]: Posicion en pixeles
        """
        w, h = self.cfg.window_size
        return x * w, y * h

    def _track_hands(self, hands: HandsFrame) -> None:
        """Actualiza la velocidad suavizada de cada mano en pixeles por segundo

        Args:
            hands (HandsFrame): Frame actual con posicion y marca temporal
        """
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
        """Comprueba si una mano alcanza el bloque con velocidad suficiente

        Args:
            note (ChartNote): Bloque objetivo a comprobar
            hand (Hand): Mano evaluada
            hands (HandsFrame): Posiciones actuales de las manos
        """
        p = hands.get(hand)
        if not p.valid:
            return False
        reach = self.cfg.block_radius + self.cfg.saber_radius
        if math.dist(self._to_px(p.x, p.y), self.cfg.cell_center(note.col, note.row)) > reach:
            return False
        return self._speed[hand] >= self.cfg.min_swing_speed

    def _hit(self, ns: _NoteState, error: float) -> GameEvent:
        """Clasifica un golpe segun su precision temporal y lo puntua

        Args:
            ns (_NoteState): Estado del bloque golpeado
            error (float): Diferencia en segundos entre el golpe y el instante ideal (> 0 es tarde)

        Returns:
            GameEvent: Evento con el resultado del acierto y los puntos obtenidos
        """
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
        """Cierra un bloque, actualiza puntuacion y racha y registra el resultado

        Args:
            ns (_NoteState): Estado del bloque que se resuelve
            judgement (Judgement): Resultado asignado al bloque
            error (Optional[float]): Error temporal en segundos, o None si fue un fallo
            speed (Optional[float]): Velocidad de la mano al golpear en px/s, o None si fue un fallo
            score (int): Puntos obtenidos por el bloque

        Returns:
            GameEvent: Evento creado y almacenado en los resultados
        """
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