# IPM_beat_saber

Juego 2D inspirado en Beat Saber para la práctica de Interacción Persona-Máquina. La idea es controlar dos sables con los movimientos de las manos captados por una webcam y golpear bloques siguiendo un ritmo.

**Estado actual:** estructura inicial del proyecto. Los módulos solo contienen una descripción de su responsabilidad; la lógica del juego, la instalación y la ejecución están pendientes.

## Estructura del proyecto

```text
IPM_beat_saber/
├── README.md                 # Presentación y estructura del repositorio
├── LICENSE                   # Licencia del proyecto
└── beat_saber_ipm/            # Código y recursos del juego
    ├── main.py               # Punto de entrada e integración de módulos
    ├── config.py             # Configuración general
    ├── models.py             # Tipos de datos compartidos
    ├── tracking.py           # Webcam y detección de muñecas
    ├── calibration.py        # Coordenadas y zona de movimiento
    ├── game.py               # Reglas, colisiones, puntuación y estados
    ├── rendering.py          # Pantallas, bloques, sables e interfaz
    ├── rhythm.py             # Patrones de bloques y sincronización
    ├── metrics.py            # Estadísticas y exportación de resultados
    ├── assets/
    │   ├── audio/            # Música y efectos de sonido
    │   ├── charts/           # Patrones de aparición de bloques
    │   └── images/           # Imágenes y recursos gráficos
    ├── models/               # Archivos de modelos de detección
    ├── results/              # Resultados exportados
    ├── requirements.txt      # Dependencias previstas, aún comentadas
    ├── setup.ps1             # Futura preparación del entorno en Windows
    ├── setup.sh              # Futura preparación del entorno en Unix
    ├── .gitignore            # Exclusiones de entornos, cachés y resultados
    └── README.md             # Detalles y acuerdos de desarrollo
```

Las carpetas de recursos, modelos y resultados contienen un archivo `.gitkeep` para conservarlas en Git aunque todavía no tengan contenido. `models.py` definirá los tipos de datos de Python; la carpeta `models/` guardará los archivos de los modelos de detección.

## Organización de los módulos

- **Entrada y calibración:** `tracking.py` obtendrá las posiciones de las manos y `calibration.py` las adaptará a la zona de juego.
- **Lógica y ritmo:** `game.py` gestionará la partida y `rhythm.py` decidirá cuándo aparecen los bloques.
- **Representación y resultados:** `rendering.py` dibujará el juego y `metrics.py` calculará y exportará las estadísticas.
- **Integración:** `main.py` conectará los módulos, con la configuración de `config.py` y los datos compartidos de `models.py`.

Las tecnologías previstas son Python, OpenCV, MediaPipe y Pygame. El [README del juego](beat_saber_ipm/README.md) recoge el reparto de trabajo propuesto, el formato inicial de las posiciones de las manos y las etapas de desarrollo.

## Obtener la estructura

Si ya tienes el repositorio clonado, desde su carpeta ejecuta:

```bash
git switch main
git pull --ff-only origin main
```

El código del juego está dentro de `beat_saber_ipm/`. Las instrucciones de instalación y ejecución se añadirán cuando exista un prototipo funcional.
