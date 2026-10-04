# Configuración

[← Volver al README](../README.md)

Todos los ajustes del motor están en el bloque `CONFIGURACIÓN`, al principio de [`guion_a_video.py`](../guion_a_video.py). Los del piloto automático se cambian desde la app, en **Piloto automático…** (ver la [guía del piloto](piloto-automatico.md)).

| Ajuste | Para qué sirve |
|---|---|
| `CARPETA_TEXTO_VOZ` | Dónde está la app Texto a Voz, que genera la voz (por defecto, `Texto_Voz\` dentro del proyecto). |
| `VOCES`, `VELOCIDAD`, `TONO` | Voces que entran en el sorteo y cómo suenan. |
| `PAUSA_*` | Pausas entre líneas y escenas. |
| `FUENTE_SUBS`, `PALABRAS_MAX`, `COLOR_CLAVE` | Aspecto de los subtítulos. |
| `DURACION_FONDO_VERTICAL` / `_HORIZONTAL` | Cada cuánto cambia el clip de fondo (30 s en shorts, 60 s en YouTube). |
| `VOLUMEN_MUSICA` | Volumen de la música (se atenúa sola cuando habla la voz). |
| `TEXTO_FINAL_CORTE`, `TEXTO_SIGUIENTE` | Textos de cierre de los shorts. |
| `CORTE_OBJETIVO`, `CORTE_MIN`, `CORTE_MAX` | Duración de los shorts automáticos (150, 61 y 170 s de voz). |
| `FINAL_SOLO_YOUTUBE` | Parte final que no sale en los shorts (`0.2`); con `0`, los shorts cuentan la historia entera. |
| `CRF`, `PRESET`, `FPS` | Calidad y velocidad de codificación. |

## Archivos locales

Estos archivos se crean en tu PC y no se suben a Git:

| Archivo | Contenido |
|---|---|
| `ajustes.json` | Carpeta de Obsidian o de guiones elegida y ajustes del piloto. |
| `secretos.json` | Claves de Gemini, YouTube y TikTok. |
| `.cache\proyectos.json` | Voz, subreddit y usuario de cada proyecto. |
| `.cache\tts\` | Caché de voz: si solo cambias fondos o música, no se vuelve a generar, y si cambias una frase, solo se regenera esa línea. |
| `.cache\piloto.log` | Detalle de cada pasada del piloto. |
