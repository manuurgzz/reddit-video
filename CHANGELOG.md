# Registro de cambios

Todos los cambios relevantes del proyecto se documentan aquí. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Sin publicar]

### Añadido
- **Piloto automático** (`automatizar.py` y «Piloto automático…» en la app): Gemini escribe historias con tu prompt de Obsidian, la app crea los vídeos de las que apruebas (botón «✓ Aprobar para el piloto») y los publica en YouTube (programados) y TikTok (borrador), con una tarea diaria de Windows y una notificación al terminar. Guía en `docs/piloto-automatico.md`.
- `test_piloto.py`: el piloto completo sin conexión.
- Si Gemini está saturado, el piloto reintenta y pasa a otro modelo Flash (`gemini-3.6-flash`, `gemini-3.5-flash`); cada pasada, también las lanzadas desde la app, queda en `.cache/piloto.log`.
- Cortes automáticos de los shorts: si la nota no trae *Mapa de cortes*, la app parte la historia en shorts de ~2:30 que acaban en cliffhanger y deja el final para YouTube; al crear se ajustan a la duración real de la voz.
- Texto normal sin formato: «＋ Pegar historia…» en la app, archivos `.txt` y notas de `01_Historias`.
- `test_cortes.py` para comprobar los cortes.
- `requirements.txt`, `.gitattributes` y `.editorconfig`.
- Banner y README reorganizado: características, diagrama del proceso, referencia de la línea de comandos y estructura del proyecto.
- Guías en `docs/`: cortes automáticos, formato del guion y Obsidian, y configuración.
- Tests automáticos en GitHub Actions (Windows) en cada push.

### Cambiado
- «Usar gráfica NVIDIA» ya no rompe el vídeo en un PC sin NVIDIA: usa el procesador y lo avisa (en la app, la casilla aparece desactivada).
- Conectar otra carpeta de Obsidian ya no borra el resto de ajustes.
- La voz en off la genera el motor de la app Texto a Voz, ahora incluida en el repo (`Texto_Voz\`, con `texto_a_voz.bat` para abrir su web); se elimina el código propio de edge-tts y el ajuste de asyncio que dejará de existir en Python 3.16. La caché de voz se conserva.
- La app indica qué escenas van solo en YouTube cuando la tabla de cortes no las incluye en ningún short.
- Sin título en la nota, la tarjeta usa el nombre del archivo legible («La reforma de mi cunado») en vez del nombre tal cual.

## 2026-10-03 · Rediseño de la app

### Añadido
- Tema oscuro inspirado en Reddit, con la interfaz organizada en tarjetas.
- Vista previa en vivo de la tarjeta del post de Reddit.
- Ficha de voz con sorteo («🎲 Otra al azar») y botón «▶ Escuchar».
- Diseño del piloto automático en `automatizar.py` (todavía sin implementar).

## [1.1] · 2026-10-01 · Integración con Obsidian

### Añadido
- «Conectar Obsidian…»: lee las notas de `02_Clips` (o `03_Guiones`) y las abre en Obsidian.
- Marca en la nota los clips hechos y actualiza `clips_hechos` y `estado`.
- Temática de fondo por short según la tabla de clips.

## [1.0] · 2026-10-01 · Primera versión

### Añadido
- Conversión de guion Markdown a vídeo de YouTube (16:9) con `.srt` y shorts verticales (9:16).
- Voz en off con edge-tts, subtítulos palabra a palabra y tarjeta inicial del post de Reddit.
- Fondos por temática, música opcional y codificación con NVIDIA NVENC.

[Sin publicar]: https://github.com/manuurgzz/reddit-video/compare/v1.1...HEAD
[1.1]: https://github.com/manuurgzz/reddit-video/compare/v1.0...v1.1
[1.0]: https://github.com/manuurgzz/reddit-video/releases/tag/v1.0
