"""Prueba de humo: la aplicación completa arranca y juega una partida corta sin pantalla."""
import os
from dataclasses import replace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

import main as app_main  # noqa: E402
from config import DEFAULT_CONFIG  # noqa: E402
from models import Chart, ChartNote, Hand  # noqa: E402


def test_full_session_with_simulated_tracker(tmp_path):
    cfg = replace(DEFAULT_CONFIG, countdown=0.1, end_padding=0.4, results_dir=tmp_path / "res")
    app = app_main.App(app_main.parse_args(["--tracker", "sim", "--player", "ci"]), cfg)
    app.chart = Chart("mini", 120, [ChartNote(0.3, Hand.RIGHT, 2, 1), ChartNote(0.6, Hand.LEFT, 1, 1)])
    try:
        app.step()
        assert app.mode == app_main.MENU
        app.handle_key(pygame.K_RETURN)
        for _ in range(600):
            app.step()
            app.clock.tick(120)
            if app.mode == app_main.RESULTS:
                break
        assert app.mode == app_main.RESULTS
        app.step()  # dibuja resultados
        assert app.summary.total_notes == 2
        assert (tmp_path / "res" / "summary.csv").exists()
    finally:
        pygame.quit()


def test_missing_model_gives_clear_error(tmp_path, capsys):
    from tracking import WebcamTracker
    cfg = replace(DEFAULT_CONFIG, pose_model_path=tmp_path / "no_existe.task")
    try:
        WebcamTracker(cfg).start()
    except FileNotFoundError as exc:
        assert "setup" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("debía fallar sin modelo")
