# Registro de cambios

Todos los cambios relevantes del proyecto se documentan aquí. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [1.0.1] · Escribir historias desde la ventana

### Añadido
- Botón **✦ Escribir con IA** en la tarjeta Historia: Gemini escribe una historia nueva al momento, sin entrar en «Piloto automático», y se carga para revisarla. Si falta la clave de Gemini, ofrece ponerla.

### Corregido
- Al crear los vídeos de una nota sin checklist (pegada en la app o escrita por el piloto), el estado pasa de «aprobada» a «hecha» (o «en-produccion» si solo se creó un formato).

## [1.0.0] · Instalador y app rediseñada

### Añadido
- **Instalador `.exe`** (`construir.ps1`, `RedditVideo.spec`, `instalador.iss`): lleva dentro la app, la voz y FFmpeg; se instala sin permisos de administrador, con icono en el escritorio y el menú Inicio y desinstalador. GitHub Actions lo construye y lo adjunta a la Release al subir una etiqueta `v*`.
- Icono propio de la app (`assets/`, `herramientas/crear_icono.py`).
- Botón **Cancelar** durante la creación o el piloto: corta ffmpeg al momento y no deja vídeos a medias. Cerrar la ventana con un trabajo en marcha pregunta antes y no deja ffmpeg huérfano.
- `--crear` en la línea de comandos de la app (vídeos sin ventana) y `test_robustez.py`.
- Datos separados de la app instalada: tus fondos, música, historias y vídeos en `Documentos\Reddit Video`; ajustes, claves y caché en `%LOCALAPPDATA%\Reddit Video`.
- **Piloto automático** (`automatizar.py` y «Piloto automático…» en la app): Gemini escribe historias con tu prompt de Obsidian, la app crea los vídeos de las que apruebas (botón «✓ Aprobar para el piloto») y los publica en YouTube (programados) y TikTok (borrador), con una tarea diaria de Windows y una notificación al terminar. Guía en `docs/piloto-automatico.md`.
- `test_piloto.py`: el piloto completo sin conexión.
- Si Gemini está saturado, el piloto reintenta y pasa a otro modelo Flash (`gemini-3.6-flash`, `gemini-3.5-flash`); cada pasada, también las lanzadas desde la app, queda en `.cache/piloto.log`.
- Cortes automáticos de los shorts: si la nota no trae *Mapa de cortes*, la app parte la historia en shorts de ~2:30 que acaban en cliffhanger y deja el final para YouTube; al crear se ajustan a la duración real de la voz.
- Texto normal sin formato: «＋ Pegar historia…» en la app, archivos `.txt` y notas de `01_Historias`.
- `test_cortes.py` para comprobar los cortes.
- `requirements.txt`, `.gitattributes` y `.editorconfig`.
- Banner y README reorganizado: características, diagrama del proceso, referencia de la línea de comandos y estructura del proyecto.

### Cambiado
- **Interfaz rediseñada**: dos columnas (historia y post a la izquierda, voz y salida a la derecha), tarjetas planas, botones en píldora, un único acento naranja, registro plegado en «Mostrar detalles», menú «Carpetas» y ajustes del piloto en pestañas.
- La voz exige `edge-tts>=7.3.1`: Microsoft cambió su servicio y las versiones anteriores dan 403; ahora el error lo explica.
- La tarea diaria del piloto, en la versión instalada, lanza el propio `.exe` con `--una-vez`.
- «Usar gráfica NVIDIA» ya no rompe el vídeo en un PC sin NVIDIA: usa el procesador y lo avisa (en la app, la casilla aparece desactivada).
- Conectar otra carpeta de Obsidian ya no borra el resto de ajustes.
- Piloto sin publicación activada: una historia con sus vídeos ya hechos deja de contar como «en marcha» (antes bloqueaba para siempre la escritura de historias nuevas).
- La voz en off la genera el motor de la app Texto a Voz, ahora incluida en el repo (`Texto_Voz\`, con `texto_a_voz.bat` para abrir su web); se elimina el código propio de edge-tts y el ajuste de asyncio que dejará de existir en Python 3.16. La caché de voz se conserva.
- La app indica qué escenas van solo en YouTube cuando la tabla de cortes no las incluye en ningún short.
- Sin título en la nota, la tarjeta usa el nombre del archivo legible («La reforma de mi cunado») en vez del nombre tal cual.

### Corregido
- Cuelgues y saturación: ffmpeg y ffprobe con tiempo límite (ffmpeg parado 2 min se corta), voz con 90 s de plazo, peticiones de red de 60 s en vez de 15 min, inicio de sesión con el puerto ocupado, `powershell` de la tarea programada con plazo, y la ventana pinta por tandas con el registro acotado en vez de congelarse con muchos mensajes.
- Pérdida de datos: `ajustes.json`, `secretos.json`, `proyectos.json`, la caché de voz, el Registro y las notas de Obsidian se escriben enteros o nada (antes, un corte a mitad de escritura los dejaba vacíos); caché de voz dañada o `.wav` cortado se regeneran en vez de fallar siempre; el registro del piloto rota a los 2 MB.
- Errores que dejaban la ventana bloqueada con el botón desactivado (excepción dentro del bucle de mensajes, voz de muestra sin respuesta, doble pulsación), y `print` fallando en la app sin consola.

## 2026-10-03 · Rediseño de la app

### Añadido
- Tema oscuro inspirado en Reddit, con la interfaz organizada en tarjetas.
- Vista previa en vivo de la tarjeta del post de Reddit.
- Ficha de voz con sorteo («🎲 Otra al azar») y botón «▶ Escuchar».
- Diseño del piloto automático en `automatizar.py` (todavía sin implementar).

## 2026-10-01 · Integración con Obsidian

### Añadido
- «Conectar Obsidian…»: lee las notas de `02_Clips` (o `03_Guiones`) y las abre en Obsidian.
- Marca en la nota los clips hechos y actualiza `clips_hechos` y `estado`.
- Temática de fondo por short según la tabla de clips.

## 2026-10-01 · Primera versión

### Añadido
- Conversión de guion Markdown a vídeo de YouTube (16:9) con `.srt` y shorts verticales (9:16).
- Voz en off con edge-tts, subtítulos palabra a palabra y tarjeta inicial del post de Reddit.
- Fondos por temática, música opcional y codificación con NVIDIA NVENC.
