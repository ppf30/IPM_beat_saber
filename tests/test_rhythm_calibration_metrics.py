import csv

import pytest

from calibration import Calibration, Calibrator, HandSmoother, MovementZone
from config import DEFAULT_CONFIG, Config
from game import Game
from metrics import export_session, summarize
from models import Hand, HandPosition, HandsFrame, Judgement
from rhythm import SongClock, chart_for_level, generate_demo_chart, load_chart


# ---------------------------------------------------------------- rhythm
def test_demo_chart_is_valid_and_sorted():
    chart = generate_demo_chart()
    cfg = DEFAULT_CONFIG
    assert len(chart.notes) > 30
    assert [n.time for n in chart.notes] == sorted(n.time for n in chart.notes)
    for n in chart.notes:
        assert 0 <= n.col < cfg.grid_cols and 0 <= n.row < cfg.grid_rows
    # nunca dos bloques simultáneos en la misma celda
    seen = set()
    for n in chart.notes:
        key = (round(n.time, 3), n.col, n.row)
        assert key not in seen
        seen.add(key)


def test_load_chart_from_json(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(
        '{"title": "T", "bpm": 60, "notes": ['
        '{"beat": 3, "hand": "right", "col": 3, "row": 2},'
        '{"beat": 2, "hand": "left", "col": 0, "row": 0}]}',
        encoding="utf-8",
    )
    chart = load_chart(path)
    assert chart.title == "T" and chart.bpm == 60
    assert [(n.time, n.hand) for n in chart.notes] == [(2.0, Hand.LEFT), (3.0, Hand.RIGHT)]


def test_load_chart_rejects_bad_files(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"title": "sin notas"}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_chart(path)


def test_example_chart_in_repo_is_valid():
    chart = load_chart(DEFAULT_CONFIG.pose_model_path.parent.parent / "assets" / "charts" / "ejemplo.json")
    cfg = DEFAULT_CONFIG
    assert len(chart.notes) > 0
    assert all(0 <= n.col < cfg.grid_cols and 0 <= n.row < cfg.grid_rows for n in chart.notes)


def test_song_clock_countdown_and_pause():
    now = [100.0]
    clock = SongClock(3.0, clock=lambda: now[0])
    clock.start()
    assert clock.song_time() == pytest.approx(-3.0)
    now[0] += 5.0
    assert clock.song_time() == pytest.approx(2.0)
    clock.pause()
    now[0] += 5.0
    assert clock.song_time() == pytest.approx(2.0) and clock.paused
    clock.resume()
    now[0] += 1.0
    assert clock.song_time() == pytest.approx(3.0) and not clock.paused


# ----------------------------------------------------------- calibration
def frame(ts, lx=None, rx=None, y=0.5):
    left = HandPosition(lx, y, True) if lx is not None else HandPosition()
    right = HandPosition(rx, y, True) if rx is not None else HandPosition()
    return HandsFrame(left, right, ts)


def test_zone_maps_edges_and_clamps():
    zone = MovementZone(0.2, 0.2, 0.8, 0.8)
    assert zone.to_screen(0.2, 0.2) == (0.0, 0.0)
    assert zone.to_screen(0.8, 0.8) == (1.0, 1.0)
    assert zone.to_screen(0.5, 0.5) == pytest.approx((0.5, 0.5))
    assert zone.to_screen(0.0, 1.0) == (0.0, 1.0)


def test_calibrator_builds_zone_from_samples():
    cal = Calibrator(Config(calibration_min_samples=10))
    cal.start(0.0)
    assert cal.current_zone() is None
    for i in range(100):
        v = i / 99
        cal.add(frame(i * 0.03, lx=0.2 + 0.2 * v, rx=0.6 + 0.2 * v, y=0.3 + 0.4 * v))
    zone = cal.result().zone
    assert 0.2 <= zone.x_min < 0.25 and 0.75 < zone.x_max <= 0.8
    assert 0.3 <= zone.y_min < 0.35 and 0.65 < zone.y_max <= 0.7
    assert cal.finished(DEFAULT_CONFIG.calibration_duration + 0.1)


def test_calibration_save_and_load(tmp_path):
    path = tmp_path / "cal.json"
    Calibration(MovementZone(0.1, 0.2, 0.9, 0.8)).save(path)
    loaded = Calibration.load(path)
    assert loaded.zone == MovementZone(0.1, 0.2, 0.9, 0.8)
    assert Calibration.load(tmp_path / "missing.json") is None


def test_smoother_holds_short_gaps_only():
    sm = HandSmoother(Config(smoothing_alpha=1.0, max_tracking_gap=0.15))
    assert sm.apply(frame(0.0, lx=0.3)).left.valid
    assert sm.apply(frame(0.10)).left.valid        # hueco corto: se mantiene
    assert not sm.apply(frame(0.30)).left.valid    # hueco largo: se pierde
    assert not sm.apply(frame(0.31)).right.valid


def test_smoother_reuses_output_for_repeated_frames():
    sm = HandSmoother(Config(smoothing_alpha=0.5))
    f = frame(1.0, lx=0.4)
    assert sm.apply(f) is sm.apply(f)


# --------------------------------------------------------------- metrics
def test_summary_and_export(tmp_path):
    from models import Chart, ChartNote
    chart = Chart("t", 100, [ChartNote(1.0, Hand.RIGHT, 1, 1), ChartNote(2.0, Hand.LEFT, 1, 1)])
    game = Game(chart)
    game._resolve(game._notes[0], Judgement.PERFECT, 0.05, 900.0, 100)
    game._resolve(game._notes[1], Judgement.MISS, None, None, 0)
    game.frames_total, game.frames_lost[Hand.LEFT] = 10, 5
    s = summarize(game, "Ana")
    assert (s.hits, s.misses, s.accuracy) == (1, 1, 0.5)
    assert s.mean_error_ms == 50.0 and s.accuracy_right == 1.0 and s.accuracy_left == 0.0
    assert s.tracking_loss_left == 0.5

    notes_csv, summary_csv = export_session(game, s, tmp_path)
    export_session(game, s, tmp_path)  # segunda partida: añade fila, no repite cabecera
    rows = list(csv.DictReader(summary_csv.open(encoding="utf-8")))
    assert len(rows) == 2 and rows[0]["player"] == "Ana"
    assert len(list(csv.DictReader(notes_csv.open(encoding="utf-8")))) == 2


# ------------------------------------------------- niveles y datos de salud
def test_levels_change_playability_and_have_charts():
    from config import LEVELS, level_config
    easy, normal, hard = (level_config(DEFAULT_CONFIG, n) for n in ("suave", "normal", "intenso"))
    assert easy.ok_window > normal.ok_window > hard.ok_window
    assert easy.approach_time > normal.approach_time > hard.approach_time
    assert easy.min_swing_speed < normal.min_swing_speed < hard.min_swing_speed
    for name in LEVELS:
        assert len(chart_for_level(name).notes) > 20
    assert chart_for_level("suave").bpm < chart_for_level("intenso").bpm


def test_range_of_motion_in_shoulder_widths(tmp_path):
    cal = Calibration(MovementZone(0.2, 0.2, 0.8, 0.8), shoulder_width=0.2)
    rx, ry = cal.range_of_motion(aspect=0.75)
    assert rx == pytest.approx(3.0) and ry == pytest.approx(2.25)
    assert Calibration(MovementZone(0, 0, 1, 1)).range_of_motion() is None
    cal.save(tmp_path / "c.json")
    assert Calibration.load(tmp_path / "c.json").shoulder_width == pytest.approx(0.2)


def test_calibrator_estimates_shoulder_width():
    cal = Calibrator(Config(calibration_min_samples=5))
    cal.start(0.0)
    for i in range(20):
        f = frame(i * 0.03, lx=0.3 + i * 0.01, rx=0.6)
        cal.add(HandsFrame(f.left, f.right, f.timestamp, shoulder_width=0.25))
    assert cal.result().shoulder_width == pytest.approx(0.25)


def test_fatigue_and_speed_metrics():
    from models import Chart, ChartNote
    notes = [ChartNote(float(i), Hand.RIGHT, 1, 1) for i in range(1, 9)]
    game = Game(Chart("t", 100, notes))
    # 1ª mitad: 4 aciertos rápidos; 2ª mitad: 2 aciertos lentos y 2 fallos
    for n in game._notes[:4]:
        game._resolve(n, Judgement.PERFECT, 0.0, 1000.0, 100)
    for n in game._notes[4:6]:
        game._resolve(n, Judgement.GOOD, 0.0, 500.0, 70)
    for n in game._notes[6:]:
        game._resolve(n, Judgement.MISS, None, None, 0)
    s = summarize(game, "Ana", level="suave",
                  calibration=Calibration(MovementZone(0.2, 0.2, 0.8, 0.8), 0.2))
    assert s.level == "suave"
    assert s.accuracy_drop_pp == pytest.approx(50.0)   # 100% -> 50%
    assert s.speed_drop_pct == pytest.approx(50.0)     # 1000 -> 500 px/s
    assert s.mean_hit_speed_px_s == pytest.approx(833.3, abs=0.1)
    assert s.rom_x == pytest.approx(3.0)
