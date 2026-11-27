"""Dibujo de pantallas, bloques, sables e interfaz en Pygame"""

from __future__ import annotations

import math
from collections import deque
from typing import Optional

import numpy as np
import pygame

from calibration import MovementZone
from config import DEFAULT_CONFIG, LEVELS, Config
from game import Game
from metrics import SessionSummary
from models import ChartNote, GameEvent, Hand, HandsFrame, Judgement

COLORS = {Hand.LEFT: (235, 64, 88), Hand.RIGHT: (64, 145, 255)}
LETTERS = {Hand.LEFT: "I", Hand.RIGHT: "D"}
JUDGEMENT_STYLE = {
    Judgement.PERFECT: ("¡PERFECTO!", (255, 215, 64)),
    Judgement.GOOD: ("BIEN", (120, 230, 140)),
    Judgement.OK: ("OK", (210, 210, 210)),
    Judgement.MISS: ("FALLO", (150, 150, 160)),
    Judgement.WRONG_HAND: ("OTRA MANO", (255, 150, 60)),
}
WHITE = (245, 245, 250)
GREY = (150, 155, 175)
POPUP_LIFETIME = 0.75


def _lerp_color(a, b, t):
    """Interpola linealmente entre dos colores RGB segun el factor t

    Args:
        a (tuple[int, int, int]): Color RGB inicial
        b (tuple[int, int, int]): Color RGB final
        t (float): Factor de interpolacion

    Returns:
        tuple[int, int, int]: Color RGB resultante
    """
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Renderer:
    """Dibuja las pantallas del juego y los efectos visuales sin logica de partida

    Attributes:
        screen (pygame.Surface): Superficie principal donde se renderiza la escena
        cfg (Config): Configuracion visual y geometrica del juego
        w (int): Ancho de la pantalla en pixeles
        h (int): Alto de la pantalla en pixeles
        font_xl (pygame.font.Font): Fuente tipografica extragrande
        font_l (pygame.font.Font): Fuente tipografica grande
        font_m (pygame.font.Font): Fuente tipografica mediana
        font_s (pygame.font.Font): Fuente tipografica pequenya
    """

    def __init__(self, screen: pygame.Surface, config: Config = DEFAULT_CONFIG):
        """Inicializa fuentes, fondo y contenedores de efectos visuales

        Args:
            screen (pygame.Surface): Ventana o superficie de dibujo de Pygame
            config (Config): Parametros de configuracion del juego
        """
        self.screen = screen
        self.cfg = config
        self.w, self.h = screen.get_size()
        names = "dejavusans,arial,helvetica"
        self.font_xl = pygame.font.SysFont(names, 110, bold=True)
        self.font_l = pygame.font.SysFont(names, 56, bold=True)
        self.font_m = pygame.font.SysFont(names, 30)
        self.font_s = pygame.font.SysFont(names, 22)
        self._bg = self._make_background()
        self._trails = {h: deque(maxlen=14) for h in Hand}
        self._popups: list[tuple[str, tuple, tuple[float, float], float]] = []

    def _make_background(self) -> pygame.Surface:
        """Crea una superficie con un degradado vertical de fondo

        Returns:
            pygame.Surface: Imagen de fondo generada para la pantalla actual
        """
        bg = pygame.Surface((self.w, self.h))
        top, bottom = (14, 12, 32), (38, 20, 62)
        for y in range(self.h):
            pygame.draw.line(bg, _lerp_color(top, bottom, y / self.h), (0, y), (self.w, y))
        return bg

    def text(self, s, font, color, pos, anchor="topleft", shadow=True, alpha=255):
        """Dibuja un texto en pantalla con sombra y transparencia opcionales

        Args:
            s (str): Texto a mostrar
            font (pygame.font.Font): Fuente usada para renderizar el texto
            color (tuple[int, int, int]): Color RGB del texto
            pos (tuple[int, int]): Coordenadas de posicion en pantalla
            anchor (str): Nombre del ancla del rectangulo del texto
            shadow (bool): Indica si se dibuja sombra detras del texto
            alpha (int): Nivel de opacidad entre 0 y 255

        Returns:
            pygame.Rect: Rectangulo delimitador del texto dibujado
        """
        surf = font.render(s, True, color)
        rect = surf.get_rect()
        setattr(rect, anchor, pos)
        if shadow:
            sh = font.render(s, True, (0, 0, 0))
            sh.set_alpha(int(alpha * 0.6))
            self.screen.blit(sh, rect.move(2, 2))
        surf.set_alpha(alpha)
        self.screen.blit(surf, rect)
        return rect

    def _preview_surface(self, frame: np.ndarray, size: tuple[int, int]) -> pygame.Surface:
        """Convierte un frame BGR de numpy a una superficie escalada de Pygame

        Args:
            frame (np.ndarray): Imagen de entrada en formato BGR
            size (tuple[int, int]): Dimensiones destino en pixeles

        Returns:
            pygame.Surface: Superficie escalada lista para dibujar
        """
        h, w = frame.shape[:2]
        rgb = np.ascontiguousarray(frame[:, :, ::-1])
        surf = pygame.image.frombuffer(rgb.tobytes(), (w, h), "RGB")
        return pygame.transform.smoothscale(surf, size)

    def _px(self, x: float, y: float) -> tuple[int, int]:
        """Convierte coordenadas normalizadas a pixeles de pantalla

        Args:
            x (float): Coordenada horizontal normalizada
            y (float): Coordenada vertical normalizada

        Returns:
            tuple[int, int]: Coordenadas en pixeles
        """
        return int(x * self.w), int(y * self.h)

    def _bar(self, rect: pygame.Rect, value: float, color=(120, 200, 255)):
        """Dibuja una barra de progreso horizontal dentro del rectangulo indicado

        Args:
            rect (pygame.Rect): Rectangulo exterior de la barra
            value (float): Proporcion de llenado entre 0 y 1
            color (tuple[int, int, int]): Color RGB del relleno
        """
        pygame.draw.rect(self.screen, (40, 40, 64), rect, border_radius=8)
        fill = rect.copy()
        fill.width = int(rect.width * max(0.0, min(value, 1.0)))
        if fill.width > 0:
            pygame.draw.rect(self.screen, color, fill, border_radius=8)
        pygame.draw.rect(self.screen, GREY, rect, 2, border_radius=8)

    def add_events(self, events: list[GameEvent], now: float) -> None:
        """Registra avisos visuales de evaluacion a partir de eventos de partida

        Args:
            events (list[GameEvent]): Eventos de golpe o fallo ocurridos
            now (float): Marca de tiempo actual en segundos
        """
        for e in events:
            label, color = JUDGEMENT_STYLE[e.judgement]
            self._popups.append((label, color, self.cfg.cell_center(e.note.col, e.note.row), now))

    def reset_effects(self) -> None:
        """Limpia los avisos flotantes y las estelas de ambas manos"""
        self._popups.clear()
        for t in self._trails.values():
            t.clear()

    def draw_menu(self, chart_title: str, tracker_name: str, calibrated: bool, message: str = "", level: str = "normal") -> None:
        """Dibuja la pantalla principal del menu

        Args:
            chart_title (str): Titulo de la cancion o patron cargado
            tracker_name (str): Nombre del metodo de seguimiento activo
            calibrated (bool): Indica si existe calibracion guardada
            message (str): Mensaje informativo o de aviso opcional
            level (str): Nivel de dificultad seleccionado
        """

