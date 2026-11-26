"""Inicio y conexión entre los módulos.

Uso::

    python main.py                       # webcam + chart de demostración
    python main.py --tracker mouse       # sin cámara: ratón (Ctrl = mano izquierda)
    python main.py --tracker sim         # manos simuladas (demo/pruebas)
    python main.py --level suave --player Ana
    python main.py --chart assets/charts/otro.json
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

from calibration import Calibration, Calibrator, HandSmoother  # noqa: E402
from config import DEFAULT_CONFIG, DEFAULT_LEVEL, LEVELS, Config, level_config  # noqa: E402
from game import Game  # noqa: E402
from metrics import SessionSummary, export_session, summarize  # noqa: E402
from models import HandsFrame, MatchState  # noqa: E402
from rendering import Renderer  # noqa: E402
from rhythm import Conductor, chart_for_level, load_chart  # noqa: E402
from tracking import HandTracker, MouseTracker, SimulatedTracker, WebcamTracker  # noqa: E402

MENU, CALIBRATION, PLAY, RESULTS = "menu", "calibration", "play", "results"


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Beat Saber IPM: juego serio con webcam")
    p.add_argument("--tracker", choices=["webcam", "mouse", "sim"], default="webcam")
    p.add_argument("--camera", type=int, default=None, help="índice de la cámara")
    p.add_argument("--level", choices=list(LEVELS), default=DEFAULT_LEVEL, help="nivel de dificultad")
    p.add_argument("--chart", type=Path, default=None, help="chart JSON propio (si no, el del nivel)")
    p.add_argument("--player", default="", help="identificador del jugador para las estadísticas")
    p.add_argument("--fullscreen", action="store_true")
    # Opciones para pruebas automáticas / capturas
    p.add_argument("--autostart", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--frames", type=int, default=None, help=argparse.SUPPRESS)
    p.add_argument("--screenshot", type=Path, default=None, help=argparse.SUPPRESS)
    return p.parse_args(argv)


class App:
    def __init__(self, args: argparse.Namespace, cfg: Config = DEFAULT_CONFIG):
        if args.camera is not None:
            cfg = replace(cfg, camera_index=args.camera)
        self.args, self.cfg = args, cfg
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        flags = pygame.FULLSCREEN | pygame.SCALED if args.fullscreen else 0
        self.screen = pygame.display.set_mode(cfg.window_size, flags)
        pygame.display.set_caption("Beat Saber IPM")
        self.renderer = Renderer(self.screen, cfg)
        self.clock = pygame.time.Clock()
        self.tracker = self._build_tracker(args.tracker)
        self.level = args.level
        self.custom_chart = args.chart is not None
        self.chart = load_chart(args.chart) if self.custom_chart else chart_for_level(self.level, cfg)
        self.play_cfg = level_config(cfg, self.level)

        if self.tracker.uses_camera:
            saved = Calibration.load(cfg.calibration_path)
            self.calibrated = saved is not None
            self.calibration = saved or Calibration.default(cfg)
        else:
            self.calibrated, self.calibration = True, Calibration.identity()
        self.smoother = HandSmoother(cfg)

        self.mode = MENU
        self.message = ""
        self.calibrator = Calibrator(cfg)
        self.cal_phase = "ready"
        self.game: Game | None = None
        self.conductor: Conductor | None = None
        self.paused = False
        self.summary: SessionSummary | None = None
        self.saved_to = ""
        self.running = True

    def _build_tracker(self, kind: str) -> HandTracker:
        if kind == "webcam":
            return WebcamTracker(self.cfg)
        return MouseTracker() if kind == "mouse" else SimulatedTracker()

    # ------------------------------------------------------------ transiciones
    def set_level(self, level: str) -> None:
        self.level = level
        if not self.custom_chart:
            self.chart = chart_for_level(level, self.cfg)

    def start_game(self) -> None:
        self.play_cfg = level_config(self.cfg, self.level)
        self.renderer.cfg = self.play_cfg  # el dibujo debe usar los mismos tamaños que las colisiones
        self.game = Game(self.chart, self.play_cfg)
        self.conductor = Conductor(self.chart, self.play_cfg)
        self.conductor.start()
        self.smoother = HandSmoother(self.cfg)
        self.renderer.reset_effects()
        self.paused = False
        self.mode = PLAY

    def finish_game(self) -> None:
        self.conductor.stop()
        self.summary = summarize(
            self.game,
            self.args.player,
            level=self.level,
            calibration=self.calibration if self.tracker.uses_camera else None,
            camera_aspect=self.cfg.camera_size[1] / self.cfg.camera_size[0],
        )
        try:
            notes_csv, _ = export_session(self.game, self.summary, self.cfg.results_dir)
            self.saved_to = str(notes_csv.parent.name + "/" + notes_csv.name)
        except OSError as exc:
            self.saved_to = f"(no se pudo guardar: {exc})"
        self.mode = RESULTS

    def abort_game(self) -> None:
        if self.conductor:
            self.conductor.stop()
        self.mode = MENU

    def start_calibration(self) -> None:
        self.mode = CALIBRATION
        self.cal_phase = "ready"
        self.calibrator = Calibrator(self.cfg)

    # ------------------------------------------------------------------ eventos
    def handle_key(self, key: int) -> None:
        if self.mode == MENU:
            if key == pygame.K_RETURN:
                self.message = ""
                self.start_game()
            elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
                self.set_level(list(LEVELS)[key - pygame.K_1])
            elif key == pygame.K_c and self.tracker.uses_camera:
                self.start_calibration()
            elif key == pygame.K_ESCAPE:
                self.running = False
        elif self.mode == CALIBRATION:
            if key == pygame.K_ESCAPE:
                self.mode = MENU
            elif key == pygame.K_SPACE and self.cal_phase == "ready":
                self.cal_phase = "capturing"
                self.calibrator.start(time.monotonic())
        elif self.mode == PLAY:
            if key == pygame.K_p:
                self.paused = not self.paused
                (self.conductor.pause if self.paused else self.conductor.resume)()
            elif key == pygame.K_ESCAPE:
                if self.paused:
                    self.abort_game()
                else:
                    self.paused = True
                    self.conductor.pause()
        elif self.mode == RESULTS:
            if key == pygame.K_RETURN or key == pygame.K_ESCAPE:
                self.mode = MENU
            elif key == pygame.K_r:
                self.start_game()

    # ---------------------------------------------------------------- por frame
    def step(self) -> None:
        now = time.monotonic()
        raw = self.tracker.read()
        preview = self.tracker.preview()

        if self.mode == MENU:
            self.renderer.draw_menu(
                self.chart.title, self.tracker.name, self.calibrated, self.message, self.level
            )

        elif self.mode == CALIBRATION:
            if self.cal_phase == "capturing":
                self.calibrator.add(raw)
                if self.calibrator.finished(now):
                    result = self.calibrator.result()
                    if result is None:
                        self.cal_phase = "ready"
                        self.message = "No se detectaron suficientes datos. Inténtalo de nuevo."
                    else:
                        self.calibration, self.calibrated = result, True
                        result.save(self.cfg.calibration_path)
                        self.message = "Calibración guardada."
                        self.mode = MENU
                    if self.mode == CALIBRATION:
                        self.start_calibration()
                        self.cal_phase = "ready"
            if self.mode == CALIBRATION:
                self.renderer.draw_calibration(
                    self.cal_phase, self.calibrator.progress(now), raw,
                    self.calibrator.current_zone(), preview, self.calibrator.n_samples,
                )

        elif self.mode == PLAY:
            hands = self.smoother.apply(self.calibration.apply(raw))
            if self.paused:
                song_time = self.conductor.song_time()
            else:
                song_time = self.conductor.update()
                self.renderer.add_events(self.game.update(song_time, hands), now)
            self.renderer.draw_game(self.game, song_time, hands, preview, now, self.paused)
            if self.game.state is MatchState.FINISHED:
                self.finish_game()

        elif self.mode == RESULTS:
            self.renderer.draw_results(self.summary, self.saved_to)

        pygame.display.flip()

    def run(self) -> None:
        self.tracker.start()
        frames = 0
        try:
            if self.args.autostart:
                self.start_game()
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        self.handle_key(event.key)
                self.step()
                self.clock.tick(self.cfg.fps)
                frames += 1
                if self.args.frames is not None and frames >= self.args.frames:
                    break
            if self.args.screenshot:
                pygame.image.save(self.screen, str(self.args.screenshot))
        finally:
            self.tracker.stop()
            pygame.quit()


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        App(args).run()
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
