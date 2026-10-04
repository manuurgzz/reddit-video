#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
automatizar.py — PILOTO AUTOMÁTICO: Gemini escribe la historia, la app crea los vídeos y los publica.

Cada pasada (una al día con el Programador de tareas de Windows, o «Hacer una pasada ahora» en la app):
  1 · Escribir   Si hay menos historias en marcha que «cola», Gemini escribe una nueva siguiendo tu
                 00_Sistema/Prompt-historias-propias.md y la guarda como nota en la carpeta de guiones.
  2 · Aprobar    Tú la lees y pulsas «✓ Aprobar» en la app (o pones «estado: aprobada» en Obsidian).
                 Sin «revision_humana», nace ya aprobada.
  3 · Crear      La nota aprobada más antigua → vídeo de YouTube y shorts (una nota por pasada).
  4 · Publicar   Un short por cada hora de «horas_publicacion»: en YouTube queda programado; en TikTok llega
                 como borrador (te avisa el móvil y lo publicas con un toque). El vídeo largo sale con el primer
                 short y su enlace va en la descripción de los demás.

Estados de la nota: pendiente → aprobada → lista → programada → publicada  (o error, con el motivo en «error:»).
El estado vive en el frontmatter de cada nota y, si existe, en 00_Sistema/Registro.md.
Claves y permisos: secretos.json (no se sube a Git). Ajustes: bloque «auto» de ajustes.json (los cambia la app).

Uso:
    python automatizar.py --una-vez                    una pasada (lo que lanza la tarea programada)
    python automatizar.py --programar 09:00            una pasada al día a esa hora  (--desprogramar la quita)
    python automatizar.py --conectar-youtube cliente.json
    python automatizar.py --conectar-tiktok
"""
import argparse
import base64
import hashlib
import json
import msvcrt
import os
import re
import secrets as azar
import subprocess
import sys
import time
import traceback
import webbrowser
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

import guion_a_video as gv

SECRETOS = gv.BASE / "secretos.json"
REGISTRO_PASADAS = gv.CARPETA_CACHE / "piloto.log"
ESTADO = gv.CARPETA_CACHE / "piloto.json"
CANDADO = gv.CARPETA_CACHE / "piloto.lock"
TAREA = "Reddit Video - Piloto automatico"

POR_DEFECTO = {
    "activo": False,
    "hora": "09:00",                    # pasada diaria
    "modelo": "gemini-3.8-flash",       # el Flash gratuito; con facturación, "gemini-3.1-pro-preview" escribe mejor
    "cola": 2,                          # historias en marcha (sin publicar del todo) antes de pedir otra
    "revision_humana": True,            # False = crea y publica sin esperar a que la apruebes
    "gpu": False,
    "youtube": False,
    "tiktok": False,
    "horas_publicacion": ["14:00", "20:00"],   # un short en cada hora
    "sintetico": True,                  # declara a YouTube que hay contenido generado con IA (historia y voz)
}
EN_MARCHA = ("pendiente", "aprobada", "lista", "programada")
MODELOS_RESPALDO = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash"]  # si el elegido está saturado (503)


def ajustes():
    return {**POR_DEFECTO, **gv.leer_ajustes().get("auto", {})}


def guardar_ajustes(cfg):
    gv.guardar_ajustes(auto=cfg)


def secretos():
    try:
        return json.loads(SECRETOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guardar_secretos(**cambios):
    SECRETOS.write_text(json.dumps({**secretos(), **cambios}, ensure_ascii=False, indent=1), encoding="utf-8")


def boveda():
    b = gv.leer_ajustes().get("boveda")
    return Path(b) if b else None


def pedir(url, datos=None, cabeceras=None, metodo=None, formulario=False):
    """Petición HTTPS. `datos`: dict (JSON o formulario), bytes o un archivo abierto. Devuelve (JSON, cabeceras)."""
    cab = dict(cabeceras or {})
    if isinstance(datos, dict):
        if formulario:
            datos, cab["Content-Type"] = urlencode(datos).encode(), "application/x-www-form-urlencoded"
        else:
            datos = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            cab.setdefault("Content-Type", "application/json; charset=UTF-8")
    try:
        with urlopen(Request(url, data=datos, headers=cab, method=metodo), timeout=900) as r:
            cuerpo = r.read()
            try:
                return json.loads(cuerpo), r.headers
            except ValueError:
                return {}, r.headers
    except HTTPError as e:
        cuerpo = e.read().decode("utf-8", "replace")
        try:  # Google y TikTok: {"error": {"message": …}}; OAuth: {"error": "invalid_grant", "error_description": …}
            d = json.loads(cuerpo)
            err = d.get("error")
            cuerpo = (err.get("message") if isinstance(err, dict) else f"{err}: {d.get('error_description', '')}") or cuerpo
        except (ValueError, AttributeError):
            pass
        raise RuntimeError(f"{e.code} de {urlparse(url).netloc}: {cuerpo[:300]}") from None


# ──────────────────────────────────────────────────────────────────────────
#  1 · Escribir: Gemini
# ──────────────────────────────────────────────────────────────────────────

PROMPT_DE_SERIE = """# ROL
Eres un guionista experto en historias narradas estilo Reddit (r/AITAH, r/ProRevenge, r/TrueOffMyChest,
r/MaliciousCompliance, r/LetsNotMeet) para vídeos de YouTube con voz en off. Tu única métrica es la RETENCIÓN.

# ESTRUCTURA
8 partes de 600-700 palabras (4.800-5.600 en total): gancho in media res, primera grieta, escalada, giro central,
contraataque, momento más oscuro, clímax y desenlace con una pregunta moral para los comentarios.
Cliffhanger fuerte al final de cada parte y micro-cliffhanger cada 150-200 palabras. Planta detalles y págalos.

# ESTILO
Primera persona, tono confesional de post de Reddit, español natural, frases cortas, una idea por línea.
Números y siglas escritos como se pronuncian. Nada de acotaciones, emojis ni texto que no se lea en voz alta.

# LÍMITES
100 % ficción (nada de personas, marcas o casos reales), sin menores en riesgo, sin violencia gráfica ni sexo explícito.

# FORMATO DE CADA PARTE
PARTE X/8 · [título corto]
[texto narrado]"""

MODO_AUTOMATICO = """

# MODO AUTOMÁTICO (manda sobre lo anterior)
Trabajas sin nadie al otro lado: no propongas opciones ni esperes respuesta; en cada fase decides tú.
Cuando te pida partes de la historia, devuelve SOLO el texto narrado con su encabezado «PARTE X/8 · título»:
sin recuentos de palabras, notas, acotaciones ni comentarios antes o después."""

PLAN = {"type": "OBJECT", "properties": {
    "titulo": {"type": "STRING", "description": "título del post de Reddit, en primera persona"},
    "subreddit": {"type": "STRING", "description": "subreddit cuyo estilo imita, p. ej. r/ProRevenge"},
    "categoria": {"type": "STRING", "description": "venganza, drama-familiar, pareja, trabajo, vecinos, misterio u otro"},
    "resumen": {"type": "STRING", "description": "máximo 3 líneas"},
    "gancho": {"type": "STRING", "description": "la frase con la que arranca la historia"},
    "escaleta": {"type": "ARRAY", "items": {"type": "STRING"},
                 "description": "las 8 partes: qué pasa, qué pregunta queda abierta y dónde van los giros"},
    "youtube_titulo": {"type": "STRING"},
    "descripcion": {"type": "STRING", "description": "2 líneas; incluye «Historia de ficción inspirada en el estilo de Reddit»"},
    "hashtags": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "6 hashtags"},
    "pregunta": {"type": "STRING", "description": "pregunta final para los comentarios"},
}}
PLAN["required"] = list(PLAN["properties"])


def gemini(cfg, sistema, turnos, esquema=None):
    """Respuesta de Gemini a la conversación `turnos` (usuario, modelo, usuario…). Con `esquema`, ya leída como JSON."""
    clave = secretos().get("gemini") or os.environ.get("GEMINI_API_KEY")
    if not clave:
        raise RuntimeError("falta la clave de Gemini: ponla en «Piloto automático…» de la app")
    config = {"maxOutputTokens": 32768}
    if esquema:
        config |= {"responseMimeType": "application/json", "responseSchema": esquema}
    cuerpo = {"systemInstruction": {"parts": [{"text": sistema}]}, "generationConfig": config,
              "contents": [{"role": "model" if i % 2 else "user", "parts": [{"text": t}]} for i, t in enumerate(turnos)]}
    modelos = [cfg["modelo"]] + [m for m in MODELOS_RESPALDO if m != cfg["modelo"]]
    for modelo, intento in ((m, i) for m in modelos for i in range(3)):
        try:
            r, _ = pedir(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
                         cuerpo, {"x-goog-api-key": clave})
            break
        except RuntimeError as e:  # 429 (límite por minuto) o 5xx (saturado): esperar, reintentar y, si sigue, otro modelo
            if not re.match(r"(429|5\d\d) ", str(e)) or (modelo, intento) == (modelos[-1], 2):
                raise
            if intento == 2:
                gv.log(f"   {modelo} sigue saturado: pruebo con {modelos[modelos.index(modelo) + 1]}")
            else:
                time.sleep(20 * (intento + 1))
    cand = (r.get("candidates") or [{}])[0]
    texto = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []) if not p.get("thought"))
    if cand.get("finishReason") != "STOP" or not texto.strip():
        raise RuntimeError(f"Gemini no terminó la respuesta ({cand.get('finishReason') or r.get('promptFeedback')})")
    return json.loads(texto) if esquema else texto.strip()


def prompt_historias():
    """El bloque de 00_Sistema/Prompt-historias-propias.md (lo editas en Obsidian); si no está, uno de serie."""
    p = boveda() / "00_Sistema" / "Prompt-historias-propias.md" if boveda() else None
    m = p and p.exists() and re.search(r"```text\n(.*?)```", p.read_text(encoding="utf-8"), re.S)
    return m.group(1).strip() if m else PROMPT_DE_SERIE


def notas_existentes():
    raiz = boveda() or gv.CARPETA_GUIONES
    return [p for p in raiz.rglob("*.md") if not any(x.startswith(("00_", ".")) for x in p.relative_to(raiz).parts)]


def titulos_hechos():
    """Historias que ya existen (para que Gemini no repita trama)."""
    return sorted({re.sub(r"^\d{4}-\d{2}-\d{2}_([^_]+_)?(clips_)?", "", p.stem).replace("-", " ")
                   for p in notas_existentes()} - {""})


def siguiente_id():
    """P001, P002…: el siguiente número de historia propia (mira los nombres de las notas y el Registro)."""
    textos = [p.name for p in notas_existentes()]
    if (reg := registro()) and reg.exists():
        textos.append(reg.read_text(encoding="utf-8"))
    nums = [int(n) for t in textos for n in re.findall(r"(?<![A-Za-z0-9])P(\d{3,})(?!\d)", t)]
    return f"P{max(nums, default=0) + 1:03d}"


def escribir_historia(cfg):
    """Gemini: primero el plan (premisa, escaleta y textos para publicar) y luego la historia de dos en dos partes."""
    sistema = prompt_historias() + MODO_AUTOMATICO
    turnos = ["FASE 1 y FASE 2 de una vez: piensa 3 premisas, quédate con la mejor y escribe su escaleta de 8 partes, "
              "más el paquete de publicación de la FASE 4. Que no se parezca a ninguna de estas historias ya hechas: "
              + ("; ".join(titulos_hechos()) or "ninguna") + "."]
    plan = gemini(cfg, sistema, turnos, PLAN)
    turnos.append(json.dumps(plan, ensure_ascii=False))
    for a in (1, 3, 5, 7):
        gv.log(f"   Partes {a} y {a + 1} de 8…")
        turnos.append(f"FASE 3: escribe las PARTES {a} y {a + 1} de 8, siguiendo la escaleta y coherente con lo ya escrito.")
        turnos.append(gemini(cfg, sistema, turnos))
    return plan, limpiar("\n\n".join(turnos[3::2]))


def limpiar(texto):
    """Quita lo que no se lee (recuentos de palabras) y deja cada «PARTE X/8 · título» como encabezado."""
    texto = re.sub(r"^.*(palabras de esta tanda|total acumulado).*$", "", texto, flags=re.M | re.I)
    texto = re.sub(r"^[#*_ \t]*(PARTE\s+\d+\s*/\s*\d+\b.*?)[*_ \t]*$", r"### \1", texto, flags=re.M | re.I)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def guardar_nota(plan, historia, cfg):
    """La historia como nota de la carpeta de guiones: textos de publicación en el frontmatter, historia al final."""
    ident = siguiente_id()
    sub = "r/" + (re.sub(r"\W", "", plan["subreddit"].split("/")[-1]) or "AITAH")
    nombre = re.sub(r"[^a-z0-9]+", "-", gv.quitar_tildes(plan["titulo"].lower())).strip("-")
    nombre = (nombre[:41].rsplit("-", 1)[0] if len(nombre) > 40 else nombre) or "historia"
    ruta = gv.CARPETA_GUIONES / f"{date.today()}_{ident}_{nombre}.md"
    desc = plan["descripcion"].strip()
    if "ficci" not in desc.lower():
        desc += "\nHistoria de ficción inspirada en el estilo de Reddit."
    tags = " ".join("#" + t for t in (re.sub(r"\W", "", h) for h in plan["hashtags"]) if t)
    q = lambda s: json.dumps(s, ensure_ascii=False)
    cita = lambda s: "\n".join("> " + l for l in s.strip().splitlines())
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(f"""---
tipo: historia
id_reddit: {ident}
subreddit: {sub}
fecha_guardada: {date.today()}
estado: {"pendiente" if cfg["revision_humana"] else "aprobada"}
origen: gemini
categoria: {q(plan["categoria"])}
youtube_titulo: {q(plan["youtube_titulo"])}
descripcion: {q(desc)}
hashtags: {q(tags)}
pregunta: {q(plan["pregunta"])}
---
# {plan["titulo"].strip()}

> [!info] Escrita por Gemini ({cfg["modelo"]}) con el piloto automático
> Léela y pulsa «✓ Aprobar» en la app (o pon `estado: aprobada`). Si no te convence, pon `estado: descartada`.

> [!abstract] Resumen
{cita(plan["resumen"])}
>
> **Gancho:** {plan["gancho"].strip()}

> [!note]- Escaleta
{cita(chr(10).join(f"{i}. {p}" for i, p in enumerate(plan["escaleta"], 1)))}

## Historia

{historia}
""", encoding="utf-8")
    if (reg := registro()) and reg.exists():
        lineas = reg.read_text(encoding="utf-8").splitlines()
        i = max((k for k, l in enumerate(lineas) if l.startswith("|")), default=len(lineas) - 1)
        lineas.insert(i + 1, f"| {ident} | {plan['titulo'].strip().replace('|', '/')} | propia (ficción, estilo {sub}) | "
                             f"{date.today()} | {gv.estado_nota(ruta)} | [[{ruta.stem}]] | — | Gemini · piloto automático |")
        reg.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


def nueva_historia(cfg):
    gv.log(f"✍️  Gemini ({cfg['modelo']}) está escribiendo una historia nueva…")
    plan, historia = escribir_historia(cfg)
    nota = guardar_nota(plan, historia, cfg)
    g = gv.parsear_guion(nota)
    if not g.escenas or not g.cortes:
        poner_estado(nota, "error", "la historia salió sin texto que narrar o demasiado corta para hacer shorts")
        raise RuntimeError(f"la historia de {nota.name} no sirve (sin texto o demasiado corta)")
    voz = gv.linea_de_tiempo_estimada(g.escenas)[1][-1]
    gv.poner_campo(nota, "duracion_estimada", f"~{gv.mmss(voz)} narrada · {len(historia.split())} palabras · {len(g.cortes)} shorts")
    gv.log(f"✅ «{g.titulo}» · ~{gv.mmss(voz)} de voz · {len(g.cortes)} shorts → {nota.name}")
    return nota


# ──────────────────────────────────────────────────────────────────────────
#  Estado de las notas
# ──────────────────────────────────────────────────────────────────────────

def registro():
    return boveda() / "00_Sistema" / "Registro.md" if boveda() else None


def notas(*estados):
    """Notas de la carpeta de guiones en esos estados, la más antigua primero (el nombre empieza por la fecha)."""
    return sorted(p for p in gv.guiones_de(gv.CARPETA_GUIONES) if gv.estado_nota(p) in estados)


def sin_terminar(cfg):
    """Historias de Gemini en las que el piloto aún tiene trabajo. Sin publicación activada, las que ya
    tienen sus vídeos no cuentan (las subes tú): si contasen, el piloto no volvería a escribir nunca."""
    estados = EN_MARCHA if cfg["youtube"] or cfg["tiktok"] else ("pendiente", "aprobada")
    return [p for p in notas(*estados) if gv.campo(p, "origen") == "gemini"]


def poner_estado(nota, estado, motivo=""):
    """Estado en el frontmatter de la nota y en su fila del Registro de Obsidian (si la tiene)."""
    gv.poner_campo(nota, "estado", estado)
    if motivo:
        gv.poner_campo(nota, "error", motivo[:300])
    if (reg := registro()) and reg.exists():
        txt = reg.read_text(encoding="utf-8")
        nuevo = re.sub(rf"^((?:\|[^|\n]*){{4}}\|)[^|\n]*(\|.*{re.escape(f'[[{nota.stem}]]')}.*)$",
                       rf"\g<1> {estado} \g<2>", txt, flags=re.M)
        if nuevo != txt:
            reg.write_text(nuevo, encoding="utf-8")


def cola():
    """{estado: nº de notas} de la carpeta de guiones (lo enseña la app)."""
    cuenta = {}
    for p in gv.guiones_de(gv.CARPETA_GUIONES):
        e = gv.estado_nota(p)
        cuenta[e] = cuenta.get(e, 0) + 1
    return cuenta


# ──────────────────────────────────────────────────────────────────────────
#  3 · Crear los vídeos
# ──────────────────────────────────────────────────────────────────────────

def videos(nota):
    """(vídeo de YouTube o None, [shorts en orden]) ya creados para la nota (los de la última vez que se crearon)."""
    slug = gv.parsear_guion(nota).slug
    d = gv.CARPETA_SALIDA / slug
    largo = d / f"{slug} - YouTube.mp4"
    cortos = [(int(m[1]), int(m[2]), p) for p in d.glob("*.mp4")
              if p.name.startswith(f"{slug} - Parte ") and (m := re.search(r"Parte (\d+)de(\d+)\.mp4$", p.name))]
    if cortos:
        total = max(cortos, key=lambda c: c[2].stat().st_mtime)[1]
        cortos = sorted((n, p) for n, t, p in cortos if t == total)
    return (largo if largo.exists() else None), [p for _, p in cortos]


def crear_videos(nota, cfg):
    gv.log(f"🎬 Creando los vídeos de «{nota.stem}»…")
    gv.main([str(nota), "--solo", "todo"] + ["--gpu"] * bool(cfg["gpu"]))
    largo, cortos = videos(nota)
    if not largo or not cortos:
        raise RuntimeError("no se crearon los vídeos")
    poner_estado(nota, "lista")


# ──────────────────────────────────────────────────────────────────────────
#  4 · Publicar
# ──────────────────────────────────────────────────────────────────────────

def huecos(cfg, ahora=None):
    """Las horas de publicación de hoy; las que ya pasaron, ahora mismo."""
    ahora = ahora or datetime.now().astimezone()
    out = []
    for h in cfg["horas_publicacion"]:
        hh, mm = (int(x) for x in h.strip().split(":"))
        out.append(max(ahora.replace(hour=hh, minute=mm, second=0, microsecond=0), ahora))
    return sorted(out)


def publicar(cfg):
    """Un short (de la nota más antigua que tenga alguno pendiente) por cada hora de publicación de hoy."""
    destinos = [d for d in ("youtube", "tiktok") if cfg[d]]
    hechos = []
    for cuando in huecos(cfg) if destinos else []:
        for nota in notas("lista", "programada"):
            if r := publicar_siguiente(nota, cuando, destinos, cfg):
                hechos.append(r)
                break
        else:
            break
    return hechos


def publicar_siguiente(nota, cuando, destinos, cfg):
    """Sube lo siguiente de la nota para esa hora: su próximo short (y el vídeo largo con el primero).
    Devuelve qué subió, o "" si a la nota ya no le quedaba nada."""
    largo, cortos = videos(nota)
    g, n = gv.parsear_guion(nota), len(cortos)
    titulo = gv.campo(nota, "youtube_titulo") or g.titulo
    desc, tags, pregunta = gv.campo(nota, "descripcion"), gv.campo(nota, "hashtags"), gv.campo(nota, "pregunta")
    subido = []
    if "youtube" in destinos and largo and not gv.campo(nota, "youtube"):
        url = subir_youtube(largo, titulo, "\n\n".join(filter(None, [desc, pregunta, tags])), cuando, cfg)
        gv.poner_campo(nota, "youtube", url)
        subido.append("vídeo de YouTube")
    for d in destinos:
        k = int(gv.campo(nota, f"{d}_shorts") or 0)
        if k >= n:
            continue
        if d == "youtube":
            enlace = gv.campo(nota, "youtube")
            texto = [f"▶ La historia completa, con el final: {enlace}" if enlace else "", desc, f"{tags} #shorts".strip()]
            subir_youtube(cortos[k], f"{g.titulo[:84]} (Parte {k + 1}/{n})", "\n\n".join(filter(None, texto)), cuando, cfg)
        else:
            subir_tiktok(cortos[k])
        gv.poner_campo(nota, f"{d}_shorts", k + 1)
        subido.append(f"parte {k + 1}/{n} en {'YouTube' if d == 'youtube' else 'TikTok'}")
    acabada = (all(int(gv.campo(nota, f"{d}_shorts") or 0) >= n for d in destinos)
               and ("youtube" not in destinos or not largo or gv.campo(nota, "youtube")))
    poner_estado(nota, "publicada" if acabada else "programada")
    return f"{g.titulo}: {', '.join(subido)}" if subido else ""


def iniciar_sesion(url_de, puerto=0, ruta="/"):
    """Abre el inicio de sesión en el navegador y espera (5 min) a que vuelva a http://127.0.0.1:<puerto><ruta>.
    `url_de(redireccion, estado)` da la URL de inicio de sesión. Devuelve (código, redirección)."""
    recibido = {}

    class Vuelta(BaseHTTPRequestHandler):
        def do_GET(self):
            u = urlparse(self.path)
            if u.path.rstrip("/") == ruta.rstrip("/"):
                recibido.update((k, v[0]) for k, v in parse_qs(u.query).items())
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2 style='font-family:sans-serif'>Listo. Cierra esta pestaña y vuelve a la app.</h2>".encode())

        def log_message(self, *_):
            pass

    srv = HTTPServer(("127.0.0.1", puerto), Vuelta)
    srv.timeout = 2
    redir = f"http://127.0.0.1:{srv.server_port}{ruta}"
    estado = azar.token_urlsafe(16)
    webbrowser.open(url_de(redir, estado))
    fin = time.time() + 300
    while not recibido and time.time() < fin:
        srv.handle_request()
    srv.server_close()
    if recibido.get("state") != estado or "code" not in recibido:
        raise RuntimeError("no se completó el inicio de sesión" + (f": {recibido['error']}" if "error" in recibido else ""))
    return recibido["code"], redir


# ── YouTube (Data API v3) ────────────────────────────────────────────────
TOKEN_GOOGLE = "https://oauth2.googleapis.com/token"


def conectar_youtube(cliente):
    """Inicia sesión en Google (una vez) con el cliente OAuth «App de escritorio» y guarda el permiso de subida."""
    c = json.loads(Path(cliente).read_text(encoding="utf-8"))
    c = c.get("installed") or c.get("web") or {}
    if not c.get("client_id"):
        raise RuntimeError("ese archivo no es el JSON de un cliente OAuth de Google (tipo «App de escritorio»)")
    verificador = azar.token_urlsafe(64)
    reto = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    codigo, redir = iniciar_sesion(lambda redir, estado: "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": c["client_id"], "redirect_uri": redir, "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube.upload", "access_type": "offline", "prompt": "consent",
        "state": estado, "code_challenge": reto, "code_challenge_method": "S256"}))
    r, _ = pedir(TOKEN_GOOGLE, {"code": codigo, "client_id": c["client_id"], "client_secret": c.get("client_secret", ""),
                                "redirect_uri": redir, "grant_type": "authorization_code", "code_verifier": verificador},
                 formulario=True)
    if not r.get("refresh_token"):
        raise RuntimeError("Google no ha dado un permiso permanente; vuelve a intentarlo")
    guardar_secretos(youtube={"client_id": c["client_id"], "client_secret": c.get("client_secret", ""),
                              "refresh_token": r["refresh_token"]})


def token_google():
    y = secretos().get("youtube") or {}
    if not y.get("refresh_token"):
        raise RuntimeError("YouTube no está conectado («Piloto automático…» › Conectar YouTube)")
    try:
        r, _ = pedir(TOKEN_GOOGLE, {"client_id": y["client_id"], "client_secret": y["client_secret"],
                                    "refresh_token": y["refresh_token"], "grant_type": "refresh_token"}, formulario=True)
    except RuntimeError as e:
        if "invalid_grant" in str(e):
            raise RuntimeError("Google retiró el permiso de YouTube: vuelve a conectarlo (y pon la app de Google Cloud "
                               "«En producción»: en «Prueba» el permiso caduca a los 7 días)") from None
        raise
    return r["access_token"]


def subir_youtube(video, titulo, descripcion, cuando, cfg):
    """Sube el vídeo; si `cuando` es más tarde, queda programado (privado hasta esa hora). Devuelve su enlace."""
    limpio = lambda s: re.sub(r"[<>]", "", s)
    programado = cuando > datetime.now().astimezone() + timedelta(minutes=10)
    estado = {"privacyStatus": "private" if programado else "public", "selfDeclaredMadeForKids": False,
              "containsSyntheticMedia": bool(cfg["sintetico"])}
    if programado:
        estado["publishAt"] = cuando.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = {"snippet": {"title": limpio(titulo)[:100], "description": limpio(descripcion)[:4900], "categoryId": "24",
                        "defaultLanguage": "es", "defaultAudioLanguage": "es"}, "status": estado}
    tam, token = video.stat().st_size, token_google()
    _, cab = pedir("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status", meta,
                   {"Authorization": f"Bearer {token}", "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(tam)})
    with open(video, "rb") as f:  # ponytail: una sola petición; si se corta, se repite entera en la próxima pasada
        r, _ = pedir(cab["Location"], f, {"Authorization": f"Bearer {token}", "Content-Type": "video/mp4",
                                          "Content-Length": str(tam)}, "PUT")
    url = f"https://youtu.be/{r['id']}"
    gv.log(f"   ▶ YouTube: {video.name} → {url}" + (f" (sale el {cuando:%d/%m a las %H:%M})" if programado else ""))
    return url


# ── TikTok (Content Posting API: borrador en la bandeja de entrada) ─────────
TIKTOK = "https://open.tiktokapis.com"
TIKTOK_PUERTO, TIKTOK_RUTA = 8723, "/callback/"   # en la app de TikTok: plataforma Desktop, http://127.0.0.1:8723/callback/


def conectar_tiktok():
    t = secretos().get("tiktok") or {}
    if not (t.get("client_key") and t.get("client_secret")):
        raise RuntimeError("faltan el Client key y el Client secret de tu app de TikTok")
    verificador = azar.token_urlsafe(64)
    reto = hashlib.sha256(verificador.encode()).hexdigest()  # TikTok pide el SHA-256 en hexadecimal, no en base64
    codigo, redir = iniciar_sesion(lambda redir, estado: "https://www.tiktok.com/v2/auth/authorize/?" + urlencode({
        "client_key": t["client_key"], "response_type": "code", "scope": "video.upload", "redirect_uri": redir,
        "state": estado, "code_challenge": reto, "code_challenge_method": "S256"}), TIKTOK_PUERTO, TIKTOK_RUTA)
    _token_tiktok(t, {"code": codigo, "grant_type": "authorization_code", "redirect_uri": redir, "code_verifier": verificador})


def _token_tiktok(t, datos):
    """Pide un token a TikTok y guarda el refresh_token nuevo (cambia cada vez)."""
    r, _ = pedir(TIKTOK + "/v2/oauth/token/", {"client_key": t["client_key"], "client_secret": t["client_secret"], **datos},
                 formulario=True)
    if "access_token" not in r:
        raise RuntimeError(f"TikTok no dio permiso: {r.get('error_description') or r.get('error') or r}")
    guardar_secretos(tiktok={**t, "refresh_token": r["refresh_token"]})
    return r["access_token"]


def token_tiktok():
    t = secretos().get("tiktok") or {}
    if not t.get("refresh_token"):
        raise RuntimeError("TikTok no está conectado («Piloto automático…» › Conectar TikTok)")
    return _token_tiktok(t, {"grant_type": "refresh_token", "refresh_token": t["refresh_token"]})


def trozos_tiktok(tam):
    """(tamaño de trozo, nº de trozos): hasta 64 MB va entero; si no, trozos de 32 MB y el último se lleva el resto."""
    trozo = tam if tam <= 64_000_000 else 32_000_000
    return trozo, tam // trozo


def subir_tiktok(video):
    """Lo deja como borrador en tu bandeja de TikTok: te llega una notificación y lo publicas desde el móvil."""
    tam = video.stat().st_size
    trozo, n = trozos_tiktok(tam)
    r, _ = pedir(TIKTOK + "/v2/post/publish/inbox/video/init/",
                 {"source_info": {"source": "FILE_UPLOAD", "video_size": tam, "chunk_size": trozo, "total_chunk_count": n}},
                 {"Authorization": f"Bearer {token_tiktok()}"})
    if r.get("error", {}).get("code", "ok") != "ok":
        raise RuntimeError(f"TikTok: {r['error'].get('message') or r['error']}")
    with open(video, "rb") as f:
        for i in range(n):
            ini, fin = i * trozo, (tam if i == n - 1 else (i + 1) * trozo)
            pedir(r["data"]["upload_url"], f.read(fin - ini),
                  {"Content-Type": "video/mp4", "Content-Range": f"bytes {ini}-{fin - 1}/{tam}"}, "PUT")
    gv.log(f"   ♪ TikTok: {video.name} → borrador en tu bandeja de entrada")


# ──────────────────────────────────────────────────────────────────────────
#  Una pasada completa
# ──────────────────────────────────────────────────────────────────────────

def motivo(e):
    m = str(e.code if isinstance(e, SystemExit) else e) or type(e).__name__
    return m.replace("❌", "").strip()


def pasada(cfg=None):
    """Una pasada; lo que va haciendo sale donde diga gv.log (la app) y queda también en .cache/piloto.log."""
    CANDADO.parent.mkdir(parents=True, exist_ok=True)
    antes = gv.log
    with open(REGISTRO_PASADAS, "a", encoding="utf-8") as archivo:
        def log(m=""):
            print(m, file=archivo, flush=True)
            antes(m)
        gv.log = log
        try:
            _pasada(cfg or ajustes())
        finally:
            gv.log = antes


def _pasada(cfg):
    with open(CANDADO, "w") as candado:
        try:
            msvcrt.locking(candado.fileno(), msvcrt.LK_NBLCK, 1)  # se suelta solo si el proceso muere
        except OSError:
            gv.log("⚠ Ya hay una pasada del piloto en marcha.")
            return
        gv.log(f"🤖 Piloto automático · {datetime.now():%d/%m/%Y %H:%M}")
        hecho, fallos = [], []

        # 1 · Escribir
        en_marcha = sin_terminar(cfg)
        if len(en_marcha) < int(cfg["cola"]):
            try:
                hecho.append(f"historia nueva: {gv.parsear_guion(nueva_historia(cfg)).titulo}")
            except Exception as e:
                gv.log(f"❌ Gemini: {motivo(e)}")
                fallos.append(f"Gemini: {motivo(e)[:120]}")
        else:
            n = len(en_marcha)
            gv.log(f"   Ya hay {n} historia{'s' * (n > 1)} sin terminar ({', '.join(sorted({gv.estado_nota(p) for p in en_marcha}))}): "
                   f"no se escribe otra hasta que avance. Para tener más a la vez, sube «Historias en marcha».")

        # 3 · Crear los vídeos de la nota aprobada más antigua
        for nota in notas("aprobada")[:1]:
            try:
                crear_videos(nota, cfg)
                hecho.append(f"vídeos creados: {gv.parsear_guion(nota).titulo}")
            except (Exception, SystemExit) as e:
                gv.log(f"❌ Crear vídeos: {motivo(e)}")
                fallos.append(f"vídeos de {nota.stem}: {motivo(e).splitlines()[0][:120]}")
                poner_estado(nota, "error", motivo(e))

        # 4 · Publicar (una vez al día: si lanzas otra pasada, no vuelve a publicar)
        try:
            dia = json.loads(ESTADO.read_text(encoding="utf-8")).get("publicado")
        except (OSError, ValueError):
            dia = None
        if dia != str(date.today()):
            try:
                subidos = publicar(cfg)
            except Exception as e:
                gv.log(f"❌ Publicar: {motivo(e)}")
                fallos.append(f"publicar: {motivo(e)[:120]}")
            else:
                if subidos:
                    ESTADO.write_text(json.dumps({"publicado": str(date.today())}), encoding="utf-8")
                    hecho += subidos

        if pendientes := sum(gv.campo(p, "origen") == "gemini" for p in notas("pendiente")):
            hecho.append(f"{pendientes} historia{'s' * (pendientes > 1)} esperando tu aprobación")
        resumen = " · ".join(hecho + [f"⚠ {f}" for f in fallos]) or "nada que hacer hoy"
        gv.log(("⚠ " if fallos else "✅ ") + resumen)
        if hecho or fallos:
            avisar(resumen)


def avisar(texto):
    """Notificación de Windows (si no se puede, no pasa nada)."""
    q = "'" + texto[:250].replace("'", "''") + "'"
    ps = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null; "
          "$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
          "[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
          "$t = $x.GetElementsByTagName('text'); "
          "$t.Item(0).AppendChild($x.CreateTextNode('Reddit Video · piloto automático')) | Out-Null; "
          f"$t.Item(1).AppendChild($x.CreateTextNode({q})) | Out-Null; "
          "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
          "'{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe')"
          ".Show([Windows.UI.Notifications.ToastNotification]::new($x))")
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, timeout=30, creationflags=gv.SIN_VENTANA)
    except Exception:
        pass


def programar(activo, hora="09:00"):
    """Da de alta (o de baja) la tarea de Windows que lanza una pasada al día (si el PC estaba apagado, al encenderlo)."""
    q = lambda s: "'" + str(s).replace("'", "''") + "'"
    if activo:
        exe = Path(sys.executable).with_name("pythonw.exe")
        argumento = f'"{Path(__file__).resolve()}" --una-vez'
        ps = (f"$a = New-ScheduledTaskAction -Execute {q(exe if exe.exists() else sys.executable)} "
              f"-Argument {q(argumento)} -WorkingDirectory {q(gv.BASE)}; "
              f"$t = New-ScheduledTaskTrigger -Daily -At {q(hora)}; "
              "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Hours 8); "
              f"Register-ScheduledTask -TaskName {q(TAREA)} -Action $a -Trigger $t -Settings $s -Force | Out-Null")
    else:
        ps = f"Unregister-ScheduledTask -TaskName {q(TAREA)} -Confirm:$false -ErrorAction SilentlyContinue"
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, text=True, creationflags=gv.SIN_VENTANA)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[-400:] or "no se pudo cambiar la tarea programada")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Piloto automático: Gemini escribe, la app crea los vídeos y los publica")
    ap.add_argument("--una-vez", action="store_true", help="una pasada (lo que lanza la tarea programada)")
    ap.add_argument("--programar", metavar="HH:MM", help="una pasada al día a esa hora (tarea de Windows)")
    ap.add_argument("--desprogramar", action="store_true")
    ap.add_argument("--conectar-youtube", metavar="CLIENTE.json", help="el JSON del cliente OAuth de Google Cloud")
    ap.add_argument("--conectar-tiktok", action="store_true")
    a = ap.parse_args(argv)
    if a.una_vez:  # sin ventana (pythonw): lo que pasa queda en .cache/piloto.log
        try:
            pasada()
        except BaseException:
            with open(REGISTRO_PASADAS, "a", encoding="utf-8") as archivo:
                archivo.write(traceback.format_exc())
            avisar("La pasada falló: el detalle está en .cache/piloto.log")
    elif a.programar or a.desprogramar:
        programar(bool(a.programar), a.programar or "")
    elif a.conectar_youtube:
        conectar_youtube(a.conectar_youtube)
        print("YouTube conectado.")
    elif a.conectar_tiktok:
        conectar_tiktok()
        print("TikTok conectado.")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
