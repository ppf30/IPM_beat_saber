from dataclasses import replace

import pytest

from config import DEFAULT_CONFIG
from game import Game
from models import Chart, ChartNote, Hand, HandPosition, HandsFrame, Judgement, MatchState

CFG = DEFAULT_CONFIG
W, H = CFG.window_size


def px(x, y):
    return HandPosition(x / W, y / H, True)


def frame(ts, left=None, right=None):
    return HandsFrame(left or HandPosition(), right or HandPosition(), ts)


def make_chart(*notes):
    return Chart("t", 100, list(notes))


def sweep(game, hand, cell, t_hit, start=-0.04, end=0.04, step=0.02):
    """Pasa la mano rápidamente por el centro de la celda alrededor de ``t_hit``."""
    cx, cy = CFG.cell_center(*cell)
    events = []
    n = int(round((end - start) / step))
    for i in range(n + 1):
        dt = start + i * step
        x = cx + (dt / 0.1) * 80  # ~4000 px/s
        pos = px(x, cy)
        f = frame(t_hit + dt, **{hand.value: pos})
        events += game.update(t_hit + dt, f)
    return events


def test_perfect_hit_scores_and_combo():
    note = ChartNote(1.0, Hand.RIGHT, 1, 1)
    game = Game(make_chart(note))
    events = sweep(game, Hand.RIGHT, (1, 1), 1.0)
    hits = [e for e in events if e.judgement is Judgement.PERFECT]
    assert len(hits) == 1
    assert hits[0].score == CFG.points_perfect
    assert game.combo == 1 and game.hits == 1


def test_stationary_hand_does_not_hit():
    note = ChartNote(1.0, Hand.RIGHT, 1, 1)
    game = Game(make_chart(note))
    cx, cy = CFG.cell_center(1, 1)
    events = []
    t = 0.0
    while t < 2.0:
        events += game.update(t, frame(t, right=px(cx, cy)))
        t += 1 / 60
    assert [e.judgement for e in events] == [Judgement.MISS]
    assert game.combo == 0


def test_wrong_hand_penalises_but_note_can_still_be_hit():
    note = ChartNote(1.0, Hand.RIGHT, 1, 1)
    game = Game(make_chart(note))
    wrong = sweep(game, Hand.LEFT, (1, 1), 0.9, start=-0.05, end=0.05)
    assert any(e.judgement is Judgement.WRONG_HAND for e in wrong)
    assert game.wrong_hand_count == 1 and game.hits == 0
    right = sweep(game, Hand.RIGHT, (1, 1), 1.0)
    assert any(e.judgement is Judgement.PERFECT for e in right)


def test_early_and_late_judgements():
    notes = [ChartNote(1.0, Hand.RIGHT, 1, 1), ChartNote(3.0, Hand.LEFT, 2, 1)]
    game = Game(make_chart(*notes))
    # Golpe casi 0.2 s antes de tiempo -> OK; la comprobación se hace por el evento
    ev = sweep(game, Hand.RIGHT, (1, 1), 0.8, start=-0.02, end=0.02)
    assert ev and ev[0].judgement is Judgement.OK and ev[0].time_error < 0
    ev = sweep(game, Hand.LEFT, (2, 1), 3.1, start=-0.02, end=0.02)
    assert ev and ev[0].judgement is Judgement.GOOD and ev[0].time_error > 0


def test_multiplier_grows_with_combo():
    step = CFG.combo_step
    notes = [ChartNote(1.0 + i, Hand.RIGHT, i % 2 + 1, 1) for i in range(step + 1)]
    game = Game(make_chart(*notes))
    scores = []
    for i, n in enumerate(notes):
        ev = sweep(game, Hand.RIGHT, (n.col, n.row), n.time)
        scores += [e.score for e in ev if e.judgement is Judgement.PERFECT]
    assert scores[0] == CFG.points_perfect
    assert scores[-1] == CFG.points_perfect * 2  # combo >= 10 -> x2
    assert game.max_combo == step + 1


def test_miss_resets_combo_and_game_finishes():
    notes = [ChartNote(1.0, Hand.RIGHT, 1, 1), ChartNote(2.0, Hand.RIGHT, 2, 1)]
    game = Game(make_chart(*notes))
    sweep(game, Hand.RIGHT, (1, 1), 1.0)
    assert game.combo == 1
    t = 1.5
    while game.state is not MatchState.FINISHED and t < 10:
        game.update(t, frame(t))
        t += 0.05
    assert game.state is MatchState.FINISHED
    assert game.combo == 0 and game.max_combo == 1
    assert [r.judgement for r in game.results] == [Judgement.PERFECT, Judgement.MISS]
    assert game.accuracy == pytest.approx(0.5)


def test_countdown_does_nothing():
    game = Game(make_chart(ChartNote(1.0, Hand.RIGHT, 1, 1)))
    assert game.update(-1.0, frame(0.0)) == []
    assert game.state is MatchState.COUNTDOWN


def test_lost_tracking_is_counted():
    game = Game(make_chart(ChartNote(5.0, Hand.RIGHT, 1, 1)))
    for i in range(10):
        game.update(i * 0.02, frame(i * 0.02, right=px(500, 300)))
    assert game.frames_lost[Hand.LEFT] == 10
    assert game.frames_lost[Hand.RIGHT] == 0


def test_speed_requirement_can_be_disabled():
    cfg = replace(CFG, min_swing_speed=0.0)
    game = Game(make_chart(ChartNote(1.0, Hand.RIGHT, 1, 1)), cfg)
    cx, cy = cfg.cell_center(1, 1)
    ev = game.update(1.0, frame(1.0, right=px(cx, cy)))
    assert ev and ev[0].judgement is Judgement.PERFECT


def test_visible_notes_only_within_approach_time():
    game = Game(make_chart(ChartNote(5.0, Hand.RIGHT, 1, 1)))
    assert game.visible_notes(0.0) == []
    vis = game.visible_notes(5.0 - CFG.approach_time / 2)
    assert len(vis) == 1 and vis[0][1] == pytest.approx(0.5)
