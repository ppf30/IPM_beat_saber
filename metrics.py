"""Calculo y exportacion de estadisticas de la partida"""

from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Optional

from calibration import Calibration
from game import Game
from models import HIT_JUDGEMENTS, Hand, Judgement


@dataclass
class SessionSummary:
    """Resumen metrico de una sesion de juego

    Attributes:
        timestamp (str): Fecha y hora de registro de la partida
        player (str): Nombre o identificador del jugador
        level (str): Nivel de dificultad de la partida
        chart (str): Titulo del patron o cancion jugada
        total_notes (int): Numero total de bloques en la partida
        hits (int): Cantidad de bloques golpeados correctamente
        misses (int): Cantidad de bloques no golpeados a tiempo
        wrong_hand (int): Cantidad de golpes realizados con la mano incorrecta
        perfect (int): Cantidad de golpes con evaluacion perfecta
        good (int): Cantidad de golpes con evaluacion buena
        ok (int): Cantidad de golpes con evaluacion aceptable
        accuracy (float): Proporcion de aciertos respecto al total de bloques
        score (int): Puntuacion final obtenida
        max_combo (int): Mayor racha consecutiva de aciertos
        mean_error_ms (float): Error medio de tiempo en milisegundos con signo
        mean_abs_error_ms (float): Error absoluto medio de tiempo en milisegundos
        accuracy_left (float): Precision obtenida con la mano izquierda
        accuracy_right (float): Precision obtenida con la mano derecha
        tracking_loss_left (float): Fraccion de fotogramas sin deteccion de la mano izquierda
        tracking_loss_right (float): Fraccion de fotogramas sin deteccion de la mano derecha
        mean_hit_speed_px_s (float): Velocidad media de la mano al golpear en pixeles por segundo
        accuracy_drop_pp (float): Diferencia de precision en puntos porcentuales entre mitades
        speed_drop_pct (float): Variacion porcentual de velocidad entre primera y segunda mitad
        rom_x (float): Rango horizontal de movimiento en anchos de hombro
        rom_y (float): Rango vertical de movimiento en anchos de hombro
    """

    timestamp: str
    player: str
    level: str
    chart: str
    total_notes: int
    hits: int
    misses: int
    wrong_hand: int
    perfect: int
    good: int
    ok: int
    accuracy: float
    score: int
    max_combo: int
    mean_error_ms: float
    mean_abs_error_ms: float
    accuracy_left: float
    accuracy_right: float
    tracking_loss_left: float
    tracking_loss_right: float
    mean_hit_speed_px_s: float
    accuracy_drop_pp: float
    speed_drop_pct: float
    rom_x: float
    rom_y: float


def _half_stats(events) -> tuple[float, float]:
    """Calcula la precision y la velocidad media de golpe para un subconjunto de eventos

    Args:
        events (list[GameEvent]): Lista de eventos de partida a evaluar

    Returns:
        tuple[float, float]: Tupla con la precision y la velocidad media en px/s
    """
    if not events:
        return 0.0, 0.0
    hits = [e for e in events if e.judgement in HIT_JUDGEMENTS]
    speeds = [e.hand_speed for e in hits if e.hand_speed is not None]
    return len(hits) / len(events), (mean(speeds) if speeds else 0.0)


def summarize(
    game: Game,
    player: str = "",
    now: Optional[datetime] = None,
    level: str = "",
    calibration: Optional[Calibration] = None,
    camera_aspect: float = 0.75,) -> SessionSummary:
    """Genera el resumen estadistico de una partida finalizada

    Args:
        game (Game): Instancia de partida con resultados y metricas acumuladas
        player (str): Nombre del jugador para asociar al resumen
        now (Optional[datetime]): Marca temporal opcional para el registro
        level (str): Nivel de dificultad de la partida
        calibration (Optional[Calibration]): Calibracion de movimiento usada en la sesion
        camera_aspect (float): Relacion de aspecto usada para calcular el rango de movimiento

    Returns:
        SessionSummary: Estructura con los indicadores calculados de la sesion
    """
    results = game.results
    hit_events = [r for r in results if r.judgement in HIT_JUDGEMENTS]

    def count(j: Judgement) -> int:
        return sum(1 for r in results if r.judgement is j)

    errors_ms = [r.time_error * 1000.0 for r in hit_events if r.time_error is not None]
    per_hand = {h: [r for r in results if r.note.hand is h] for h in Hand}
    hits_hand = {
        h: sum(1 for r in per_hand[h] if r.judgement in HIT_JUDGEMENTS) for h in Hand
    }

    def ratio(a: float, b: float) -> float:
        return a / b if b else 0.0

    frames = game.frames_total
    half = len(results) // 2
    (acc1, spd1), (acc2, spd2) = _half_stats(results[:half]), _half_stats(results[half:])
    have_halves = half > 0 and len(results) - half > 0
    rom = calibration.range_of_motion(camera_aspect) if calibration else None
    all_speeds = [r.hand_speed for r in hit_events if r.hand_speed is not None]
    return SessionSummary(
        timestamp=(now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S"),
        player=player,
        level=level,
        chart=game.chart.title,
        total_notes=game.total_notes,
        hits=len(hit_events),
        misses=count(Judgement.MISS),
        wrong_hand=game.wrong_hand_count,
        perfect=count(Judgement.PERFECT),
        good=count(Judgement.GOOD),
        ok=count(Judgement.OK),
        accuracy=round(game.accuracy, 4),
        score=game.score,
        max_combo=game.max_combo,
        mean_error_ms=round(ratio(sum(errors_ms), len(errors_ms)), 1),
        mean_abs_error_ms=round(ratio(sum(abs(e) for e in errors_ms), len(errors_ms)), 1),
        accuracy_left=round(ratio(hits_hand[Hand.LEFT], len(per_hand[Hand.LEFT])), 4),
        accuracy_right=round(ratio(hits_hand[Hand.RIGHT], len(per_hand[Hand.RIGHT])), 4),
        tracking_loss_left=round(ratio(game.frames_lost[Hand.LEFT], frames), 4),
        tracking_loss_right=round(ratio(game.frames_lost[Hand.RIGHT], frames), 4),
        mean_hit_speed_px_s=round(mean(all_speeds), 1) if all_speeds else 0.0,
        accuracy_drop_pp=round((acc1 - acc2) * 100, 1) if have_halves else 0.0,
        speed_drop_pct=round((spd1 - spd2) / spd1 * 100, 1) if have_halves and spd1 > 0 and spd2 > 0 else 0.0,
        rom_x=round(rom[0], 2) if rom else 0.0,
        rom_y=round(rom[1], 2) if rom else 0.0,
    )


def export_session(game: Game, summary: SessionSummary, results_dir: Path) -> tuple[Path, Path]:
    """Exporta el detalle de bloques a un archivo CSV y agrega el resumen a summary csv

    Args:
        game (Game): Partida con los resultados detallados por bloque
        summary (SessionSummary): Resumen estadistico de la sesion
        results_dir (Path): Directorio destino donde se guardan los archivos CSV

    Returns:
        tuple[Path, Path]: Rutas generadas para el CSV de bloques y el CSV de resumen
    """
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = re.sub(r"[^0-9]", "", summary.timestamp)
    who = re.sub(r"[^A-Za-z0-9_-]", "", summary.player) or "anonimo"

    notes_path = results_dir / f"{stamp}_{who}_notes.csv"
    with notes_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["note_time_s", "hand", "col", "row", "judgement", "time_error_ms", "hand_speed_px_s", "score"]
        )
        for r in game.results:
            writer.writerow([
                round(r.note.time, 3), r.note.hand.value, r.note.col, r.note.row,
                r.judgement.value,
                "" if r.time_error is None else round(r.time_error * 1000.0, 1),
                "" if r.hand_speed is None else round(r.hand_speed, 1),
                r.score,
            ])

    summary_path = results_dir / "summary.csv"
    is_new = not summary_path.exists()
    with summary_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[fld.name for fld in fields(SessionSummary)])
        if is_new:
            writer.writeheader()
        writer.writerow(asdict(summary))
    return notes_path, summary_path

