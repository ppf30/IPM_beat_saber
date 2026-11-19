"""Datos de las manos compartidos entre la detección y el juego.

Las coordenadas están normalizadas entre 0 y 1, con origen en la esquina
superior izquierda de la vista en espejo: x crece hacia la derecha e y
hacia abajo. Estos tipos no dependen de la biblioteca de detección.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class HandPosition:
    """Posición de una muñeca en la captura actual.

    Si no se detecta la mano, se representa con valid=False y x=y=None.
    Una posición no válida nunca debe producir un golpe.
    """

    x: Optional[float] = None
    y: Optional[float] = None
    valid: bool = False

    def __post_init__(self) -> None:
        if self.valid:
            if self.x is None or self.y is None:
                raise ValueError("Una mano válida necesita ambas coordenadas.")
            if not (0.0 <= self.x <= 1.0 and 0.0 <= self.y <= 1.0):
                raise ValueError("Las coordenadas deben estar entre 0 y 1.")
        elif self.x is not None or self.y is not None:
            raise ValueError("Una mano no detectada no debe conservar coordenadas.")


@dataclass(frozen=True)
class HandsFrame:
    """Posiciones de ambas manos correspondientes a una misma captura.

    captured_at es el instante de captura en segundos de time.monotonic(),
    independiente del tiempo de la canción. left y right son las manos
    izquierda (sable rojo) y derecha (sable azul) del jugador, aunque sus
    posiciones se crucen en pantalla. Cada captura debe usar las detecciones
    actuales; si se pierde una mano, se usa HandPosition() para esa mano.
    """

    captured_at: float
    left: HandPosition = field(default_factory=HandPosition)
    right: HandPosition = field(default_factory=HandPosition)
