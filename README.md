# IPM_beat_saber

Juego serio 2D inspirado en Beat Saber para la práctica de Interacción Persona-Máquina. El jugador controla dos sables con las manos, captadas por una webcam, y golpea bloques al ritmo de la música para entrenar la coordinación de los brazos. Al terminar, el juego exporta estadísticas (precisión, error de tiempo, equilibrio entre manos) pensadas para la evaluación con usuarios.

**Estado actual:** prototipo completo y jugable, con tres niveles de dificultad e indicadores funcionales. Está probado con 26 pruebas automáticas y con manos simuladas; **el seguimiento con webcam real debe validarse en un equipo con cámara**.

## Inicio rápido (Miniconda)

```bash
cd beat_saber_ipm
bash setup.sh                     # Windows: .\setup.ps1  (Anaconda PowerShell Prompt)
conda activate IPM_beat_saber
python main.py                    # con webcam
python main.py --tracker mouse    # sin cámara, con el ratón
```

Instalación detallada, controles, niveles, indicadores y entrega en el [README del juego](beat_saber_ipm/README.md).

## Estructura del proyecto

```text
IPM_beat_saber/
├── README.md                 # Presentación y estructura del repositorio
├── LICENSE                   # Licencia del proyecto
└── beat_saber_ipm/            # Código y recursos del juego
    ├── main.py               # Punto de entrada: menú, calibración, partida y resultados
    ├── config.py             # Configuración general (todos los parámetros ajustables)
    ├── models.py             # Tipos de datos compartidos (manos, bloques, eventos)
    ├── tracking.py           # Webcam + MediaPipe; trackers de ratón y simulado
    ├── calibration.py        # Zona de movimiento, calibración y suavizado
    ├── game.py               # Reglas, colisiones, puntuación y estados de partida
    ├── rendering.py          # Pantallas, bloques, sables e interfaz (Pygame)
    ├── rhythm.py             # Charts (patrones), generador de demo y reloj musical
    ├── metrics.py            # Estadísticas y exportación a CSV
    ├── tests/                # Pruebas automáticas (pytest)
    ├── download_models.py    # Descarga el modelo de MediaPipe
    ├── empaquetar.py         # Crea el .zip de la entrega
    ├── environment.yml       # Entorno de Miniconda
    ├── assets/
    │   ├── audio/            # Música y efectos (opcional)
    │   ├── charts/           # Patrones de bloques de cada nivel (suave, normal, intenso)
    │   └── images/           # Recursos gráficos (sin usar por ahora)
    ├── detection_models/     # Modelo de MediaPipe (lo descarga download_models.py)
    ├── results/              # Resultados exportados (CSV, no se versionan)
    ├── requirements.txt      # Dependencias (mismas versiones que environment.yml)
    ├── setup.ps1 / setup.sh  # Crea el entorno conda y descarga el modelo
    ├── conftest.py           # Permite a pytest importar los módulos
    ├── .gitignore            # Exclusiones de entornos, cachés, CSV y calibración
    └── README.md             # Manual del juego y acuerdos de desarrollo
```

La carpeta de modelos se llama `detection_models/` (antes `models/`) para no confundirla con `models.py`, que define los tipos de datos de Python.

## Tecnologías

Python 3.12 (Miniconda), OpenCV (cámara), MediaPipe Pose (muñecas y hombros), Pygame (gráficos, interacción y audio) y pytest.

## Actualizar el repositorio local

```bash
git switch main
git pull --ff-only origin main
```
