# Registro de cambios

Todos los cambios relevantes del proyecto se documentan aquí. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Sin publicar]

### Añadido
- Cortes automáticos de los shorts: si la nota no trae *Mapa de cortes*, la app parte la historia en shorts de ~2:30 que acaban en cliffhanger y deja el final para YouTube; al crear se ajustan a la duración real de la voz.
- Texto normal sin formato: «＋ Pegar historia…» en la app, archivos `.txt` y notas de `01_Historias`.
- `test_cortes.py` para comprobar los cortes.
- `requirements.txt`, `.gitattributes` y `.editorconfig`.
- Banner y README reorganizado: características, diagrama del proceso, referencia de la línea de comandos y estructura del proyecto.

### Cambiado
- La app indica qué escenas van solo en YouTube cuando la tabla de cortes no las incluye en ningún short.
- Sin título en la nota, la tarjeta usa el nombre del archivo legible («La reforma de mi cunado») en vez del nombre tal cual.

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
