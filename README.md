# Reddit Video · guion → vídeos de historias de Reddit

App para Windows que convierte un guion de texto (`.md`) en:
- **YouTube (16:9)**: vídeo completo con todas las escenas, más un `.srt` para subir como subtítulos.
- **TikTok / Reels / Shorts (9:16)**: un short por cada fila del "Mapa de cortes" (en pantalla no pone "Parte X").

Voz en off automática (gratis, con edge-tts), subtítulos palabra a palabra, tarjeta de post de Reddit al principio y fondos "satisfying" o de gameplay. Los vídeos salen en `salida\<nombre del guion>\`.

## Instalación (una sola vez)

1. Descarga el proyecto: botón verde **Code → Download ZIP** (o la última versión en **Releases**) y descomprímelo donde quieras.
2. Doble clic en **`INSTALAR_Y_CREAR.bat`**. Instala lo que falte (Python, edge-tts y ffmpeg) y abre la app.
3. **Fondos**: la primera vez se crean las carpetas `fondos\JABON`, `SLIME`, `ARENA`, `PINTURA`, `PRENSA`, `RUNNER`, `PARKOUR` y `CERA`.
   Mete en cada una algún clip de Pexels o Pixabay (gratis). Busca "soap cutting", "slime", "kinetic sand", "paint pouring", "hydraulic press", "wax cutting"...
   - Vale en vertical u horizontal: en los shorts se recorta y en YouTube se pone sobre un fondo desenfocado.
   - Si una carpeta está vacía, se usa otra que tenga clips.
   - Si un vídeo dura más de 15 minutos, se usa ese mismo para toda su temática, cogiendo trozos seguidos para no repetir.
   - Gameplay (`RUNNER`, `PARKOUR`): usa solo vídeo que tengas derecho a usar.
4. **Música (opcional)**: mete mp3 en `musica\` (p. ej. de la YouTube Audio Library o Pixabay Music).
5. **Historias**: pulsa **🔗 Conectar Obsidian…** y elige tu bóveda; la app lee las notas de `02_Clips` (o `03_Guiones`). Sin Obsidian, pon los guiones en `guiones\` (hay uno de ejemplo) o elige cualquier carpeta con el mismo botón.

Las veces siguientes basta con **`crear_video.bat`**.

## Uso

**Doble clic en `crear_video.bat`** y se abre la app:

1. **Historia**: elige la nota (la más reciente primero; al lado sale su estado de Obsidian: pendiente, en-produccion, hecha…). «📖 Abrir nota» la abre en Obsidian. Avisa si faltan clips en alguna carpeta de fondos.
2. **Post de Reddit**: la tarjeta del principio imita un post real (r/subreddit, u/usuario, título). El subreddit sale de la ficha de la historia; el usuario se inventa al azar (🎲 para otro). Todo se puede editar.
3. **Voz**: cada proyecto nuevo coge una voz al azar (a veces hombre, a veces mujer, distintos acentos) y la recuerda para ese proyecto. «🎲 Otra al azar» para cambiarla y «▶ Escuchar» para oírla.
4. **Qué crear**: YouTube, Shorts o los dos; música; prueba rápida; gráfica NVIDIA.
5. **Crear vídeos**: al terminar se abre la carpeta con los vídeos.

La voz, el subreddit y el usuario de cada proyecto se guardan en `.cache\proyectos.json`.

Desde la terminal también funciona:

```
python guion_a_video.py --analizar          # comprueba qué ha entendido (escenas, fondos, claves, cortes)
python guion_a_video.py                     # todo: YouTube + cortes
python guion_a_video.py --rapido            # prueba rápida a media resolución
python guion_a_video.py --solo cortes       # solo TikTok (o: youtube, parte1, parte2, parte3)
python guion_a_video.py "C:\...\otro_guion.md"
python guion_a_video.py --gpu               # si tienes gráfica NVIDIA: mucho más rápido
python guion_a_video.py --velocidad "+10%" --voz es-ES-ElviraNeural   # fuerza una voz
python guion_a_video.py --sin-musica
python guion_a_video.py --semilla 1234      # repite exactamente los mismos fondos
```

La voz se guarda en caché (`.cache\tts`): si solo cambias fondos o música, no vuelve a generarla. Si cambias una frase del guion, solo regenera esa línea.

## Obsidian

- **Conectar**: «🔗 Conectar Obsidian…» guarda la bóveda en `ajustes.json` (solo en tu PC).
- **Marcar clips hechos**: al crear vídeos (salvo en «Prueba rápida»), la app marca `- [x]` en el checklist de la nota los shorts (`Parte N/T`) y el vídeo de YouTube creados, y actualiza `clips_hechos` y `estado` (`en-produccion` o `hecha`).
- **Formato de las notas de clips** (`02_Clips`): bloques con `[ESCENA N · FONDO: JABON]`, notas como `[Palabras en amarillo: a, b]` o `[Efecto: zoom en "frase"]` y el texto narrado debajo. Cada escena se lee una vez aunque aparezca en varios clips. La tabla de clips (`Parte 1/3 | JABÓN | 1 → 4 | …`) decide qué escenas y qué temática de fondo lleva cada short.

## Qué lee del guion clásico

| En el guion | En el vídeo |
|---|---|
| `### ESCENA N · Título (tiempo)` | Escenas: marcan la temática de fondo y los cortes |
| Líneas de `**Narración:**` | Voz + subtítulos de 2 a 4 palabras, sincronizados palabra a palabra |
| `**frase en negrita**` | Subtítulo con zoom |
| `[JABÓN]`, `[SLIME]`… en `**Fondo / edición:**` | Carpeta de fondos (la primera etiqueta que aparezca) |
| `…en amarillo: "distante", "boca abajo"` | Esas palabras salen en amarillo |
| La frase «con el título» seguida del título entre comillas | Título del post de Reddit del principio, en YouTube y en los shorts (en YouTube, además, la voz lo lee) |
| Tabla del "Mapa de cortes" | Shorts 9:16 (solo se usan las escenas de cada fila) |

Añadidos automáticos: "Continúa en mi perfil" al final de los shorts intermedios, pantalla "El FINAL en YouTube (link en bio)" (con voz) al final del último short y "¡COMENTA!" en los últimos segundos del vídeo de YouTube.

**No hace (todavía):** las notas de edición finas del guion, como congelar la imagen 0,5 s, sincronizar el aplastamiento de la prensa con una frase o la pantalla partida.

## Ajustes

Todo está en el bloque `CONFIGURACIÓN`, arriba de `guion_a_video.py`: lista de voces que entran en el sorteo (`VOCES`), velocidad, pausas, tamaño de los subtítulos, palabras por golpe, volumen de la música, textos finales, calidad (CRF), etc.

El fondo cambia de clip cada 30 s en los shorts (siempre de la misma temática) y cada 60 s en YouTube: `DURACION_FONDO_VERTICAL` y `DURACION_FONDO_HORIZONTAL`.

## Requisitos

Windows 10/11 y conexión a internet (la voz se genera online con edge-tts).
