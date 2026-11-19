# Beat Saber IPM

## Objetivo y funcionamiento previsto

Práctica de Interacción Persona-Máquina de dos estudiantes: un juego 2D inspirado en Beat Saber para entrenar la coordinación de brazos mediante webcam. Cada mano controlará un sable para golpear bloques de su color siguiendo un ritmo. Más adelante se añadirán calibración, puntuación y estadísticas.

Se prevé utilizar Python, OpenCV para capturar la cámara, MediaPipe para detectar las muñecas y Pygame para gráficos, interacción y audio.

**Estado actual: solo existe la estructura inicial. Todavía no hay una aplicación ejecutable ni funcionalidades implementadas.**

## Archivos y responsabilidades

| Archivo | Responsabilidad |
| --- | --- |
| main.py | Inicio y conexión entre los módulos. |
| config.py | Configuración general del juego. |
| models.py | Futuros tipos de datos compartidos para manos, bloques y resultados. |
| tracking.py | Captura de webcam y detección de muñecas. |
| calibration.py | Adaptación de coordenadas y zona de movimiento. |
| game.py | Reglas, colisiones, puntuación y estados de partida. |
| rendering.py | Dibujo de pantallas, bloques, sables e interfaz. |
| rhythm.py | Lectura de patrones de bloques y sincronización temporal. |
| metrics.py | Cálculo y exportación de estadísticas. |
| requirements.txt | Comentarios con las dependencias previstas, pendientes de activar. |
| setup.ps1 | Marcador para la futura preparación del entorno en Windows. |
| setup.sh | Marcador para la futura preparación del entorno en sistemas Unix. |
| README.md | Objetivo, organización y acuerdos iniciales del proyecto. |
| .gitignore | Exclusiones de Python, archivos temporales y CSV generados en results/. |

Las carpetas assets/audio/, assets/charts/ y assets/images/ alojarán los recursos del juego; models/, los futuros archivos de modelos; y results/, los resultados exportados. Por ahora solo contienen un .gitkeep para conservarlas en Git.

## Reparto de trabajo propuesto

- **Pablo:** tracking.py, calibration.py, metrics.py y preparación del entorno.
- **Compañera:** game.py, rendering.py y rhythm.py.
- **Ambos:** acordar models.py y config.py e integrar mediante main.py.

## Acuerdo inicial de comunicación

La detección entregará las posiciones de ambas manos con coordenadas x e y normalizadas entre 0 y 1 y un indicador de validez para cada mano. Las coordenadas corresponderán a la pantalla en modo espejo y las manos se identificarán desde la perspectiva del jugador.

## Etapas previstas

1. Prototipos independientes.
2. Integración de los módulos.
3. Ritmo y sincronización.
4. Calibración.
5. Entrega.

## Instalación y ejecución

**Pendientes.** Las dependencias todavía no están activadas y los scripts de preparación solo contienen comentarios. Las instrucciones de instalación y ejecución se añadirán cuando exista una aplicación funcional.
