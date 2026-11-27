"""Prueba de humo: la aplicación completa arranca y juega una partida corta sin pantalla ni sonido."""
import math
import os
import time
from dataclasses import replace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import main as app_main  # noqa: E402
from config import DEFAULT_CONFIG  # noqa: E402
from models import Chart, ChartNote, Hand, HandPosition, HandsFrame  # noqa: E402
from tracking import HandTracker, WebcamTracker  # noqa: E402


class FakeTracker(HandTracker):
    """Manos que se mueven solas, para probar sin cámara."""

    name = "fake"

    def read(self):
        t = time.monotonic()
        return HandsFrame(
            HandPosition(0.35 + 0.15 * math.sin(1.7 * t), 0.5, True),
            HandPosition(0.65 + 0.15 * math.sin(1.9 * t), 0.5, True),
            t,
        )


def test_full_session_without_sound(tmp_path):
    cfg = replace(DEFAULT_CONFIG, results_dir=tmp_path / "res")
    app = app_main.App(app_main.parse_args(["--tracker", "mouse", "--player", "ci"]), cfg)
    app.tracker = FakeTracker()
    app.chart = Chart("mini", 120, [ChartNote(0.3, Hand.RIGHT, 2, 1), ChartNote(0.6, Hand.LEFT, 1, 1)])
    try:
        assert pygame.mixer.get_init() is None  # el mezclador de audio no se ha iniciado
        app.step()
        assert app.mode == app_main.MENU
        app.handle_key(pygame.K_RETURN)
        app.song_clock._countdown = 0.1  # cuenta atrás corta para la prueba
        for _ in range(600):
            app.step()
            app.clock.tick(120)
            if app.mode == app_main.RESULTS:
                break
        assert app.mode == app_main.RESULTS
        app.step()  # dibuja resultados
        assert app.summary.total_notes == 2
        assert (tmp_path / "res" / "summary.csv").exists()
        assert pygame.mixer.get_init() is None
    finally:
        pygame.quit()


def test_menu_levels_change_with_keys():
    app = app_main.App(app_main.parse_args(["--tracker", "mouse"]), DEFAULT_CONFIG)
    try:
        app.handle_key(pygame.K_1)
        assert app.level == "suave" and app.chart.title == "Demo suave"
        app.handle_key(pygame.K_3)
        assert app.level == "intenso"
    finally:
        pygame.quit()


def test_missing_model_gives_clear_error(tmp_path):
    cfg = replace(DEFAULT_CONFIG, pose_model_path=tmp_path / "no_existe.task")
    try:
        WebcamTracker(cfg).start()
    except FileNotFoundError as exc:
        assert "download_models" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("debía fallar sin modelo")
