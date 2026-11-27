"""Captura de webcam y detección de muñecas.

Todos los trackers entregan un ``HandsFrame`` con coordenadas normalizadas en
modo espejo (ver models.py). Hay tres implementaciones intercambiables:

* ``WebcamTracker``: OpenCV + MediaPipe Pose (landmarks 15 y 16 = muñecas).
* ``MouseTracker``: depuración sin cámara (ratón = mano derecha; con Ctrl = izquierda).
* ``SimulatedTracker``: movimiento automático, útil para demos y pruebas.
"""
from __future__ import annotations

import math
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional

import numpy as np

from config import DEFAULT_CONFIG, Config
from models import Hand, HandPosition, HandsFrame


class HandTracker(ABC):
    #: True si las coordenadas vienen de una cámara y necesitan calibración.
    uses_camera: bool = False
    name: str = "tracker"

    def start(self) -> None:  # pragma: no cover - trivial
        pass

    def stop(self) -> None:  # pragma: no cover - trivial
        pass

    @abstractmethod
    def read(self) -> HandsFrame:
        """Último ``HandsFrame`` disponible (no bloquea)."""

    def preview(self) -> Optional[np.ndarray]:
        """Última imagen BGR en modo espejo (o ``None`` si no hay cámara)."""
        return None


class WebcamTracker(HandTracker):
    uses_camera = True
    name = "webcam"
    LEFT_WRIST = 15   # muñeca izquierda anatómica del jugador
    RIGHT_WRIST = 16
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12

    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.cfg = config
        self._lock = threading.Lock()
        self._frame = HandsFrame.empty()
        self._preview: Optional[np.ndarray] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cap = None
        self._landmarker = None

    # -- ciclo de vida ------------------------------------------------------
    def start(self) -> None:
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        if not self.cfg.pose_model_path.exists():
            raise FileNotFoundError(
                f"Falta el modelo de MediaPipe en {self.cfg.pose_model_path}.\n"
                "Descárgalo con:  python download_models.py   (o ejecuta setup.sh / setup.ps1)"
            )
        cap = cv2.VideoCapture(self.cfg.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.camera_size[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.camera_size[1])
        if not cap.isOpened():
            raise RuntimeError(
                f"No se pudo abrir la cámara {self.cfg.camera_index}. "
                "Prueba con --camera N o usa --tracker mouse."
            )
        options = vision.PoseLandmarkerOptions(
            # Python lee rutas Unicode; MediaPipe puede fallar con ellas en Windows.
            base_options=mp_python.BaseOptions(model_asset_buffer=self.cfg.pose_model_path.read_bytes()),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._cap = cap
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._mp = mp
        self._cv2 = cv2
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="webcam-tracker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._cap is not None:
            self._cap.release()
        if self._landmarker is not None:
            self._landmarker.close()

    # -- lectura ------------------------------------------------------------
    def read(self) -> HandsFrame:
        with self._lock:
            return self._frame

    def preview(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._preview

    # -- hilo de captura ----------------------------------------------------
    def _to_hand(self, lm) -> HandPosition:
        visibility = getattr(lm, "visibility", None)
        visible = visibility is None or visibility >= self.cfg.min_visibility
        inside = 0.0 <= lm.x <= 1.0 and 0.0 <= lm.y <= 1.0
        # La imagen de la cámara no está volteada: x_espejo = 1 - x.
        return HandPosition(1.0 - lm.x, lm.y, bool(visible and inside))

    def _loop(self) -> None:
        cv2, mp = self._cv2, self._mp
        t0 = time.monotonic()
        last_ts = -1
        while self._running:
            ok, bgr = self._cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            now = time.monotonic()
            # MediaPipe exige marcas de tiempo estrictamente crecientes (ms).
            ts = max(int((now - t0) * 1000), last_ts + 1)
            last_ts = ts
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            result = self._landmarker.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts
            )
            left = right = HandPosition()
            shoulder = 0.0
            if result.pose_landmarks:
                lms = result.pose_landmarks[0]
                left = self._to_hand(lms[self.LEFT_WRIST])
                right = self._to_hand(lms[self.RIGHT_WRIST])
                ls, rs = lms[self.LEFT_SHOULDER], lms[self.RIGHT_SHOULDER]
                if min(getattr(ls, "visibility", 1.0), getattr(rs, "visibility", 1.0)) >= self.cfg.min_visibility:
                    shoulder = abs(ls.x - rs.x)

            small = cv2.flip(cv2.resize(bgr, (320, 240)), 1)
            for pos, color in ((left, (88, 64, 235)), (right, (255, 145, 64))):
                if pos.valid:
                    center = (int(pos.x * 320), int(pos.y * 240))
                    cv2.circle(small, center, 8, color, -1)
            with self._lock:
                self._frame = HandsFrame(left, right, now, shoulder)
                self._preview = small


class MouseTracker(HandTracker):
    """Ratón = mano derecha. Manteniendo Ctrl, el ratón mueve la mano izquierda."""

    name = "mouse"

    def __init__(self) -> None:
        self._pos = {Hand.LEFT: (0.3, 0.6), Hand.RIGHT: (0.7, 0.6)}

    def read(self) -> HandsFrame:
        import pygame

        surface = pygame.display.get_surface()
        w, h = surface.get_size()
        mx, my = pygame.mouse.get_pos()
        active = Hand.LEFT if pygame.key.get_mods() & pygame.KMOD_CTRL else Hand.RIGHT
        self._pos[active] = (mx / w, my / h)
        return HandsFrame(
            HandPosition(*self._pos[Hand.LEFT], True),
            HandPosition(*self._pos[Hand.RIGHT], True),
            time.monotonic(),
        )


class SimulatedTracker(HandTracker):
    """Manos que se mueven solas. ``motion(t)`` -> (lx, ly, rx, ry) para personalizar."""

    name = "sim"

    def __init__(
        self,
        motion: Optional[Callable[[float], tuple[float, float, float, float]]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._motion = motion or self._default_motion
        self._clock = clock

    @staticmethod
    def _default_motion(t: float) -> tuple[float, float, float, float]:
        return (
            0.35 + 0.15 * math.sin(1.7 * t),
            0.50 + 0.20 * math.sin(2.3 * t + 1.0),
            0.65 + 0.15 * math.sin(1.9 * t + 2.0),
            0.50 + 0.20 * math.sin(2.1 * t),
        )

    def read(self) -> HandsFrame:
        t = self._clock()
        lx, ly, rx, ry = self._motion(t)
        return HandsFrame(HandPosition(lx, ly, True), HandPosition(rx, ry, True), t)
