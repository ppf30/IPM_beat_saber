# Beat Saber IPM — juego serio para el seguimiento funcional de los brazos

Práctica 2 de IPM (visión por computador). Juego 2D inspirado en Beat Saber que se controla con las manos delante de una **webcam**: cada mano es un sable y hay que golpear los bloques de su color siguiendo un **patrón rítmico visual**. Mientras se juega, el sistema registra indicadores de coordinación y movimiento que permiten **comparar el rendimiento entre sesiones**. La versión actual no reproduce música ni efectos de sonido.

## Utilidad: por qué es un juego serio

El proyecto explora dos posibles aplicaciones en el ámbito de la **salud**:

- **Ejercicio de brazos y posible apoyo a la rehabilitación.** Propone movimientos repetidos de brazos mediante una actividad con retroalimentación visual inmediata y tres niveles de dificultad. Requiere un ordenador con webcam. Su utilidad en rehabilitación y su uso sentado están pendientes de validación.
- **Registro del rendimiento para su seguimiento.** Guarda indicadores de sincronización, movimiento y aciertos por mano. Estos datos permiten explorar cambios entre sesiones; su posible relación con la fragilidad requeriría un estudio específico.

Los indicadores implementados son:

| Indicador | Cómo se obtiene | Qué refleja |
| --- | --- | --- |
| Error temporal y sesgo (ms) | Error absoluto medio y error medio con signo de los aciertos; negativo = anticipación, positivo = retraso | Sincronización con el objetivo visual |
| Velocidad media del golpe (px/s) | Velocidad estimada de la muñeca en coordenadas de pantalla al acertar | Rapidez del movimiento representado en el juego |
| Amplitud de la zona de calibración | Rango horizontal y vertical conjunto de ambas manos, normalizado por el ancho de hombros | Extensión de la zona de movimiento registrada al calibrar |
| Proporción de aciertos izquierda / derecha | Bloques acertados divididos entre los asignados a cada mano | Diferencias de rendimiento entre manos |
| Caída de rendimiento | Diferencia de precisión y velocidad entre la primera y la segunda mitad de los resultados, divididos por número de bloques | Variación del rendimiento durante la partida |
| Pérdida de seguimiento por mano | Fracción de actualizaciones del juego con la mano no válida, después del suavizado y la tolerancia a pérdidas breves | Disponibilidad del seguimiento utilizado para jugar |

> **Aviso:** es un prototipo académico. Sus indicadores son orientativos, **no permiten diagnosticar fragilidad, fatiga ni otras condiciones** y no están validados clínicamente. El error temporal no es una prueba de tiempo de reacción. Medidas como la fuerza de agarre o la velocidad de la marcha quedan fuera de este juego.

## Instalación y ejecución

Necesitas **Miniconda o Anaconda**, una webcam para el control por movimiento y conexión a Internet para instalar las dependencias y descargar el modelo. El entorno del proyecto utiliza **Python 3.12**.

Abre una terminal con Conda disponible (en Windows, por ejemplo, **Anaconda PowerShell Prompt**) y sitúate en la carpeta del repositorio, donde está `main.py`.

1. Crea el entorno e instala las dependencias:

   ```powershell
   conda env create -f environment.yml
   conda activate IPM_beat_saber
   ```

   `environment.yml` ya instala las dependencias de `requirements.txt`; no hace falta instalarlas de nuevo. Si utilizas un entorno propio con Python 3.12, el comando equivalente para instalar solo las dependencias es `python -m pip install -r requirements.txt`.

2. Descarga el modelo de detección de pose:

   ```powershell
   python download_models.py
   ```

   Se guarda en `detection_models/pose_landmarker_full.task`. El script omite la descarga si el archivo ya existe y no está vacío.

3. Ejecuta el juego con un identificador de jugador:

   ```powershell
   python main.py --player Pablo
   ```

   Usa el mismo identificador para comparar sesiones de la misma persona. También puedes ejecutar `python main.py`; en ese caso, el campo `player` del resumen queda vacío y el archivo de detalle utiliza `anonimo`.

En las siguientes ejecuciones basta con activar el entorno y arrancar el juego desde la carpeta del repositorio:

```powershell
conda activate IPM_beat_saber
python main.py --player Pablo
```

### Prueba sin cámara

```powershell
python main.py --tracker mouse --player prueba
```

Mueve el ratón para controlar la **mano derecha**. Mantén pulsado `Ctrl` mientras lo mueves para controlar la **izquierda**; la otra mano conserva su última posición. No hace falta hacer clic. Este modo no requiere descargar el modelo ni calibrar, aunque sí instalar las dependencias. También guarda resultados, por lo que conviene usar un identificador distinto al de las sesiones con webcam.

### Opciones de ejecución

| Opción | Uso |
| --- | --- |
| `--tracker webcam` / `--tracker mouse` | Selecciona la entrada; por defecto, `webcam` |
| `--camera 1` | Cambia el índice de la webcam; por defecto, `0` |
| `--level suave` / `normal` / `intenso` | Selecciona el nivel inicial; por defecto, `normal` |
| `--player Pablo` | Identifica al jugador en las estadísticas |
| `--fullscreen` | Abre el juego a pantalla completa |
| `--chart ruta/patron.json` | Carga un patrón propio en lugar del generado para cada nivel |
| `--help` | Muestra la ayuda de los argumentos |

## Controles y calibración

| Pantalla | Teclas |
| --- | --- |
| Menú | `1`: suave; `2`: normal; `3`: intenso; `ENTER`: jugar; `C`: calibrar con webcam; `ESC`: salir |
| Calibración | `ESPACIO`: iniciar la captura; `ESC`: cancelar y volver al menú |
| Partida | `P`: pausar o reanudar; `ESC`: pausar y, si ya está en pausa, abandonar al menú |
| Resultados | `R`: repetir; `ENTER` o `ESC`: volver al menú |

**Primera vez con webcam:** pulsa `C` en el menú y colócate de frente a la cámara, con los hombros y los brazos visibles durante todo el recorrido. Pulsa `ESPACIO` y durante **8 segundos** mueve ambas manos por su máximo alcance cómodo: arriba, abajo, izquierda y derecha.

La zona registrada se adapta a las coordenadas de la pantalla y se guarda, junto con el ancho de hombros estimado, en `calibration.json`. Se reutiliza al abrir el juego. Repite la calibración si cambias de persona, posición o encuadre. Si no hay suficientes muestras, el juego lo indica y permite repetirla. Se puede jugar sin calibrar, usando una zona por defecto, pero no se obtiene una amplitud normalizada válida.

## Cómo se juega

- Cada bloque aparece antes de su instante objetivo y un **marco blanco cuadrado** se cierra sobre él: hay que golpearlo cuando el marco alcanza el bloque.
- Se golpea con **la mano de su color** (**I** = izquierda, roja; **D** = derecha, azul) y **en movimiento**: pasar la mano rápido, no apoyarla. Usar la otra mano rompe la racha.
- **Perfecto** (100 puntos base), **Bien** (70) y **OK** (40) según la precisión temporal. Tras acumular 10, 20 y 30 aciertos seguidos, el multiplicador de los siguientes golpes pasa a ×2, ×3 y ×4. Un bloque perdido o un golpe con la mano incorrecta reinicia la racha.
- Los niveles cambian el tempo, los márgenes de acierto y la velocidad mínima de golpe; el nivel suave también amplía los bloques. Los patrones de demostración avanzan desde golpes individuales hasta golpes simultáneos con ambas manos.

## Estadísticas guardadas

Al completar una partida se escribe en `results/`, dentro de la carpeta del proyecto:

- `<AAAAMMDDhhmmss>_<jugador>_notes.csv`: una fila por bloque con su instante objetivo (`note_time_s`), mano requerida (`hand`), celda (`col`, `row`), resultado (`judgement`), error temporal (`time_error_ms`), velocidad (`hand_speed_px_s`) y puntos obtenidos por ese bloque (`score`). Los resultados son `perfect`, `good`, `ok` o `miss`; en los fallos, el error y la velocidad quedan vacíos.
- `summary.csv`: añade una fila por partida con fecha y hora, jugador, nivel, patrón, total de bloques, aciertos, fallos, golpes con la mano incorrecta, puntuación final, mejor racha y los indicadores descritos arriba. Los golpes con la mano incorrecta se cuentan en `wrong_hand`; no generan una fila adicional en el archivo de bloques ni resuelven el bloque, que todavía se puede acertar.

Las partidas que se abandonan antes de completarlas, desde la pausa o al cerrar la ventana, no se exportan. Los CSV y la calibración personal están excluidos de Git mediante `.gitignore`.

### Interpretación de los datos

- `accuracy`, `accuracy_left`, `accuracy_right` y `tracking_loss_left/right` son proporciones entre 0 y 1 en el CSV; para expresarlas como porcentaje hay que multiplicarlas por 100.
- `accuracy_drop_pp` es la precisión de la primera mitad menos la de la segunda, en puntos porcentuales. `speed_drop_pct` es la caída porcentual de velocidad respecto a la primera mitad. Un valor negativo indica mejora. Las mitades se forman por cantidad de resultados de bloques, en orden de resolución, y pueden abarcar tiempos distintos. El patrón también cambia de dificultad durante la partida, por lo que una caída no demuestra fatiga.
- `mean_hit_speed_px_s` se calcula sobre los aciertos y depende de la calibración, el suavizado y las coordenadas de pantalla; no es una velocidad física en metros por segundo.
- `rom_x` y `rom_y` proceden de la zona conjunta de calibración guardada, no de una medición nueva por brazo durante cada partida. La normalización por hombros reduce la dependencia de la distancia a la cámara, pero sigue siendo una estimación 2D sensible al encuadre y a la postura.
- La pérdida de seguimiento se cuenta en las actualizaciones del juego, después de conservar posiciones durante pérdidas breves de hasta 0,15 segundos; no representa directamente el porcentaje de fotogramas originales de cámara sin detección.
- Algunos indicadores se guardan como `0` cuando no hay datos suficientes: por ejemplo, la amplitud sin ancho de hombros válido o la caída de velocidad sin aciertos con velocidad positiva en ambas mitades. Conviene revisar los aciertos y la calibración antes de interpretarlos.

Para comparar sesiones, utiliza el mismo jugador, modo de entrada, nivel, patrón y condiciones de cámara y calibración. La comparación se realiza a partir de los CSV; todavía no hay un informe automático de evolución.

## Patrones personalizados

La opción `--chart` acepta un archivo JSON como este:

```json
{
  "title": "Ejemplo",
  "bpm": 60,
  "notes": [
    {"beat": 4, "hand": "left", "col": 0, "row": 1},
    {"beat": 6, "hand": "right", "col": 3, "row": 1}
  ]
}
```

Guárdalo, por ejemplo, como `assets/charts/ejemplo.json` y ejecuta:

```powershell
python main.py --chart assets/charts/ejemplo.json --player Pablo
```

`bpm` debe ser positivo; `beat` indica el instante en pulsos desde el inicio del reloj, después de la cuenta atrás. Las manos se escriben `left` y `right`; las columnas van de `0` a `3`, de izquierda a derecha, y las filas de `0` a `2`, de arriba abajo. En el ejemplo, los instantes objetivo son los segundos 4 y 6 del reloj; los bloques se muestran con antelación. Con un patrón propio, cambiar de nivel modifica los parámetros de juego, pero mantiene las mismas notas. El JSON define objetivos temporales y no incorpora audio.

## Cómo está hecho

```text
main.py coordina la entrada, los estados y el dibujo:

webcam / ratón -> tracking.py -> calibration.py -> game.py
                                                    ^
                              rhythm.py ------------+
                              (patrones y reloj)

estado del juego -> rendering.py -> pantalla (Pygame)
partida completa -> metrics.py   -> results/*.csv
```

- **main.py**: punto de entrada, argumentos y coordinación de las pantallas de menú, calibración, partida y resultados.
- **tracking.py**: `WebcamTracker` captura con OpenCV y detecta la pose con MediaPipe (API *Tasks*, modelo `pose_landmarker_full`) en un hilo independiente. Usa las muñecas (puntos 15 y 16) y los hombros (11 y 12). Las coordenadas y la vista previa se presentan en modo espejo, con las manos desde la perspectiva del jugador. Incluye `MouseTracker` para probar sin cámara.
- **calibration.py**: calcula la zona de movimiento de cada persona, suaviza la señal y tolera pérdidas breves de detección.
- **game.py**: reglas de colisión, velocidad de golpe, puntuación y estados. No depende de una pantalla ni de una cámara y permite comprobar la lógica con posiciones sintéticas.
- **rhythm.py**: carga los patrones de bloques desde JSON, genera los de demostración y mantiene el reloj de la partida con cuenta atrás y pausa.
- **rendering.py**: pantallas e interfaz con Pygame; los bloques se identifican con letra además de color.
- **metrics.py**: calcula los indicadores y exporta los CSV.
- **config.py** reúne todos los parámetros; **models.py** los tipos de datos compartidos.

Convención de coordenadas: `x` e `y` normalizadas entre 0 y 1, origen arriba a la izquierda, imagen en modo espejo, `left` = mano izquierda del jugador, `valid` por mano y `timestamp` monotónico en segundos para los datos de seguimiento.

## Problemas habituales

- **Falta el modelo:** activa el entorno y ejecuta `python download_models.py` desde la carpeta del proyecto.
- **No se puede abrir la cámara:** comprueba los permisos del sistema y si otra aplicación la está usando. Prueba `python main.py --camera 1` u otro índice disponible. Para probar el juego sin webcam, utiliza `--tracker mouse`.
- **No se detectan bien las manos o cuesta alcanzar los bloques:** mejora la iluminación, mantén muñecas y hombros dentro del encuadre y repite la calibración con `C` desde el menú.
- **Falta alguna dependencia:** comprueba que el entorno `IPM_beat_saber` esté activo y ejecuta `python -m pip install -r requirements.txt`.

## Limitaciones y trabajo futuro

- El seguimiento utiliza una sola cámara y estima la posición de las muñecas en 2D. La amplitud corresponde a una zona conjunta de ambas manos, no a ángulos articulares ni a movilidad individual de cada hombro.
- Las partidas de demostración duran menos de un minuto. La variación de precisión y velocidad también depende del patrón, la dificultad y la detección; su interpretación como fatiga está pendiente de validación.
- El resumen no registra el modo de entrada ni una copia de la calibración. Hay que mantener condiciones comparables y separar las pruebas con ratón mediante el identificador del jugador.
- Faltan estudios con usuarios y profesionales sanitarios, referencias por edad y validación del uso sentado.
- Mejoras posibles: audio sincronizado con los patrones, informe gráfico de evolución por jugador, rejilla adaptada al uso sentado y compensación de la latencia de la cámara.

## Licencia

El código se distribuye bajo la licencia [MIT](LICENSE).
