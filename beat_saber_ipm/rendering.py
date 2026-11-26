"""Dibujo de pantallas, bloques, sables e interfaz (Pygame).

El renderizador solo dibuja: no decide nada sobre reglas ni sobre el flujo del
programa. Los colores se acompañan siempre de una letra (I/D) para no depender
únicamente del color (accesibilidad).
"""
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
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Renderer:
    def __init__(self, screen: pygame.Surface, config: Config = DEFAULT_CONFIG):
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

    # ------------------------------------------------------------------ util
    def _make_background(self) -> pygame.Surface:
        bg = pygame.Surface((self.w, self.h))
        top, bottom = (14, 12, 32), (38, 20, 62)
        for y in range(self.h):
            pygame.draw.line(bg, _lerp_color(top, bottom, y / self.h), (0, y), (self.w, y))
        return bg

    def text(self, s, font, color, pos, anchor="topleft", shadow=True, alpha=255):
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
        h, w = frame.shape[:2]
        rgb = np.ascontiguousarray(frame[:, :, ::-1])
        surf = pygame.image.frombuffer(rgb.tobytes(), (w, h), "RGB")
        return pygame.transform.smoothscale(surf, size)

    def _px(self, x: float, y: float) -> tuple[int, int]:
        return int(x * self.w), int(y * self.h)

    def _bar(self, rect: pygame.Rect, value: float, color=(120, 200, 255)):
        pygame.draw.rect(self.screen, (40, 40, 64), rect, border_radius=8)
        fill = rect.copy()
        fill.width = int(rect.width * max(0.0, min(value, 1.0)))
        if fill.width > 0:
            pygame.draw.rect(self.screen, color, fill, border_radius=8)
        pygame.draw.rect(self.screen, GREY, rect, 2, border_radius=8)

    # ---------------------------------------------------------------- estado
    def add_events(self, events: list[GameEvent], now: float) -> None:
        for e in events:
            label, color = JUDGEMENT_STYLE[e.judgement]
            self._popups.append((label, color, self.cfg.cell_center(e.note.col, e.note.row), now))

    def reset_effects(self) -> None:
        self._popups.clear()
        for t in self._trails.values():
            t.clear()

    # ------------------------------------------------------------- pantallas
    def draw_menu(
        self, chart_title: str, tracker_name: str, calibrated: bool, message: str = "", level: str = "normal"
    ) -> None:
        self.screen.blit(self._bg, (0, 0))
        cx = self.w // 2
        self.text("BEAT SABER IPM", self.font_xl, WHITE, (cx, 120), "center")
        self.text("Entrena la coordinación de tus brazos", self.font_m, GREY, (cx, 200), "center")
        self.text(f"Canción: {chart_title}", self.font_m, WHITE, (cx, 275), "center")
        x = cx - 300
        for i, name in enumerate(LEVELS, start=1):
            selected = name == level
            rect = pygame.Rect(0, 0, 190, 40)
            rect.center = (cx - 200 + (i - 1) * 200, 325)
            pygame.draw.rect(self.screen, (90, 70, 170) if selected else (36, 34, 60), rect, border_radius=10)
            pygame.draw.rect(self.screen, WHITE if selected else GREY, rect, 2, border_radius=10)
            self.text(f"{i}  {name}", self.font_s, WHITE if selected else GREY, rect.center, "center", shadow=False)
        cal = "calibrada" if calibrated else "sin calibrar (se usa la zona por defecto)"
        self.text(f"Entrada: {tracker_name} · {cal}", self.font_s, GREY, (cx, 370), "center")
        for i, hand in enumerate((Hand.LEFT, Hand.RIGHT)):
            x = cx - 170 + i * 340
            pygame.draw.circle(self.screen, COLORS[hand], (x, 430), 34)
            self.text(LETTERS[hand], self.font_l, WHITE, (x, 430), "center", shadow=False)
            label = "mano izquierda" if hand is Hand.LEFT else "mano derecha"
            self.text(label, self.font_s, WHITE, (x, 485), "center")
        self.text("Golpea cada bloque con la mano de su color, en el momento en que se cierra el aro",
                  self.font_s, GREY, (cx, 540), "center")
        self.text("1-3: nivel    ENTER: jugar    C: calibrar    ESC: salir", self.font_m, WHITE, (cx, 620), "center")
        if message:
            self.text(message, self.font_s, (255, 215, 64), (cx, 680), "center")

    def draw_calibration(
        self,
        phase: str,
        progress: float,
        hands: HandsFrame,
        zone: Optional[MovementZone],
        preview: Optional[np.ndarray],
        n_samples: int,
    ) -> None:
        self.screen.blit(self._bg, (0, 0))
        cx = self.w // 2
        self.text("CALIBRACIÓN", self.font_l, WHITE, (cx, 50), "center")
        if phase == "ready":
            msg = "Colócate de pie, con los brazos visibles. Pulsa ESPACIO y empieza."
        else:
            msg = "Mueve ambas manos al máximo alcance: arriba, abajo, izquierda y derecha."
        self.text(msg, self.font_s, GREY, (cx, 105), "center")

        rect = pygame.Rect(0, 0, 640, 480)
        rect.center = (cx, 380)
        if preview is not None:
            self.screen.blit(self._preview_surface(preview, rect.size), rect)
        else:
            pygame.draw.rect(self.screen, (24, 24, 44), rect)
        pygame.draw.rect(self.screen, GREY, rect, 2)
        if zone is not None:
            z = pygame.Rect(
                rect.x + zone.x_min * rect.w, rect.y + zone.y_min * rect.h,
                (zone.x_max - zone.x_min) * rect.w, (zone.y_max - zone.y_min) * rect.h,
            )
            pygame.draw.rect(self.screen, (255, 215, 64), z, 3)
        for hand in Hand:
            p = hands.get(hand)
            if p.valid:
                pos = (int(rect.x + p.x * rect.w), int(rect.y + p.y * rect.h))
                pygame.draw.circle(self.screen, COLORS[hand], pos, 14)
                pygame.draw.circle(self.screen, WHITE, pos, 14, 2)
        self._bar(pygame.Rect(rect.x, rect.bottom + 20, rect.w, 22), progress)
        if phase == "capturing" and n_samples == 0:
            self.text("No se detectan tus manos", self.font_s, (255, 150, 60),
                      (cx, rect.bottom + 70), "center")

    def draw_game(
        self,
        game: Game,
        song_time: float,
        hands: HandsFrame,
        preview: Optional[np.ndarray],
        now: float,
        paused: bool = False,
    ) -> None:
        cfg = self.cfg
        self.screen.blit(self._bg, (0, 0))
        self._draw_grid()
        for note, progress in sorted(game.visible_notes(song_time), key=lambda t: -t[1]):
            self._draw_block(note, progress)
        self._draw_sabers(hands)
        self._draw_popups(now)
        self._draw_hud(game, song_time, hands, preview)
        if song_time < 0:
            self.text(str(math.ceil(-song_time)), self.font_xl, WHITE, (self.w // 2, self.h // 2), "center")
            self.text("¡Prepárate!", self.font_m, GREY, (self.w // 2, self.h // 2 + 90), "center")
        if paused:
            veil = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            veil.fill((0, 0, 0, 150))
            self.screen.blit(veil, (0, 0))
            self.text("PAUSA", self.font_xl, WHITE, (self.w // 2, self.h // 2 - 30), "center")
            self.text("P: continuar    ESC: abandonar", self.font_m, GREY, (self.w // 2, self.h // 2 + 60), "center")

    def draw_results(self, s: SessionSummary, saved_to: str = "") -> None:
        self.screen.blit(self._bg, (0, 0))
        cx = self.w // 2
        self.text(f"RESULTADOS · nivel {s.level}" if s.level else "RESULTADOS", self.font_l, WHITE, (cx, 50), "center")
        self.text(f"{s.score}", self.font_xl, (255, 215, 64), (cx, 130), "center")
        self.text("puntos", self.font_s, GREY, (cx, 192), "center")
        rows = [
            ("Precisión", f"{s.accuracy * 100:.0f}%  ({s.hits}/{s.total_notes} bloques)"),
            ("Perfectos / Bien / OK", f"{s.perfect} / {s.good} / {s.ok}"),
            ("Fallos / mano equivocada", f"{s.misses} / {s.wrong_hand}"),
            ("Mejor racha", f"{s.max_combo}"),
            ("Error de tiempo medio", f"{s.mean_abs_error_ms:.0f} ms  (sesgo {s.mean_error_ms:+.0f} ms)"),
            ("Precisión izq. / der.", f"{s.accuracy_left * 100:.0f}% / {s.accuracy_right * 100:.0f}%"),
            ("Velocidad media del golpe", f"{s.mean_hit_speed_px_s:.0f} px/s"),
            ("Amplitud de movimiento", f"{s.rom_x:.1f} × {s.rom_y:.1f} anchos de hombro" if s.rom_x else "sin calibrar con cámara"),
            ("Fatiga (2ª mitad vs 1ª)", f"precisión {-s.accuracy_drop_pp:+.0f} pp · velocidad {-s.speed_drop_pct:+.0f}%"),
            ("Mano no detectada izq. / der.", f"{s.tracking_loss_left * 100:.0f}% / {s.tracking_loss_right * 100:.0f}%"),
        ]
        y = 232
        for label, value in rows:
            self.text(label, self.font_m, GREY, (cx - 40, y), "topright")
            self.text(value, self.font_m, WHITE, (cx + 40, y), "topleft")
            y += 38
        if saved_to:
            self.text(f"Guardado en {saved_to}", self.font_s, GREY, (cx, 640), "center")
        self.text("ENTER: menú    R: repetir", self.font_m, WHITE, (cx, 685), "center")

    # --------------------------------------------------------------- piezas
    def _draw_grid(self) -> None:
        cfg = self.cfg
        for col in range(cfg.grid_cols):
            for row in range(cfg.grid_rows):
                c = cfg.cell_center(col, row)
                pygame.draw.circle(self.screen, (52, 48, 86), c, int(cfg.block_radius * 0.55), 2)

    def _draw_block(self, note: ChartNote, progress: float) -> None:
        cfg = self.cfg
        color = COLORS[note.hand]
        cx, cy = cfg.cell_center(note.col, note.row)
        p = max(progress, 0.0)
        radius = int(cfg.block_radius * (0.7 + 0.3 * (1 - p)))
        pygame.draw.circle(self.screen, _lerp_color((20, 20, 30), color, 0.55), (cx, cy), radius)
        pygame.draw.circle(self.screen, color, (cx, cy), radius, 5)
        ring = int(cfg.block_radius * (1 + 1.8 * p))
        pygame.draw.circle(self.screen, WHITE, (cx, cy), ring, 3)
        self.text(LETTERS[note.hand], self.font_l, WHITE, (cx, cy), "center", shadow=False)

    def _draw_sabers(self, hands: HandsFrame) -> None:
        for hand in Hand:
            p = hands.get(hand)
            trail = self._trails[hand]
            if not p.valid:
                trail.clear()
                continue
            pos = self._px(p.x, p.y)
            trail.append(pos)
            color = COLORS[hand]
            pts = list(trail)
            for i in range(1, len(pts)):
                t = i / len(pts)
                pygame.draw.line(self.screen, _lerp_color((30, 30, 50), color, t), pts[i - 1], pts[i],
                                 max(2, int(self.cfg.saber_radius * 1.4 * t)))
            pygame.draw.circle(self.screen, color, pos, int(self.cfg.saber_radius))
            pygame.draw.circle(self.screen, WHITE, pos, int(self.cfg.saber_radius * 0.5))

    def _draw_popups(self, now: float) -> None:
        alive = []
        for label, color, (x, y), t0 in self._popups:
            age = now - t0
            if age > POPUP_LIFETIME:
                continue
            alive.append((label, color, (x, y), t0))
            k = age / POPUP_LIFETIME
            self.text(label, self.font_m, color, (x, y - 70 - 40 * k), "center", alpha=int(255 * (1 - k)))
        self._popups = alive

    def _draw_hud(self, game: Game, song_time: float, hands: HandsFrame, preview) -> None:
        self.text(f"{game.score}", self.font_l, WHITE, (30, 20))
        self.text(f"Precisión {game.accuracy * 100:.0f}%", self.font_s, GREY, (32, 85))
        if game.combo >= 2:
            mult = min(1 + game.combo // self.cfg.combo_step, self.cfg.max_multiplier)
            self.text(f"{game.combo} seguidos  x{mult}", self.font_m, (255, 215, 64),
                      (self.w // 2, 30), "center")
        if preview is not None:
            surf = self._preview_surface(preview, (240, 180))
            rect = surf.get_rect(topright=(self.w - 20, 20))
            self.screen.blit(surf, rect)
            pygame.draw.rect(self.screen, GREY, rect, 2)
        self._bar(pygame.Rect(30, self.h - 40, self.w - 60, 14), game.progress(song_time), (140, 120, 255))
        lost = [("izquierda", Hand.LEFT), ("derecha", Hand.RIGHT)]
        warn = [name for name, h in lost if not hands.get(h).valid]
        if warn and song_time >= 0:
            self.text("No se detecta tu mano " + " ni tu mano ".join(warn), self.font_s,
                      (255, 150, 60), (self.w // 2, self.h - 70), "center")
