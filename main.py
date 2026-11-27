"""Punto de entrada principal de la aplicacion"""

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
from metrics import export_session, summarize  # noqa: E402
from models import MatchState  # noqa: E402
from rendering import Renderer  # noqa: E402
from rhythm import SongClock, chart_for_level, load_chart  # noqa: E402
from tracking import HandTracker, MouseTracker, WebcamTracker  # noqa: E402

MENU, CALIBRATION, PLAY, RESULTS = "menu", "calibration", "play", "results"


def parse_args(argv=None) -> argparse.Namespace:
    """Analiza los argumentos de linea de comandos para configurar la ejecucion

    Args:
        argv: Lista opcional de argumentos a procesar

    Returns:
        argparse.Namespace: Argumentos parseados con sus valores por defecto
    """
    p = argparse.ArgumentParser(description="Beat Saber IPM: juego serio con webcam")
    p.add_argument("--tracker", choices=["webcam", "mouse"], default="webcam")
    p.add_argument("--camera", type=int, default=None, help="índice de la cámara")
    p.add_argument("--level", choices=list(LEVELS), default=DEFAULT_LEVEL, help="nivel de dificultad")
    p.add_argument("--chart", type=Path, default=None, help="patrón JSON propio (si no, el del nivel)")
    p.add_argument("--player", default="", help="identificador del jugador para las estadísticas")
    p.add_argument("--fullscreen", action="store_true")
    return p.parse_args(argv)


class App:
    """Coordina el ciclo de vida, pantallas, entrada y partida del juego

    Attributes:
        cfg (Config): Configuracion base de la aplicacion
        player (str): Nombre del jugador actual
        screen (pygame.Surface): Ventana principal de Pygame
        renderer (Renderer): Renderizador encargado del dibujo
        clock (pygame.time.Clock): Reloj de cuadros por segundo
        tracker (HandTracker): Sistema de seguimiento de manos activo
        level (str): Nivel de dificultad seleccionado
        custom_chart (Optional[Chart]): Patron cargado desde archivo si existe
        chart (Chart): Patron activo para la partida
        calibrated (bool): Indica si hay calibracion disponible
        calibration (Calibration): Transformacion de calibracion activa
        smoother (HandSmoother): Suavizador temporal de posiciones de manos
        calibrator (Calibrator): Gestor del proceso de calibracion
        cal_phase (str): Fase actual de la calibracion
        mode (str): Pantalla o modo actual de la aplicacion
        message (str): Mensaje informativo mostrado en el menu
        game (Optional[Game]): Instancia de la partida en curso
        song_clock (Optional[SongClock]): Reloj temporal de la partida
        summary: Resumen estadistico de la ultima sesion
        saved_to (str): Ruta donde se guardaron los resultados
        running (bool): Indica si el bucle principal sigue activo
    """

    def __init__(self, args: argparse.Namespace, cfg: Config = DEFAULT_CONFIG):
        """Inicializa la ventana, el tracker, la calibracion y el estado inicial

        Args:
            args (argparse.Namespace): Argumentos de ejecucion parseados
            cfg (Config): Configuracion general del juego
        """
        if args.camera is not None:
            cfg = replace(cfg, camera_index=args.camera)
        self.cfg = cfg
        self.player = args.player
        pygame.display.init()
        pygame.font.init()
        flags = pygame.FULLSCREEN | pygame.SCALED if args.fullscreen else 0
        self.screen = pygame.display.set_mode(cfg.window_size, flags)
        pygame.display.set_caption("Beat Saber IPM")
        self.renderer = Renderer(self.screen, cfg)
        self.clock = pygame.time.Clock()

        self.tracker: HandTracker = WebcamTracker(cfg) if args.tracker == "webcam" else MouseTracker()
        self.level = args.level
        self.custom_chart = load_chart(args.chart) if args.chart else None
        self.chart = self.custom_chart or chart_for_level(self.level)

        if self.tracker.uses_camera:
            saved = Calibration.load(cfg.calibration_path)
            self.calibrated = saved is not None
            self.calibration = saved or Calibration.default(cfg)
        else:
            self.calibrated, self.calibration = True, Calibration.identity()
        self.smoother = HandSmoother(cfg)
        self.calibrator = Calibrator(cfg)
        self.cal_phase = "ready"

        self.mode = MENU
        self.message = ""
        self.game: Game | None = None
        self.song_clock: SongClock | None = None
        self.summary = None
        self.saved_to = ""
        self.running = True

    def set_level(self, level: str) -> None:
        """Cambia el nivel de dificultad y actualiza el chart si no hay uno propio

        Args:
            level (str): Clave del nuevo nivel seleccionado
        """
        self.level = level
        self.chart = self.custom_chart or chart_for_level(level)

    def start_game(self) -> None:
        """Prepara y comienza una nueva partida con la configuracion del nivel"""
        play_cfg = level_config(self.cfg, self.level)
        self.renderer.cfg = play_cfg
        self.game = Game(self.chart, play_cfg)
        self.song_clock = SongClock(play_cfg.countdown)
        self.smoother = HandSmoother(self.cfg)
        self.renderer.reset_effects()
        self.mode = PLAY

    def finish_game(self) -> None:
        """Calcula las metricas finales, exporta los datos y pasa a resultados"""
        self.summary = summarize(
            self.game,
            self.player,
            level=self.level,
            calibration=self.calibration if self.tracker.uses_camera else None,
            camera_aspect=self.cfg.camera_size[1] / self.cfg.camera_size[0],
        )
        try:
            notes_csv, _ = export_session(self.game, self.summary, self.cfg.results_dir)
            self.saved_to = f"{notes_csv.parent.name}/{notes_csv.name}"
        except OSError as exc:
            self.saved_to = f"(no se pudo guardar: {exc})"
        self.mode = RESULTS

    def start_calibration(self) -> None:
        """Inicia la pantalla de calibracion en fase de espera"""
        self.calibrator = Calibrator(self.cfg)
        self.cal_phase = "ready"
        self.mode = CALIBRATION

    def finish_calibration(self) -> None:
        """Guarda la calibracion si es valida y regresa al menu principal"""
        result = self.calibrator.result()
        if result is None:
            self.message = "No se detectaron suficientes datos. Inténtalo de nuevo (tecla C)."
        else:
            self.calibration, self.calibrated = result, True
            result.save(self.cfg.calibration_path)
            self.message = "Calibración guardada."
        self.mode = MENU

    def toggle_pause(self) -> None:
        """Alterna entre pausa y reanudacion del reloj de la partida"""
        (self.song_clock.resume if self.song_clock.paused else self.song_clock.pause)()

    def handle_key(self, key: int) -> None:
        """Procesa una pulsacion de tecla segun el modo actual de la aplicacion

        Args:
            key (int): Codigo de tecla de Pygame presionada
        """
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
                self.toggle_pause()
            elif key == pygame.K_ESCAPE:
                if self.song_clock.paused:
                    self.mode = MENU
                else:
                    self.toggle_pause()
        elif self.mode == RESULTS:
            if key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self.mode = MENU
            elif key == pygame.K_r:
                self.start_game()

    def step(self) -> None:
        """Ejecuta la logica y el dibujo correspondientes a un fotograma"""
        now = time.monotonic()
        raw = self.tracker.read()
        preview = self.tracker.preview()

        if self.mode == CALIBRATION and self.cal_phase == "capturing":
            self.calibrator.add(raw)
            if self.calibrator.finished(now):
                self.finish_calibration()

        if self.mode == MENU:
            self.renderer.draw_menu(
                self.chart.title, self.tracker.name, self.calibrated, self.message, self.level
            )
        elif self.mode == CALIBRATION:
            self.renderer.draw_calibration(
                self.cal_phase, self.calibrator.progress(now), raw,
                self.calibrator.current_zone(), preview, self.calibrator.n_samples,
            )
        elif self.mode == PLAY:
            hands = self.smoother.apply(self.calibration.apply(raw))
            song_time = self.song_clock.song_time()
            if not self.song_clock.paused:
                self.renderer.add_events(self.game.update(song_time, hands), now)
            self.renderer.draw_game(self.game, song_time, hands, preview, now, self.song_clock.paused)
            if self.game.state is MatchState.FINISHED:
                self.finish_game()
        elif self.mode == RESULTS:
            self.renderer.draw_results(self.summary, self.saved_to)

        pygame.display.flip()

    def run(self) -> None:
        """Arranca el tracker, ejecuta el bucle principal y libera recursos al salir"""
        self.tracker.start()
        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        self.handle_key(event.key)
                self.step()
                self.clock.tick(self.cfg.fps)
        finally:
            self.tracker.stop()
            pygame.quit()


def main(argv=None) -> int:
    """Crea y ejecuta la aplicacion manejando errores esperados de inicio o ejecucion

    Args:
        argv: Argumentos opcionales de linea de comandos

    Returns:
        int: Codigo de salida del proceso
    """
    try:
        App(parse_args(argv)).run()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
    