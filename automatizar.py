#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
automatizar.py — PILOTO AUTOMÁTICO · DISEÑO, SIN IMPLEMENTAR

Este archivo todavía no hace nada: es el plano para automatizar el proceso entero más adelante.
Ni la app ni guion_a_video.py lo importan. El boceto de código de abajo está comentado a propósito.

══════════════════════════════════════════════════════════════════════════════════════════════
 OBJETIVO
══════════════════════════════════════════════════════════════════════════════════════════════
De «hay una historia buena en Reddit» a «vídeos subidos y nota marcada como publicada» sin abrir
la app. Por defecto sigues revisando tú cada guion antes de que se renderice.

  HOY (a mano)                                   CON PILOTO AUTOMÁTICO
  1. Buscar la historia en Reddit             →  E1 Captar      API de Reddit, filtros, sin repetir (id_reddit)
  2. Escribir ficha y nota de clips           →  E2 Guionizar   Claude escribe la nota en formato 02_Clips
  3. Revisar la nota                          →  E3 Aprobar     cambias «estado: pendiente» a «aprobada»
  4. Abrir la app y pulsar «Crear vídeos»     →  E4 Renderizar  gv.main(...), que ya existe y marca el checklist
  5. Subir a YouTube / TikTok / Reels         →  E5 Publicar    APIs oficiales, programado y escalonado
  6. Marcar la nota como publicada            →  E6 Registrar   estado, enlaces y errores en la propia nota

══════════════════════════════════════════════════════════════════════════════════════════════
 PRINCIPIOS
══════════════════════════════════════════════════════════════════════════════════════════════
  · Obsidian es la única fuente de verdad: la cola son las notas y el estado vive en su frontmatter.
    Sin base de datos. Si algo se corta a medias, la siguiente pasada sigue donde se quedó.
  · Cada pasada avanza cada nota como mucho un paso y respeta límites (historias/día, cupo de YouTube).
  · Lo lanza el Programador de tareas de Windows: una pasada y termina. Nada de procesos siempre vivos.
  · Reutiliza el motor tal cual: parsear_guion, datos_proyecto, main, marcar_en_obsidian, estado_nota.
  · Claves y tokens en secretos.json (añadirlo a .gitignore) o en variables de entorno, nunca en ajustes.json.
  · El piloto solo toca notas que ha creado él (frontmatter «origen: auto»): tus notas a mano no se
    renderizan solas aunque estén en «pendiente».

══════════════════════════════════════════════════════════════════════════════════════════════
 ESTADOS DE UNA NOTA (campo «estado:»)
══════════════════════════════════════════════════════════════════════════════════════════════
     nueva ─E2─▶ pendiente ─(tú)─▶ aprobada ─E4─▶ en-produccion / hecha ─E5─▶ programada ─▶ publicada
                    │
                    └─(tú)─▶ descartada              cualquier paso que falle ─▶ error  (+ «error: <motivo>»)

  Ya existen: pendiente, en-produccion, hecha, publicada, descartada.  Nuevos: nueva, aprobada, programada, error.
  Ojo: marcar_en_obsidian() respeta «publicada» y «descartada»; habría que añadir «programada» a esa lista.

══════════════════════════════════════════════════════════════════════════════════════════════
 AJUSTES (bloque «auto» dentro de ajustes.json)
══════════════════════════════════════════════════════════════════════════════════════════════
    "auto": {
      "activo": false,
      "hora": "09:00",                            pasada diaria
      "subreddits": ["AITAH", "pettyrevenge", "relationship_advice"],
      "min_votos": 2000, "min_palabras": 600,
      "max_historias_dia": 2,
      "revision_humana": true,                    false = renderiza sin esperar a «aprobada»
      "gpu": true,
      "publicar": {"youtube": false, "tiktok": false, "reels": false},
      "horario_publicacion": ["18:00"]            un short por día y franja; el vídeo largo, el primero
    }

══════════════════════════════════════════════════════════════════════════════════════════════
 ETAPAS
══════════════════════════════════════════════════════════════════════════════════════════════
  E1 · Captar
    · API oficial de Reddit (app tipo «script» con OAuth): /r/<sub>/top?t=day.
      Filtrar por votos, longitud, NSFW y posts «UPDATE» (enlazarlos con su historia original).
    · Saltar los ya vistos buscando «id_reddit: <id>» en la bóveda (las notas ya lo llevan).
    · Guardar la ficha en la carpeta de historias, la que enlaza «historia: [[…]]»: de ahí sale el r/ del post.
    · Revisar los términos de la API de Reddit y anonimizar nombres propios.
  E2 · Guionizar (Claude)
    · Una llamada por historia. En el system: la plantilla de la nota de clips y una nota real de ejemplo.
      Es siempre igual, así que se cachea. La respuesta es la nota en Markdown, tal cual.
    · Validar con gv.parsear_guion(): escenas con narración, tabla «Parte X/Y», fondos dentro de ETIQUETAS
      y checklist «- [ ]». Si falla, un reintento pasándole el error; si vuelve a fallar → estado: error.
    · Guardar en 02_Clips con «estado: pendiente» (o «aprobada» si revision_humana es false) y «origen: auto».
  E3 · Aprobar (tú)
    · Lees y retocas la nota en Obsidian y cambias el estado a «aprobada», o a «descartada».
  E4 · Renderizar
    · gv.main([nota, "--solo", "todo"] + ["--gpu"]): ya marca el checklist, clips_hechos y el estado.
    · Antes, avisar si faltan clips de fondo (gv.clips_de) para no gastar una pasada en fondos lisos.
  E5 · Publicar
    · YouTube Data API v3: videos.insert en privado con publishAt (queda programado) y captions.insert con el .srt.
      El cupo por defecto es de 10.000 unidades al día y cada subida gasta ~1.600: unas 6 subidas al día.
    · TikTok (Content Posting API) solo publica en privado hasta que auditen la app; Reels va por la Graph API
      de Instagram. Mientras no estén: la nota se queda en «hecha» con «listo para subir» y los vídeos en salida/<slug>/.
    · Título y descripción: sección «### YouTube» de la nota (parsear_guion ya saca de ahí el título).
    · Escalonar: el vídeo largo y la Parte 1 el primer día, la Parte 2 al siguiente… en horario_publicacion.
    · Marcar el contenido como sintético/alterado cuando la plataforma lo pida.
  E6 · Registrar
    · En la nota: estado, «publicado_youtube: <url>», «error: …».
    · Resumen de cada pasada en 00_Registro.md y notificación de Windows al terminar («2 vídeos listos · 1 error»).

══════════════════════════════════════════════════════════════════════════════════════════════
 CAMBIOS QUE HARÁN FALTA FUERA DE ESTE ARCHIVO
══════════════════════════════════════════════════════════════════════════════════════════════
  · guion_a_video.py: poner_campo(ruta, clave, valor) para escribir cualquier campo del frontmatter
    (hoy solo se reescriben estado y clips_hechos, con regex, en marcar_en_obsidian).
  · guion_a_video.py: que main() devuelva los vídeos creados (ahora solo salen en el log).
  · app.pyw: interruptor «Piloto automático» en la barra de acción (boceto comentado allí) y línea con la cola.
  · Dependencias nuevas, solo cuando se implemente: anthropic, praw (o peticiones a mano a la API de Reddit),
    google-api-python-client + google-auth-oauthlib para YouTube.
"""

# ──────────────────────────────────────────────────────────────────────────
#  Boceto (comentado: NO se ejecuta)
# ──────────────────────────────────────────────────────────────────────────
#
# import argparse
# import json
# import subprocess
# from pathlib import Path
#
# import guion_a_video as gv
#
# CANDADO = gv.CARPETA_CACHE / "auto.lock"   # evita dos pasadas a la vez
# SECRETOS = gv.BASE / "secretos.json"       # claves y tokens, fuera de Git
# TAREA = "RedditVideo · Piloto automático"
#
#
# def ajustes():
#     por_defecto = {"activo": False, "hora": "09:00", "subreddits": ["AITAH"], "min_votos": 2000,
#                    "min_palabras": 600, "max_historias_dia": 2, "revision_humana": True, "gpu": False,
#                    "publicar": {"youtube": False, "tiktok": False, "reels": False}, "horario_publicacion": ["18:00"]}
#     return {**por_defecto, **gv.leer_ajustes().get("auto", {})}
#
#
# def notas(estado):
#     """Notas del piloto (origen: auto) en ese estado, de la más antigua a la más nueva."""
#     ...
#
#
# # ── E1 · Captar ───────────────────────────────────────────────────────────
# def historias_nuevas(cfg) -> list:
#     """[{id, subreddit, titulo, texto, votos, url}] que pasan los filtros y no están ya en la bóveda."""
#     ...
#
#
# def guardar_ficha(historia) -> Path:
#     ...
#
#
# # ── E2 · Guionizar ────────────────────────────────────────────────────────
# PLANTILLA_NOTA = "..."   # formato 02_Clips + una nota real de ejemplo (texto fijo → se cachea)
#
#
# def escribir_nota(ficha: Path, cfg) -> Path:
#     import anthropic
#     cliente = anthropic.Anthropic()                 # ANTHROPIC_API_KEY o `ant auth login`
#     with cliente.beta.messages.stream(
#         model="claude-opus-5-5",
#         max_tokens=64000,
#         output_config={"effort": "high"},
#         betas=["server-side-fallback-2026-07-01"],
#         fallbacks="default",                        # si este modelo se niega, la API reintenta con otro
#         cache_control={"type": "ephemeral"},
#         system=PLANTILLA_NOTA,
#         messages=[{"role": "user", "content": ficha.read_text(encoding="utf-8")}],
#     ) as s:
#         msg = s.get_final_message()
#     if msg.stop_reason != "end_turn":              # "refusal" o "max_tokens" → estado: error
#         ...
#     texto = "".join(b.text for b in msg.content if b.type == "text")
#     ruta = ...                                      # 02_Clips/<fecha>_<slug>_clips.md, con origen: auto
#     ruta.write_text(texto, encoding="utf-8")
#     g = gv.parsear_guion(ruta)
#     if not g.escenas or not g.cortes:               # un reintento pasándole el fallo; luego, error
#         ...
#     return ruta
#
#
# # ── E4 · Renderizar ───────────────────────────────────────────────────────
# def renderizar(nota: Path, cfg):
#     gv.main([str(nota), "--solo", "todo"] + ["--gpu"] * cfg["gpu"])   # marca checklist y estado
#
#
# # ── E5 · Publicar ─────────────────────────────────────────────────────────
# def publicar(nota: Path, cfg):
#     """Sube y programa lo que esté activado en cfg["publicar"]; si nada lo está, deja «listo para subir»."""
#     ...
#
#
# # ── Una pasada completa ───────────────────────────────────────────────────
# def pasada(cfg):
#     for h in historias_nuevas(cfg)[: cfg["max_historias_dia"]]:
#         escribir_nota(guardar_ficha(h), cfg)
#     for nota in notas("aprobada") + ([] if cfg["revision_humana"] else notas("pendiente")):
#         try:
#             renderizar(nota, cfg)
#         except Exception as e:
#             gv.poner_campo(nota, "estado", "error")
#             gv.poner_campo(nota, "error", str(e))
#     for nota in notas("hecha"):
#         publicar(nota, cfg)
#
#
# def programar(activo, hora="09:00"):
#     """Da de alta (o de baja) la tarea de Windows que lanza una pasada al día. La usaría el interruptor de la app."""
#     if activo:
#         subprocess.run(["schtasks", "/create", "/f", "/tn", TAREA, "/sc", "daily", "/st", hora,
#                         "/tr", f'pythonw "{Path(__file__).resolve()}" --una-vez'], check=True)
#     else:
#         subprocess.run(["schtasks", "/delete", "/f", "/tn", TAREA], check=True)
#
#
# def main(argv=None):
#     ap = argparse.ArgumentParser(description="Piloto automático: de Reddit a vídeo publicado")
#     ap.add_argument("--una-vez", action="store_true", help="hace una pasada y termina (lo que lanza la tarea)")
#     ap.add_argument("--simular", action="store_true", help="enseña qué haría, sin tocar nada")
#     ap.add_argument("--programar", action="store_true")
#     ap.add_argument("--desprogramar", action="store_true")
#     ...  # con el CANDADO cogido: pasada(ajustes())
#
#
# if __name__ == "__main__":
#     main()
