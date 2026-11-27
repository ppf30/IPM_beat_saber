# Beat Saber IPM — juego serio para el seguimiento funcional de los brazos

Práctica 2 de IPM (visión por computador). Juego 2D inspirado en Beat Saber que se controla con las manos delante de una **webcam**: cada mano es un sable y hay que golpear, al ritmo de la música, los bloques de su color. Mientras se juega, el sistema mide cómo se mueve la persona y guarda indicadores que permiten **seguir su evolución entre sesiones**.

## Utilidad: por qué es un juego serio

El juego está pensado para el ámbito de la **salud**, en dos líneas:

- **Rehabilitación física del tren superior.** Convierte ejercicios repetitivos de brazos (que suelen resultar aburridos) en una actividad motivadora, con retroalimentación inmediata y tres niveles de dificultad. Solo necesita un ordenador con webcam, así que se puede hacer en casa. Está pensado para poder usarse de pie o sentado, siempre que la cámara vea los hombros y los brazos (el uso sentado está por validar).
- **Apoyo al seguimiento de la fragilidad.** La fragilidad es la pérdida de reserva funcional que suele aparecer con la edad y se valora, entre otros aspectos, con la lentitud y el agotamiento (criterios de Fried). El juego no mide la fragilidad, pero registra indicadores funcionales relacionados con esos aspectos, de forma pasiva y sin material especial:

| Indicador | Cómo se obtiene | Qué refleja |
| --- | --- | --- |
| Error de tiempo (ms) y sesgo | Diferencia entre el golpe y el instante ideal | Sincronización y tiempo de reacción |
| Velocidad media del golpe | Velocidad de la muñeca al acertar | Rapidez de movimiento |
| Amplitud de movimiento | Zona que recorren las manos en la calibración, en anchos de hombro (no depende de la distancia a la cámara) | Movilidad del hombro y el brazo |
| Precisión izquierda / derecha y equilibrio | Aciertos por mano | Simetría entre brazos |
| Fatiga | Caída de precisión y de velocidad de la 2ª mitad respecto a la 1ª | Resistencia durante la sesión |
| % de mano no detectada | Fotogramas sin detección por mano | Calidad de la medida |

> **Aviso:** son indicadores orientativos de seguimiento personal, **no un diagnóstico** ni están validados clínicamente. Medidas como la fuerza de agarre o la velocidad de la marcha quedan fuera de este juego.

## Modo de empleo

- Necesitas **Miniconda** y una webcam (sin cámara se puede probar con `--tracker mouse`).
- Asegúrate de tener instalados todos los requerimientos
```bash
pip install requirements.txt
```
- Desde el Anaconda Poweshell:

1. Crea el entorno y descarga el modelo:
   ```bash
   conda env create -f environment.yml
   conda activate IPM_beat_saber
   python download_models.py
   ```
2. Activa el entorno y ejecuta:
   ```bash
   conda activate IPM_beat_saber
   python main.py
   ```


**Teclas:** `1`-`3` nivel · `ENTER` jugar · `C` calibrar · `P` pausa · `ESC` pausa / abandonar / salir · `R` repetir (en resultados).

**Primera vez:** pulsa `C`, colócate a 1,5–2 m de la cámara con los hombros y los brazos visibles, pulsa `ESPACIO` y durante 8 s lleva ambas manos al máximo alcance cómodo (arriba, abajo, izquierda y derecha). La zona recorrida se ajusta a la pantalla de juego y se guarda en `calibration.json`. Repite la calibración si cambias de persona o de sitio.

## Cómo se juega

- Cada bloque aparece unos instantes antes de su momento y un aro blanco se cierra sobre él: hay que golpearlo cuando el aro lo alcanza.
- Se golpea con **la mano de su color** (**I** = izquierda, roja; **D** = derecha, azul) y **en movimiento**: pasar la mano rápido, no apoyarla. Usar la otra mano rompe la racha.
- **Perfecto** (100 pts), **Bien** (70) y **OK** (40) según la precisión temporal, cada 10 aciertos seguidos sube el multiplicador.

## Estadísticas guardadas

Al terminar cada partida se escribe en `results/`:

- `<fecha>_<jugador>_notes.csv`: una fila por bloque (instante, mano, celda, resultado, error en ms, velocidad del golpe, puntos).
- `summary.csv`: una fila por partida con los indicadores de la tabla anterior, además de precisión, aciertos por tipo, mejor racha y nivel. Al acumular filas del mismo jugador se ve su evolución entre sesiones.

## Cómo está hecho

```text
webcam ─► tracking.py ──► calibration.py ──► game.py ──► rendering.py
          (MediaPipe       (zona de movimiento   (colisiones,   (Pygame)
           Pose: muñecas    y suavizado)          puntuación)       │
           y hombros)                                │              ▼
                                  rhythm.py ─────────┘          pantalla
                                  (charts y reloj)      game.py ──► metrics.py ──► results/*.csv
```

- **tracking.py**: hilo de captura con OpenCV + MediaPipe Pose (API *Tasks*, modelo `pose_landmarker_full`). Usa las muñecas (landmarks 15 y 16) y los hombros (11 y 12). La imagen se interpreta en modo espejo y las manos se asignan desde la perspectiva del jugador. Incluye `MouseTracker` y `SimulatedTracker` para desarrollar sin cámara.
- **calibration.py**: calcula la zona de movimiento de cada persona, suaviza la señal y tolera pérdidas breves de detección.
- **game.py**: reglas de colisión, velocidad de golpe, puntuación y estados. No depende de pantalla ni cámara, por lo que se prueba con datos sintéticos.
- **rhythm.py**: carga los patrones de bloques (JSON), genera los de cada nivel y mantiene el reloj de la canción.
- **rendering.py**: todas las pantallas y la interfaz; siempre con letra además de color para no depender solo de este.
- **metrics.py**: calcula los indicadores y exporta los CSV.
- **config.py** reúne todos los parámetros; **models.py** los tipos de datos compartidos.

Convención de coordenadas: `x`, `y` entre 0 y 1, imagen en modo espejo, `left` = mano izquierda del jugador, `valid` por mano y `timestamp` en segundos.



## Limitaciones y trabajo futuro

- La amplitud de movimiento es una estimación 2D con una sola cámara; no sustituye a una medida clínica.
- La fatiga solo es significativa en sesiones largas; las sesiones de demostración duran menos de un minuto.
- Faltan validación clínica y valores de referencia por edad; haría falta un estudio con usuarios y profesionales sanitarios.
- Mejoras posibles: música real con su patrón, informe gráfico de evolución por jugador, modo sentado con una rejilla adaptada y corrección de la latencia de la cámara.
