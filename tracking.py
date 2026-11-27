"""Deteccion de posicion de manos mediante camara, raton o simulacion"""

from __future__ import annotations

import math
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional

import numpy as np

import cv2 as cv
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from config import DEFAULT_CONFIG, Config
from models import Hand, HandPosition, HandsFrame


class HandTracker(ABC):
    """Interfaz base para obtener frames con la posicion de ambas manos

    Attributes:
        uses_camera (bool): Indica si el tracker requiere camara
        name (str): Identificador del tracker
    """

    uses_camera: bool = False
    name: str = "tracker"

    def start(self) -> None:
        """Inicia los recursos necesarios para el seguimiento"""
        pass

    def stop(self) -> None:
        """Libera los recursos utilizados por el tracker"""
        pass

    @abstractmethod
    def read(self) -> HandsFrame:
        """Devuelve el ultimo estado disponible de las manos sin bloquear

        Returns:
            HandsFrame: Estructura con la posicion de ambas manos y marca de tiempo
        """

    def preview(self) -> Optional[np.ndarray]:
        """Devuelve la vista previa en modo espejo si el tracker usa camara

        Returns:
            Optional[np.ndarray]: Imagen BGR redimensionada o None si no aplica
        """
        return None


class WebcamTracker(HandTracker):
    """Detecta munyecas y ancho de hombros en tiempo real usando OpenCV y MediaPipe

    Attributes:
        uses_camera (bool): Verdadero al usar entrada de video
        name (str): Nombre del tracker de camara
        LEFT_WRIST (int): Indice del landmark de la munyeca izquierda
        RIGHT_WRIST (int): Indice del landmark de la munyeca derecha
        LEFT_SHOULDER (int): Indice del landmark del hombro izquierdo
        RIGHT_SHOULDER (int): Indice del landmark del hombro derecho
    """

    uses_camera = True
    name = "webcam"
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12

    def __init__(self, config: Config = DEFAULT_CONFIG):
        """Inicializa el tracker con la configuracion indicada

        Args:
            config (Config): Parametros de camara, modelo y visibilidad
        """
        self.cfg = config
        self._lock = threading.Lock()
        self._frame = HandsFrame.empty()
        self._preview: Optional[np.ndarray] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cap = None
        self._landmarker = None

    def start(self) -> None:
        """Abre la camara, carga el modelo de pose y arranca el hilo de captura

        Raises:
            FileNotFoundError: Si no existe el archivo del modelo de MediaPipe
            RuntimeError: Si no se puede abrir el dispositivo de camara
        """

        if not self.cfg.pose_model_path.exists():
            raise FileNotFoundError(
                f"Falta el modelo de MediaPipe en {self.cfg.pose_model_path}.\n"
                "Descárgalo con:  python download_models.py   (o ejecuta setup.sh / setup.ps1)"
            )
        cap = cv.VideoCapture(self.cfg.camera_index)
        cap.set(cv.CAP_PROP_FRAME_WIDTH, self.cfg.camera_size[0])
        cap.set(cv.CAP_PROP_FRAME_HEIGHT, self.cfg.camera_size[1])
        if not cap.isOpened():
            raise RuntimeError(
                f"No se pudo abrir la cámara {self.cfg.camera_index}. "
                "Prueba con --camera N o usa --tracker mouse."
            )
        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(self.cfg.pose_model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._cap = cap
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._mp = mp
        self._cv = cv
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="webcam-tracker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Detiene el hilo de captura y cierra la camara y el detector"""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._cap is not None:
            self._cap.release()
        if self._landmarker is not None:
            self._landmarker.close()

    def read(self) -> HandsFrame:
        """Devuelve de forma segura el ultimo frame detectado

        Returns:
            HandsFrame: Ultima captura procesada por el hilo de video
        """
        with self._lock:
            return self._frame

    def preview(self) -> Optional[np.ndarray]:
        """Devuelve la miniatura con las munyecas marcadas

        Returns:
            Optional[np.ndarray]: Imagen en espejo de 320x240 con marcadores o None
        """
        with self._lock:
            return self._preview

    def _to_hand(self, lm) -> HandPosition:
        """Convierte un landmark de MediaPipe a coordenadas normalizadas en espejo

        Args:
            lm: Punto de referencia detectado por el modelo de pose

        Returns:
            HandPosition: Posicion normalizada en modo espejo y estado de validez
        """
        visibility = getattr(lm, "visibility", None)
        visible = visibility is None or visibility >= self.cfg.min_visibility
        inside = 0.0 <= lm.x <= 1.0 and 0.0 <= lm.y <= 1.0
        return HandPosition(1.0 - lm.x, lm.y, bool(visible and inside))

    def _loop(self) -> None:
        """Captura frames continuamente, calcula la pose y actualiza el estado"""
        cv, mp = self._cv, self._mp
        t0 = time.monotonic()
        last_ts = -1
        while self._running:
            ok, bgr = self._cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            now = time.monotonic()
            ts = max(int((now - t0) * 1000), last_ts + 1)
            last_ts = ts
            rgb = cv.cvtColor(bgr, cv.COLOR_BGR2RGB)
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

            small = cv.flip(cv.resize(bgr, (320, 240)), 1)
            for pos, color in ((left, (88, 64, 235)), (right, (255, 145, 64))):
                if pos.valid:
                    center = (int(pos.x * 320), int(pos.y * 240))
                    cv.circle(small, center, 8, color, -1)
            with self._lock:
                self._frame = HandsFrame(left, right, now, shoulder)
                self._preview = small


class MouseTracker(HandTracker):
    """Simula la posicion de las manos usando el raton en una ventana de Pygame

    Attributes:
        name (str): Identificador del tracker de raton
    """

    name = "mouse"

    def __init__(self) -> None:
        """Inicializa posiciones por defecto para ambas manos"""
        self._pos = {Hand.LEFT: (0.3, 0.6), Hand.RIGHT: (0.7, 0.6)}

    def read(self) -> HandsFrame:
        """Actualiza la mano derecha o izquierda con Ctrl segun el cursor

        Returns:
            HandsFrame: Frame con las coordenadas normalizadas del cursor
        """
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
    """Genera trayectorias automaticas para pruebas sin entrada fisica

    Attributes:
        name (str): Identificador del tracker simulado
    """

    name = "sim"

    def __init__(
        self,
        motion: Optional[Callable[[float], tuple[float, float, float, float]]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Configura la funcion de movimiento y la fuente de tiempo

        Args:
            motion (Optional[Callable]): Funcion que recibe el tiempo y devuelve (lx, ly, rx, ry)
            clock (Callable): Funcion que devuelve el tiempo actual en segundos
        """
        self._motion = motion or self._default_motion
        self._clock = clock

    @staticmethod
    def _default_motion(t: float) -> tuple[float, float, float, float]:
        """Calcula posiciones oscilatorias por defecto para ambas manos en el tiempo t

        Args:
            t (float): Instante de tiempo en segundos

        Returns:
            tuple[float, float, float, float]: Coordenadas normalizadas (lx, ly, rx, ry)
        """
        return (
            0.35 + 0.15 * math.sin(1.7 * t),
            0.50 + 0.20 * math.sin(2.3 * t + 1.0),
            0.65 + 0.15 * math.sin(1.9 * t + 2.0),
            0.50 + 0.20 * math.sin(2.1 * t),
        )

    def read(self) -> HandsFrame:
        """Devuelve las posiciones simuladas en el instante actual

        Returns:
            HandsFrame: Frame generado a partir de la trayectoria calculada
        """
        t = self._clock()
        lx, ly, rx, ry = self._motion(t)
        return HandsFrame(HandPosition(lx, ly, True), HandPosition(rx, ry, True), t)