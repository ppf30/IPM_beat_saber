"""Cálculo y exportación de estadísticas.

Cada partida genera:

* ``results/<fecha>_<jugador>_notes.csv``: una fila por bloque (para analizar
  tiempos de reacción, manos, etc.).
* Una fila nueva en ``results/summary.csv``: resumen de la partida, pensado
  para seguir la evolución de cada jugador entre sesiones.

Indicadores funcionales (orientativos, **no son un diagnóstico**): precisión
temporal, velocidad del golpe, amplitud de movimiento (en anchos de hombro),
simetría entre brazos y caída de rendimiento entre la primera y la segunda
mitad de la sesión (fatiga).
"""
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
    accuracy: float            # aciertos / bloques totales
    score: int
    max_combo: int
    mean_error_ms: float       # sesgo: > 0 = golpea tarde de media
    mean_abs_error_ms: float   # precisión temporal
    accuracy_left: float
    accuracy_right: float
    tracking_loss_left: float  # fracción de fotogramas sin detectar la mano
    tracking_loss_right: float
    mean_hit_speed_px_s: float  # velocidad media de la mano al golpear (px/s de pantalla)
    accuracy_drop_pp: float     # fatiga: puntos de precisión perdidos de la 1ª a la 2ª mitad
    speed_drop_pct: float       # fatiga: % de velocidad perdida de la 1ª a la 2ª mitad
    rom_x: float                # amplitud horizontal alcanzada (anchos de hombro); 0 = no disponible
    rom_y: float                # amplitud vertical alcanzada (anchos de hombro); 0 = no disponible


def _half_stats(events) -> tuple[float, float]:
    """(precisión, velocidad media de golpe) de una lista de resultados."""
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
    camera_aspect: float = 0.75,
) -> SessionSummary:
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


def export_session(
    game: Game, summary: SessionSummary, results_dir: Path
) -> tuple[Path, Path]:
    """Escribe el CSV de bloques y añade el resumen a ``summary.csv``."""
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
