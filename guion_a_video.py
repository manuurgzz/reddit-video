#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
guion_a_video.py — Convierte una historia (texto normal, .txt o nota de Obsidian) en vídeos estilo "historias de Reddit".

  · Vídeo completo 16:9 para YouTube
  · Cortes 9:16 para TikTok / Reels / Shorts (los del "Mapa de cortes" de la nota o, si no lo trae, calculados solos)

Uso rápido (Windows, desde la carpeta del script):
    python guion_a_video.py                      -> último guion de la carpeta de guiones
    python guion_a_video.py "ruta\\al\\guion.md"
    python guion_a_video.py --analizar           -> solo muestra lo que ha entendido del guion
    python guion_a_video.py --solo cortes        -> solo los cortes (o: youtube, parte2 ...)
    python guion_a_video.py --rapido             -> prueba rápida a media resolución
    python guion_a_video.py --gpu                -> codifica con NVIDIA (NVENC), mucho más rápido

Requisitos: Python 3.9+, la app Texto a Voz (CARPETA_TEXTO_VOZ) con edge-tts, y ffmpeg en el PATH
(`winget install Gyan.FFmpeg`). Todo gratis y sin marca de agua.
"""

import argparse
import asyncio
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import unicodedata
import wave
from dataclasses import dataclass, field, replace
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN — cambia aquí lo que quieras
# ══════════════════════════════════════════════════════════════════════════

BASE = Path(__file__).resolve().parent
AJUSTES = BASE / "ajustes.json"       # bóveda de Obsidian / carpeta de guiones elegida en la app (no se sube a GitHub)


def leer_ajustes():
    try:
        return json.loads(AJUSTES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


CARPETA_GUIONES = Path(leer_ajustes().get("carpeta_guiones") or BASE / "guiones")
CARPETA_FONDOS = BASE / "fondos"      # fondos/JABON, fondos/SLIME, ...
CARPETA_MUSICA = BASE / "musica"      # mp3/m4a/wav opcionales (se elige uno al azar)
CARPETA_FUENTES = BASE / "fuentes"    # opcional: mete aquí .ttf (p. ej. Montserrat ExtraBold)
CARPETA_SALIDA = BASE / "salida"
CARPETA_CACHE = BASE / ".cache"

ETIQUETAS = ["JABON", "SLIME", "ARENA", "PINTURA", "PRENSA", "RUNNER", "PARKOUR", "CERA"]

# Voz: la genera la app Texto a Voz (su motor, voz.py). Cada proyecto nuevo coge una al azar (mitad hombre, mitad mujer) y la recuerda.
VOCES = {
    "es-ES-AlvaroNeural": "Hombre · España",
    "es-ES-ElviraNeural": "Mujer · España",
    "es-ES-XimenaNeural": "Mujer · España",
    "es-MX-JorgeNeural": "Hombre · México",
    "es-MX-DaliaNeural": "Mujer · México",
    "es-US-AlonsoNeural": "Hombre · EE. UU.",
    "es-US-PalomaNeural": "Mujer · EE. UU.",
    "es-CO-GonzaloNeural": "Hombre · Colombia",
    "es-CO-SalomeNeural": "Mujer · Colombia",
    "es-AR-TomasNeural": "Hombre · Argentina",
    "es-AR-ElenaNeural": "Mujer · Argentina",
}
CARPETA_TEXTO_VOZ = BASE / "Texto_Voz"   # la app Texto a Voz, incluida en el repo
VELOCIDAD = "+25%"          # "+0%", "+10%", "-5%" ...
TONO = "+0Hz"

# Pausas (segundos)
# (los silencios que trae la voz se recortan antes; estas pausas son lo único que queda)
PAUSA_LINEA = 0.10         # entre líneas de narración
PAUSA_EXTRA_SUSPENSO = 0.22  # extra si la línea acaba en "…" o ":"
PAUSA_EXTRA_PREGUNTA = 0.08  # extra si acaba en "?"
PAUSA_ESCENA = 0.30        # entre escenas
SILENCIO_MAX_INTERNO = 0.20  # silencios dentro de una línea (puntos, comas largas) se acortan a esto
UMBRAL_SILENCIO = 450        # amplitud por debajo de la cual se considera silencio (0-32767)

# Tarjeta inicial: post de Reddit (r/subreddit, u/usuario y el título del post)
TARJETA_SEG = 3.0
LEER_TITULO_YOUTUBE = True           # en YouTube la voz lee el título mientras se ve la tarjeta

# Llamada a la acción del último corte
TEXTO_FINAL_CORTE = ["El FINAL", "en YouTube", "(link en bio)"]
VOZ_FINAL_CORTE = "El final, en YouTube. Link en la bio."   # "" para que no lo lea
COLA_FINAL_CORTE = 3.5               # segundos extra al final del último corte
COLA_NORMAL = 1.2                    # segundos extra al final del resto
COMENTA_SEG = 3.0                    # "Comenta" los últimos N s del vídeo de YouTube
TEXTO_SIGUIENTE = "Continúa en mi perfil"   # al final de los cortes intermedios ("" para quitarlo)
SIGUIENTE_PARTE_SEG = 2.5

# Cortes automáticos: si la nota no trae «Mapa de cortes» (o es un texto normal), la app parte la historia
# ella sola: shorts de la duración objetivo que terminan en un punto de suspense (…, ?, :, «pero…», fin de sección).
CORTE_OBJETIVO = 150        # s de voz que se buscan por short (los hechos a mano rondaban 2:20-3:20)
CORTE_MIN = 61              # TikTok solo paga los vídeos de más de 1 minuto
CORTE_MAX = 170             # YouTube trata como Short hasta 3:00 (se deja margen para la cola)
FINAL_SOLO_YOUTUBE = 0.2    # parte final de la historia que no sale en los shorts («El FINAL en YouTube»); 0 = entera
SEG_POR_LETRA = 0.048       # para estimar la voz antes de generarla (calibrado con la caché, voz a +25 %)
SEG_POR_FRASE = 0.26

# Subtítulos
FUENTE_SUBS = "Arial Black"
FUENTE_TARJETA = "Arial"
PALABRAS_MAX = 3            # 2-4 palabras por golpe
CARACTERES_MAX = 16
MAYUSCULAS = False
COLOR_CLAVE = "&H0000E6FF&"   # amarillo (formato ASS: &HBBGGRR&)

# Fondos: "recortar" = llenar toda la pantalla (recorta lo que sobra) · "desenfocado" = clip entero sobre fondo borroso
RELLENO_VERTICAL = "recortar"      # TikTok/Reels: los clips horizontales ocupan toda la pantalla
RELLENO_HORIZONTAL = "desenfocado"  # YouTube: los clips verticales se ven enteros con fondo borroso
DURACION_FONDO_VERTICAL = 30          # s que dura cada clip de fondo en los shorts
DURACION_FONDO_HORIZONTAL = 60        # s que dura cada clip de fondo en YouTube
VIDEO_LARGO_MIN = 15 * 60             # un vídeo de fondo así de largo se reutiliza para toda su temática

# Música
VOLUMEN_MUSICA = 0.12       # 0.0-1.0 (además se agacha sola cuando habla la voz)
MUSICA_AUTOMATICA = True    # coge una al azar de /musica si no pasas --musica

# Vídeo
FPS = 30
CRF = 20
PRESET = "veryfast"
FORMATOS = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}
EXT_VIDEO = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}
EXT_AUDIO = {".mp3", ".m4a", ".wav", ".ogg", ".aac", ".flac"}

TTS_CONCURRENCIA = 4
SR = 24000  # frecuencia de muestreo interna de la voz

# ══════════════════════════════════════════════════════════════════════════

SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # que ffmpeg no abra consolas desde la app
al_progresar = None  # la app lo cambia por una función(fracción 0-1) para la barra de progreso

# ffmpeg de winget aunque la terminal no lo tenga en el PATH
if not shutil.which("ffmpeg"):
    _wg = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet"
    for _d in [_wg / "Links", *_wg.glob("Packages/Gyan.FFmpeg*/ffmpeg-*/bin")]:
        os.environ["PATH"] = f"{_d}{os.pathsep}{os.environ['PATH']}"


def log(msg=""):
    print(msg, flush=True)


def quitar_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm(s):
    """Normaliza una palabra para comparar: sin tildes, minúsculas, solo alfanumérico."""
    return re.sub(r"[^0-9a-zñ]", "", quitar_tildes(s.lower().replace("ñ", "\x00")).replace("\x00", "ñ"))


RE_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF"
    "\U0001F900-\U0001F9FF\uFE0F\u200D\u2190-\u21FF\u2B00-\u2BFF]+"
)


def sin_emojis(s):
    return re.sub(r"\s{2,}", " ", RE_EMOJI.sub("", s)).strip()


# ──────────────────────────────────────────────────────────────────────────
#  Estructuras
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class Palabra:
    texto: str
    negrita: bool = False
    clave: bool = False
    ini: float = 0.0
    fin: float = 0.0


@dataclass
class Linea:
    texto_tts: str
    palabras: list
    wav: Path = None
    pcm: bytes = b""          # audio ya compactado (sin silencios sobrantes)
    dur: float = 0.0          # duración útil (recortado el silencio final)
    limites: list = field(default_factory=list)  # [(texto, ini, dur)] de edge-tts
    fin_parrafo: bool = False  # última frase de un párrafo (solo en texto normal): buen sitio para cortar


@dataclass
class Escena:
    num: int
    titulo: str
    etiqueta: str
    claves: list
    lineas: list
    zoom: list = field(default_factory=list)   # frases con "zoom punch" (formato de 02_Clips)


@dataclass
class Corte:
    parte: int
    total: int
    desde: int
    hasta: int
    fondo: str = ""   # temática de fondo de ese short, si la nota la indica
    lineas: tuple = ()  # corte automático: (primera, última + 1) contando todas las líneas de la historia
    seg: float = 0.0    # corte automático: duración estimada de la voz


@dataclass
class Guion:
    ruta: Path
    slug: str
    titulo: str
    escenas: list
    cortes: list


# ──────────────────────────────────────────────────────────────────────────
#  1. Leer el guion (dos formatos: guion clásico y nota de clips de Obsidian)
# ──────────────────────────────────────────────────────────────────────────

RE_ESCENA = re.compile(r"^#{2,4}\s*ESCENA\s+(\d+)\s*[·\-–—:.]?\s*(.*?)\s*(\([^)]*\))?\s*$", re.I)
RE_ESCENA_CLIPS = re.compile(r"^\[ESCENA\s+(\d+)([^\]]*)\]$", re.I)
RE_ETIQUETA = re.compile(r"\[([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)\]")
RE_COMILLAS = re.compile(r"[\"“«]([^\"”»]+)[\"”»]")
LETRAS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"


def normalizar_etiqueta(t):
    return quitar_tildes(t).upper()


def parsear_linea_narracion(texto):
    """Devuelve (texto_tts, [Palabra]) respetando **negritas**."""
    palabras = []
    partes = re.split(r"(\*\*.+?\*\*)", texto)
    for parte in partes:
        if not parte:
            continue
        negrita = parte.startswith("**") and parte.endswith("**") and len(parte) > 4
        limpio = parte[2:-2] if negrita else parte
        limpio = limpio.replace("*", "").replace("_", " ")
        limpio = sin_emojis(limpio)
        for tok in limpio.split():
            palabras.append(Palabra(tok, negrita))
    texto_tts = " ".join(p.texto for p in palabras)
    return texto_tts, palabras


def extraer_claves(fondo):
    claves = []
    for m in re.finditer(r"amarillo[^:\n]*:\s*((?:[\"“«][^\"”»]+[\"”»][\s,y]*)+)", fondo, re.I):
        claves += RE_COMILLAS.findall(m.group(1))
    return [c.strip() for c in claves if c.strip()]


def escenas_guion(lineas):
    """Formato clásico: '### ESCENA N · Título' + '**Narración:**' + '**Fondo / edición:** [ETIQUETA]'."""
    escenas = []
    actual = None
    modo = None
    fondo_txt = []

    def cerrar():
        nonlocal actual, fondo_txt
        if actual:
            fondo = " ".join(fondo_txt)
            etiquetas = [normalizar_etiqueta(e) for e in RE_ETIQUETA.findall(fondo)]
            validas = [e for e in etiquetas if e in ETIQUETAS] or etiquetas
            actual.etiqueta = validas[0] if validas else ""
            actual.claves = extraer_claves(fondo)
            if actual.lineas:
                escenas.append(actual)
        actual, fondo_txt = None, []

    for raw in lineas:
        linea = raw.strip()
        me = RE_ESCENA.match(linea)
        if me:
            cerrar()
            actual = Escena(int(me.group(1)), me.group(2).strip(" ·-"), "", [], [])
            modo = None
            continue
        if actual is None:
            continue
        if linea.startswith("#") or linea == "---":
            cerrar()
            modo = None
            continue
        if re.match(r"^\*\*Narraci[óo]n:?\*\*", linea, re.I):
            modo = "narr"
            linea = re.sub(r"^\*\*Narraci[óo]n:?\*\*:?", "", linea, flags=re.I).strip()
            if not linea:
                continue
        elif re.match(r"^\*\*(Fondo|Edici)", linea, re.I):
            modo = "fondo"
            fondo_txt.append(linea)
            continue
        if not linea:
            continue
        if modo == "narr":
            if linea.startswith(">") or re.match(r"^\*?\[.*\]\*?$", linea):
                continue
            texto_tts, palabras = parsear_linea_narracion(linea)
            if palabras:
                actual.lineas.append(Linea(texto_tts, palabras))
        elif modo == "fondo":
            fondo_txt.append(linea)
    cerrar()
    return escenas


def escenas_clips(lineas):
    """Nota de clips (02_Clips): bloques con '[ESCENA N · FONDO: X]', notas '[Efecto: …]' y el texto narrado.
    Las escenas se repiten en los clips cortos y en el vídeo completo: gana la última (la más completa)."""
    escenas, actual, fondo_seccion = {}, None, ""
    for raw in lineas:
        l = raw.strip()
        if l.startswith("#"):  # '## Clip 2 · Parte 2/3 · fondo ARENA'
            m = re.search(rf"fondo\s+([{LETRAS}]+)", l, re.I)
            fondo_seccion = normalizar_etiqueta(m.group(1)) if m else ""
            actual = None
            continue
        if l.startswith("```"):
            actual = None
            continue
        me = RE_ESCENA_CLIPS.match(l)
        if me:
            n = int(me.group(1))
            m = re.search(rf"FONDO:\s*([{LETRAS}]+)", me.group(2), re.I)
            etiqueta = normalizar_etiqueta(m.group(1)) if m else fondo_seccion
            anterior = escenas.get(n)
            actual = Escena(n, "", etiqueta or (anterior.etiqueta if anterior else ""), [], [])
            escenas[n] = actual
            continue
        if actual is None or not l:
            continue
        if l.startswith("["):
            m = re.search(r"amarillo:\s*([^\].]+)", l, re.I)
            if m:
                actual.claves += [c.strip(" \"“”«»") for c in re.split(r",|\s+y\s+", m.group(1)) if c.strip()]
            if "zoom" in l.lower():
                actual.zoom += RE_COMILLAS.findall(l)
            continue
        texto_tts, palabras = parsear_linea_narracion(l)
        if palabras:
            actual.lineas.append(Linea(texto_tts, palabras))
    return [escenas[n] for n in sorted(escenas) if escenas[n].lineas]


RE_SECCION_HISTORIA = re.compile(r"^#{1,3}\s*(historia|texto|relato)\b", re.I)
RE_CAPITULO = re.compile(r"(parte|cap[ií]tulo|part|chapter)\s+\d+\b(?!.*[.!?…]$)", re.I)  # «PARTE 2/8 · El giro»
RE_FRASE = re.compile(r"(?<=[.!?…])\s+(?=[¿¡«\"“(—–-]?[A-ZÁÉÍÓÚÜÑ0-9])")
RE_PEGADO = re.compile(r"(?<=[a-záéíóúüñ][.!?…])(?=[¿¡«]?[A-ZÁÉÍÓÚÜÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ])")  # «rojo.Todavía» (no «EE.UU.»)


def escenas_texto(lineas):
    """Texto normal (una historia pegada tal cual, un .txt, una nota de 01_Historias…): cada sección con
    título (#) es una escena y cada frase, una línea de voz. Si hay una sección «Historia…», se lee desde ahí."""
    inicio = next((i + 1 for i, l in enumerate(lineas) if RE_SECCION_HISTORIA.match(l.strip())), 0)
    escenas, actual, seccion, en_codigo = [], None, "", False
    # texto pegado de la web: 3+ espacios = salto de párrafo perdido, y «frase.Otra» sin espacio
    parrafos = [p for raw in lineas[inicio:] for p in re.split(r"\s{3,}", RE_PEGADO.sub(" ", raw.strip()))]
    for l in parrafos:
        if l.startswith("```"):
            en_codigo = not en_codigo
            continue
        if re.match(r"#{1,6}\s", l):
            actual, seccion = None, l.lstrip("#").strip()  # título de sección: no se lee, abre escena nueva
            continue
        if en_codigo or not l or l.startswith(("|", ">", "![[", "<!--")) or re.fullmatch(r"[-*_]{3,}|\(.*\)|\[.*\]", l):
            continue  # tablas, citas, separadores y notas entre paréntesis o corchetes
        l = re.sub(r"^(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s*)?", "", l)       # viñetas, listas y casillas
        l = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", l)           # [[nota|texto]] -> texto
        ultima = None
        for f in RE_FRASE.split(l):
            if len(f) <= 120 and RE_CAPITULO.match(f):  # «PARTE 2/8 · El giro» sin «#»: también abre sección
                actual, seccion = None, f.strip()
                continue
            texto_tts, palabras = parsear_linea_narracion(f)
            if not palabras:
                continue
            if actual is None:
                actual = Escena(len(escenas) + 1, seccion, "", [], [])
                escenas.append(actual)
            ultima = Linea(texto_tts, palabras)
            actual.lineas.append(ultima)
        if ultima:
            ultima.fin_parrafo = True
    return escenas


def marcar(escena, frases, atributo):
    """Pone atributo=True (clave o negrita) en las palabras que forman cada frase."""
    for frase in frases:
        objetivo = [norm(w) for w in frase.split() if norm(w)]
        if not objetivo:
            continue
        for ln in escena.lineas:
            ws = [norm(p.texto) for p in ln.palabras]
            for i in range(len(ws) - len(objetivo) + 1):
                if ws[i:i + len(objetivo)] == objetivo:
                    for p in ln.palabras[i:i + len(objetivo)]:
                        setattr(p, atributo, True)


def cortes_de_tablas(lineas):
    """Filas 'Parte X/Y' de cualquier tabla que tenga columna de escenas (Mapa de cortes o tabla de clips)."""
    cortes, cab = {}, None
    for l in lineas:
        l = l.strip()
        if not l.startswith("|"):
            cab = None
            continue
        celdas = [c.strip() for c in l.strip("|").split("|")]
        if cab is None:
            cab = [c.lower() for c in celdas]
            continue
        mp = re.search(r"Parte\s*(\d+)\s*/\s*(\d+)", celdas[0], re.I)
        col_esc = next((i for i, c in enumerate(cab) if "escena" in c), None)
        if not mp or col_esc is None or col_esc >= len(celdas):
            continue
        rango = re.findall(r"\d+", celdas[col_esc])
        if not rango:
            continue
        col_fondo = next((i for i, c in enumerate(cab) if "fondo" in c), None)
        fondo = celdas[col_fondo] if col_fondo is not None and col_fondo < len(celdas) else ""
        fondo = normalizar_etiqueta(re.sub(rf"[^{LETRAS}]", "", fondo))
        parte = int(mp.group(1))
        cortes[parte] = Corte(parte, int(mp.group(2)), int(rango[0]), int(rango[-1]), fondo if fondo in ETIQUETAS else "")
    return [cortes[k] for k in sorted(cortes)]


# ── Cortes automáticos ───────────────────────────────────────────────────

RE_GIRO = re.compile(r"^(pero|entonces|y entonces|de repente|hasta que|fue entonces|sin embargo|en ese momento|"
                     r"justo entonces|y ahí|lo que no sabía|resulta que)\b", re.I)


def estimar_voz(linea: Linea):
    """Duración de la voz: la real si ya está generada; si no, estimada por el número de letras."""
    return linea.dur or SEG_POR_LETRA * len(re.sub(r"\W", "", linea.texto_tts)) + SEG_POR_FRASE


def linea_de_tiempo_estimada(escenas):
    """[(línea, escena, ¿acaba escena?)] y el instante estimado en que empieza cada una (+ el total al final)."""
    seq = [(l, e, k == len(e.lineas) - 1) for e in escenas for k, l in enumerate(e.lineas)]
    t = [0.0]
    for l, _, fin_escena in seq:
        t.append(t[-1] + estimar_voz(l) + (PAUSA_ESCENA if fin_escena else pausa_tras(l)))
    return seq, t


def suspense(linea: Linea, fin_escena, siguiente):
    """Lo bueno que es terminar un short justo después de esta línea."""
    fin = linea.texto_tts.rstrip(" \"”»')")
    p = 3.0 if fin_escena else (1.0 if linea.fin_parrafo else 0.0)
    if fin.endswith(("…", "...")):
        p += 3
    elif fin.endswith(("?", ":")):
        p += 2
    elif fin.endswith("!"):
        p += 1
    elif not fin.endswith("."):
        p -= 3  # frase a medias
    if len(linea.palabras) <= 6 and (fin_escena or linea.fin_parrafo):
        p += 1  # remate corto: «Eso fue mi primer error.»
    if any(w.negrita for w in linea.palabras):
        p += 1  # frase con zoom
    if siguiente is not None and RE_GIRO.match(siguiente.texto_tts.lstrip("«\"“¿¡—–- ")):
        p += 2  # lo siguiente es un giro: mejor dejarlo para el próximo short
    return p


def cortes_automaticos(escenas, semilla=""):
    """Parte la historia en shorts de ~CORTE_OBJETIVO s que acaban en suspense, y deja el último
    FINAL_SOLO_YOUTUBE de la historia para YouTube. Programación dinámica sobre los huecos entre frases."""
    seq, t = linea_de_tiempo_estimada(escenas)
    n, total = len(seq), t[-1]
    if n < 2:
        return []
    bono = [suspense(l, fin, seq[i + 1][0] if i + 1 < n else None) for i, (l, _, fin) in enumerate(seq)]
    meta, margen = total * (1 - FINAL_SOLO_YOUTUBE), total * 0.1
    finales = [j for j in range(1, n) if abs(t[j] - meta) <= margen] if FINAL_SOLO_YOUTUBE else [n]

    # ponytail: O(n·frases por short); de sobra para historias de una hora
    for minimo, maximo in ((CORTE_MIN, CORTE_MAX), (0, CORTE_MAX), (0, float("inf"))):
        mejor, previo = [0.0] + [float("inf")] * n, [0] * (n + 1)
        for j in range(1, n + 1):
            for i in range(j - 1, -1, -1):
                d = t[j] - t[i]
                if d > maximo:
                    break
                c = mejor[i] + ((d - CORTE_OBJETIVO) / 20) ** 2 - bono[j - 1]
                if d >= minimo and c < mejor[j]:
                    mejor[j], previo[j] = c, i
        validos = [j for j in finales if mejor[j] < float("inf")]
        if validos:
            break
    else:
        return []
    # el corte que da paso a «El FINAL en YouTube» cuenta doble y conviene que caiga cerca de la meta
    j = min(validos, key=lambda j: mejor[j] - (bono[j - 1] if FINAL_SOLO_YOUTUBE else 0) + ((t[j] - meta) / margen) ** 2)
    tramos = []
    while j > 0:
        tramos.insert(0, (previo[j], j))
        j = previo[j]

    # un único tema de fondo por short, distinto del anterior (el de sus escenas, si tiene clips)
    temas = [e for e in ETIQUETAS if clips_de(e)]
    random.Random(semilla).shuffle(temas)
    cortes, anterior = [], ""
    for k, (i, j) in enumerate(tramos, 1):
        propios = [e.etiqueta for _, e, _ in seq[i:j] if e.etiqueta and clips_de(e.etiqueta)]
        tema = next((x for x in propios + temas[k:] + temas[:k] if x != anterior), anterior)
        cortes.append(Corte(k, len(tramos), seq[i][1].num, seq[j - 1][1].num, tema, (i, j), t[j] - t[i]))
        anterior = tema
    return cortes


def escenas_del_corte(g: Guion, c: Corte):
    """Escenas de un short; en los cortes automáticos, recortadas a sus frases."""
    if not c.lineas:
        return [e for e in g.escenas if c.desde <= e.num <= c.hasta]
    out, k = [], 0
    for e in g.escenas:
        dentro = [l for i, l in enumerate(e.lineas, k) if c.lineas[0] <= i < c.lineas[1]]
        k += len(e.lineas)
        if dentro:
            out.append(replace(e, lineas=dentro))
    return out


def mmss(s):
    return f"{int(s // 60)}:{int(s % 60):02d}"


def solo_youtube(g: Guion):
    """Escenas que la tabla de cortes deja fuera de los shorts (normalmente el final): solo van en YouTube."""
    if not g.cortes or g.cortes[0].lineas:
        return []
    return [e.num for e in g.escenas if not any(c.desde <= e.num <= c.hasta for c in g.cortes)]


def lista(nums):
    """[7, 8] -> «7 y 8»"""
    nums = [str(n) for n in nums]
    return " y ".join([", ".join(nums[:-1]), nums[-1]] if len(nums) > 1 else nums)


def parsear_guion(ruta: Path) -> Guion:
    txt = ruta.read_text(encoding="utf-8")
    txt = re.sub(r"^---\n.*?\n---\n", "", txt, count=1, flags=re.S)  # frontmatter
    lineas = txt.splitlines()
    escenas = escenas_guion(lineas) or escenas_clips(lineas)
    texto_normal = not escenas
    if texto_normal:
        escenas = escenas_texto(lineas)

    # Título de la tarjeta
    if texto_normal:
        m = re.search(r"^#\s+(.+)", txt, re.M)  # «# Título» del texto
    else:
        m = (re.search(r"con el t[íi]tulo:?\s*[\"“«]([^\"”»]+)[\"”»]", txt, re.I)
             or re.search(r"###\s*YouTube.*?\*\*T[íi]tulo:\*\*\s*(.+)", txt, re.S | re.I))
    if m:
        titulo = m.group(1).strip()
    else:  # 2026-10-01_P001_la-reforma-de-mi-cunado -> La reforma de mi cunado
        titulo = re.sub(r"^\d{4}-\d{2}-\d{2}_([^_]+_)?", "", ruta.stem).replace("-", " ").replace("_", " ").strip().capitalize()
    titulo = sin_emojis(titulo)

    for esc in escenas:
        marcar(esc, esc.claves, "clave")
        marcar(esc, esc.zoom, "negrita")

    slug = re.sub(r"_(guion|clips)_?", "_", ruta.stem)
    return Guion(ruta, slug, titulo, escenas, cortes_de_tablas(lineas) or cortes_automaticos(escenas, slug))


# ──────────────────────────────────────────────────────────────────────────
#  Datos de cada proyecto (voz y post de Reddit): se eligen la primera vez y se recuerdan
# ──────────────────────────────────────────────────────────────────────────

ARCHIVO_PROYECTOS = CARPETA_CACHE / "proyectos.json"


def voz_al_azar():
    genero = random.choice(["Hombre", "Mujer"])
    return random.choice([v for v, d in VOCES.items() if d.startswith(genero)])


def usuario_al_azar():
    return ("u/" + random.choice(["Throwaway", "ThrowRA_", "throwaway_", "Anon_"])
            + random.choice(["Quiet", "Cold", "Lost", "Silent", "Tired", "Calm"])
            + random.choice(["Heart", "Mind", "Days", "Storm", "Soul"]) + str(random.randint(7, 9999)))


def subreddit_de(ruta: Path):
    """r/… de la ficha de la historia (enlazada con 'historia: [[…]]' en el guion) o del propio guion."""
    txt = ruta.read_text(encoding="utf-8")
    m = re.search(r"^historia:\s*\"?\[\[([^\]|]+)", txt, re.M)
    if m:
        ficha = next(ruta.parent.parent.glob(f"*/{m.group(1)}.md"), None)
        if ficha:
            txt = ficha.read_text(encoding="utf-8") + txt
    m = re.search(r"original en (r/\w+)", txt, re.I) or re.search(r"\b(r/\w+)", txt)
    return m.group(1) if m else "r/AITAH"


def leer_proyectos():
    try:
        return json.loads(ARCHIVO_PROYECTOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guardar_proyecto(slug, datos):
    todos = leer_proyectos()
    todos[slug] = datos
    ARCHIVO_PROYECTOS.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVO_PROYECTOS.write_text(json.dumps(todos, ensure_ascii=False, indent=1), encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────
#  Obsidian: conectar la bóveda y marcar en la nota los clips ya creados
# ──────────────────────────────────────────────────────────────────────────

def conectar_carpeta(carpeta: Path):
    """Acepta la bóveda de Obsidian (o una carpeta dentro de ella, o una carpeta normal).
    Guarda y devuelve (bóveda o None, carpeta de donde leer las notas)."""
    boveda = next((d for d in [carpeta, *carpeta.parents] if (d / ".obsidian").is_dir()), None)
    notas = carpeta
    if boveda and carpeta == boveda:
        notas = next((boveda / n for n in ("02_Clips", "03_Guiones") if (boveda / n).is_dir()), boveda)
    guardar_ajustes(boveda=str(boveda) if boveda else "", carpeta_guiones=str(notas))
    return boveda, notas


def guardar_ajustes(**cambios):
    """Cambia solo esas claves de ajustes.json (el resto, como el bloque del piloto automático, se queda)."""
    AJUSTES.write_text(json.dumps({**leer_ajustes(), **cambios}, ensure_ascii=False, indent=1), encoding="utf-8")


def _frontmatter(txt):
    m = re.match(r"---\n(.*?)\n---\n", txt, re.S)
    return m.group(1) if m else None


def campo(ruta: Path, clave):
    """Valor de un campo del frontmatter de la nota ("" si no está). Entiende "texto entre comillas" con \\n."""
    m = re.search(rf"^{clave}:[ \t]*(.*)$", _frontmatter(ruta.read_text(encoding="utf-8")) or "", re.M)
    v = m.group(1).strip() if m else ""
    try:
        return json.loads(v) if v.startswith('"') else v.strip("'")
    except ValueError:
        return v


def poner_campo(ruta: Path, clave, valor):
    """Escribe (o añade) un campo del frontmatter; si la nota no tiene, se lo crea."""
    valor = str(valor)
    linea = f"{clave}: " + (valor if re.fullmatch(r"[\w./+-]+", valor) else json.dumps(valor, ensure_ascii=False))
    txt = ruta.read_text(encoding="utf-8")
    fm = _frontmatter(txt)
    if fm is None:
        txt = f"---\n{linea}\n---\n{txt}"
    elif re.search(rf"^{clave}:", fm, re.M):
        txt = txt.replace(fm, re.sub(rf"^{clave}:.*$", lambda _: linea, fm, count=1, flags=re.M), 1)
    else:
        txt = txt.replace(fm, f"{fm}\n{linea}", 1)
    ruta.write_text(txt, encoding="utf-8")


def estado_nota(ruta: Path):
    return campo(ruta, "estado")


def marcar_en_obsidian(ruta: Path, partes, youtube):
    """Marca '- [x]' en el checklist de la nota los shorts (Parte N/T) y el vídeo de YouTube creados,
    y actualiza clips_hechos y estado. Si la nota no tiene checklist, no toca nada."""
    txt = ruta.read_text(encoding="utf-8")

    def tachar(m):
        linea = m.group(0)
        p = re.search(r"Parte\s*(\d+)\s*/", linea, re.I)
        hecho = (p and int(p.group(1)) in partes) or (youtube and re.search(r"YouTube|completo", linea, re.I))
        return linea.replace("[ ]", "[x]", 1) if hecho else linea

    nuevo = re.sub(r"^\s*- \[ \] .*$", tachar, txt, flags=re.M)
    hechos = len(re.findall(r"^\s*- \[[xX]\]", nuevo, re.M))
    total = len(re.findall(r"^\s*- \[[ xX]\]", nuevo, re.M))
    if nuevo == txt or not total:
        return False
    nuevo = re.sub(r"^clips_hechos:.*$", f"clips_hechos: {hechos}/{total}", nuevo, count=1, flags=re.M)
    if estado_nota(ruta) not in ("publicada", "descartada"):
        nuevo = re.sub(r"^estado:.*$", f"estado: {'hecha' if hechos == total else 'en-produccion'}",
                       nuevo, count=1, flags=re.M)
    ruta.write_text(nuevo, encoding="utf-8")
    log(f"📝 Obsidian: {hechos}/{total} clips marcados como hechos en la nota.")
    return True


def datos_proyecto(g: Guion):
    """{voz, subreddit, usuario, titulo}. Proyecto nuevo -> voz y usuario al azar."""
    d = leer_proyectos().get(g.slug)
    if not d:
        d = {"voz": voz_al_azar(), "subreddit": subreddit_de(g.ruta), "usuario": usuario_al_azar()}
        guardar_proyecto(g.slug, d)
    return {"titulo": g.titulo, **d}


# ──────────────────────────────────────────────────────────────────────────
#  2. Voz con la app Texto a Voz (con caché: si repites, no vuelve a descargar)
# ──────────────────────────────────────────────────────────────────────────

def ffmpeg(*args, cwd=None, duracion=None):
    """Lanza ffmpeg. Con `duracion`, avisa del progreso a `al_progresar`."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats"]
    cmd += [str(a) for a in args]
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, errors="replace", creationflags=SIN_VENTANA)
    errores = []
    for linea in p.stdout:
        if linea.startswith("out_time_us=") and duracion and al_progresar:
            try:
                al_progresar(min(int(linea[12:]) / 1e6 / duracion, 1.0))
            except ValueError:
                pass
        elif not re.match(r"^\w+=", linea):
            errores.append(linea.rstrip())
    if p.wait() != 0:
        raise RuntimeError("ffmpeg falló:\n  " + "\n  ".join(errores[-8:] or [" ".join(cmd)]))


def ffprobe_info(ruta):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height:format=duration", "-of", "json", str(ruta)],
        capture_output=True, text=True, creationflags=SIN_VENTANA)
    try:
        d = json.loads(r.stdout)
        st = d.get("streams", [{}])[0]
        return float(d["format"]["duration"]), int(st.get("width", 0)), int(st.get("height", 0))
    except Exception:
        return 0.0, 0, 0


def motor_voz():
    """El motor de la app Texto a Voz (voz.py en CARPETA_TEXTO_VOZ)."""
    if str(CARPETA_TEXTO_VOZ) not in sys.path:
        sys.path.insert(0, str(CARPETA_TEXTO_VOZ))
    import voz
    return voz


async def _tts_uno(texto, base: Path, voz, velocidad, tono, sem):
    mp3, js = base.with_suffix(".mp3"), base.with_suffix(".json")
    if mp3.exists() and js.exists():
        return
    async with sem:
        for intento in range(4):
            try:
                audio, palabras = await motor_voz().sintetizar(texto, voz, int(velocidad.strip("%")), int(tono.removesuffix("Hz")))
                if not audio:
                    raise RuntimeError("audio vacío")
                mp3.write_bytes(audio)
                js.write_text(json.dumps(palabras, ensure_ascii=False), encoding="utf-8")  # el .json marca la línea como hecha
                return
            except Exception as e:
                if intento == 3:
                    raise RuntimeError(f"Texto a Voz falló con: {texto!r}\n  {e}")
                await asyncio.sleep(1.5 * (intento + 1))


def clave_cache(texto, voz, velocidad, tono):
    return hashlib.sha1(f"{voz}|{velocidad}|{tono}|{texto}".encode("utf-8")).hexdigest()[:20]


def a_wav(base: Path):
    wav = base.with_suffix(".wav")
    if not wav.exists():
        ffmpeg("-i", base.with_suffix(".mp3"), "-ac", "1", "-ar", SR, "-c:a", "pcm_s16le", wav)
    return wav


def muestra_voz(voz, texto, velocidad=VELOCIDAD):
    """Genera (o reutiliza) una frase de prueba y devuelve el .wav."""
    base = CARPETA_CACHE / "tts" / clave_cache(texto, voz, velocidad, TONO)
    base.parent.mkdir(parents=True, exist_ok=True)

    async def uno():
        await _tts_uno(texto, base, voz, velocidad, TONO, asyncio.Semaphore(1))

    asyncio.run(uno())
    return a_wav(base)


def generar_voces(lineas, voz, velocidad, tono):
    dir_tts = CARPETA_CACHE / "tts"
    dir_tts.mkdir(parents=True, exist_ok=True)
    bases = [dir_tts / clave_cache(l.texto_tts, voz, velocidad, tono) for l in lineas]
    pendientes = [(l, b) for l, b in zip(lineas, bases) if not b.with_suffix(".json").exists()]
    if pendientes:
        log(f"🎙️  Generando voz ({len(pendientes)} líneas nuevas, {voz})...")

        async def todo():
            sem = asyncio.Semaphore(TTS_CONCURRENCIA)
            await asyncio.gather(*[_tts_uno(l.texto_tts, b, voz, velocidad, tono, sem) for l, b in pendientes])

        asyncio.run(todo())
    for l, b in zip(lineas, bases):
        wav = a_wav(b)
        with wave.open(str(wav)) as w:
            frames = w.readframes(w.getnframes())
        l.wav = wav
        limites = json.loads(b.with_suffix(".json").read_text(encoding="utf-8"))
        l.pcm, l.limites = compactar(frames, limites)
        l.dur = len(l.pcm) / 2 / SR
        alinear(l)


def compactar(frames: bytes, limites):
    """Quita el silencio del principio y del final de la línea y acorta los silencios internos largos.
    Devuelve el audio nuevo y los tiempos de palabra reajustados."""
    from array import array
    a = array("h")
    a.frombytes(frames)
    if sys.byteorder == "big":
        a.byteswap()
    v = int(SR * 0.01)  # ventanas de 10 ms
    n = len(a) // v
    if n == 0:
        return frames, limites
    voz = []
    for i in range(n):
        trozo = a[i * v:(i + 1) * v]
        voz.append(max(max(trozo), -min(trozo)) > UMBRAL_SILENCIO)
    if not any(voz):
        return frames, limites
    primero = voz.index(True)
    ultimo = n - 1 - voz[::-1].index(True)
    margen = 3  # 30 ms antes y después de la voz
    max_sil = max(int(SILENCIO_MAX_INTERNO / 0.01), 2)
    tramos, ini_tramo, j = [], max(primero - margen, 0), primero
    while j <= ultimo:
        if voz[j]:
            j += 1
            continue
        k = j
        while k <= ultimo and not voz[k]:
            k += 1
        if k - j > max_sil:
            mitad = max_sil // 2
            tramos.append((ini_tramo, j + mitad))
            ini_tramo = k - (max_sil - mitad)
        j = k
    tramos.append((ini_tramo, min(ultimo + 1 + margen, n)))

    def mapear(t):
        w = t / 0.01
        acum = 0
        for s0, s1 in tramos:
            if w < s0:
                return acum * 0.01
            if w <= s1:
                return (acum + w - s0) * 0.01
            acum += s1 - s0
        return acum * 0.01

    pcm = b"".join(frames[s0 * v * 2:s1 * v * 2] for s0, s1 in tramos)
    nuevos = []
    for txt, ini, d in limites:
        a0, a1 = mapear(ini), mapear(ini + d)
        nuevos.append([txt, a0, max(a1 - a0, 0.03)])
    return pcm, nuevos


def alinear(linea: Linea):
    """Asigna a cada palabra del guion su tiempo según los WordBoundary de edge-tts."""
    ps = linea.palabras
    lim = [(norm(t), ini, d) for t, ini, d in linea.limites if norm(t)]
    j = 0
    conocido = [False] * len(ps)
    for i, p in enumerate(ps):
        n = norm(p.texto)
        if not n:
            continue
        for k in range(j, min(j + 4, len(lim))):
            ln = lim[k][0]
            if ln == n or ln.startswith(n) or n.startswith(ln):
                p.ini, p.fin = lim[k][1], lim[k][1] + lim[k][2]
                conocido[i] = True
                j = k + 1
                break
    # Interpolar los que no casan
    anclas = [(-1, 0.05)] + [(i, ps[i].ini) for i in range(len(ps)) if conocido[i]] + [(len(ps), max(linea.dur - 0.1, 0.1))]
    for (a, ta), (b, tb) in zip(anclas, anclas[1:]):
        huecos = list(range(a + 1, b))
        if not huecos:
            continue
        inicio = ps[a].fin if a >= 0 and conocido[a] else ta
        pesos = [max(len(ps[i].texto), 1) for i in huecos]
        total = sum(pesos)
        t = inicio
        span = max(tb - inicio, 0.05 * len(huecos))
        for i, w in zip(huecos, pesos):
            d = span * w / total
            ps[i].ini, ps[i].fin = t, t + d
            t += d


# ──────────────────────────────────────────────────────────────────────────
#  3. Línea de tiempo + audio
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class Colocada:
    linea: Linea
    t: float
    subs: bool = True


def pausa_tras(linea: Linea):
    fin = linea.texto_tts.rstrip(" \"”»'")
    p = PAUSA_LINEA
    if fin.endswith(("…", "...", ":")):
        p += PAUSA_EXTRA_SUSPENSO
    elif fin.endswith("?"):
        p += PAUSA_EXTRA_PREGUNTA
    return p


def construir_linea_tiempo(escenas, intro: Linea = None, final: Linea = None, cola=COLA_NORMAL):
    col, tramos = [], []
    t = 0.0
    if intro is not None:
        col.append(Colocada(intro, 0.25, subs=False))
        t = max(TARJETA_SEG, 0.25 + intro.dur + 0.45)
    else:
        t = 0.15
    for k, esc in enumerate(escenas):
        ini_esc = 0.0 if k == 0 else t
        for i, ln in enumerate(esc.lineas):
            col.append(Colocada(ln, t))
            t += ln.dur
            if i < len(esc.lineas) - 1:
                t += pausa_tras(ln)
        tramos.append([ini_esc, None, esc])
        if k < len(escenas) - 1:
            t += PAUSA_ESCENA
            tramos[-1][1] = t
    fin_voz = t
    if final is not None:
        t += 0.5
        col.append(Colocada(final, t, subs=False))
        t += final.dur
    total = t + cola
    tramos[-1][1] = total
    return col, tramos, fin_voz, total


def escribir_audio(colocadas, total, destino: Path):
    n_total = int(round(total * SR))
    buf = bytearray(n_total * 2)
    for c in colocadas:
        datos = c.linea.pcm
        ini = int(round(c.t * SR)) * 2
        fin = min(ini + len(datos), len(buf))
        buf[ini:fin] = datos[: fin - ini]
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(buf))


# ──────────────────────────────────────────────────────────────────────────
#  4. Subtítulos ASS
# ──────────────────────────────────────────────────────────────────────────

def ts(s):
    s = max(s, 0)
    cs = int(round(s * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    sec, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def esc_ass(s):
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def texto_visible(p: Palabra):
    t = p.texto.strip("\"“”«»'‘’()[]")
    t = t.replace("...", "…").rstrip("…").rstrip(",.;:—–-").rstrip("…")
    t = t.lstrip("—–-")
    if MAYUSCULAS:
        t = t.upper()
    return t


def trocear(palabras):
    """Agrupa palabras en golpes de 2-4 palabras."""
    trozos, actual, chars = [], [], 0
    for p in palabras:
        vis = texto_visible(p)
        if not vis:  # signo suelto ("…", "—"): no se muestra
            continue
        cortar = False
        if actual:
            if len(actual) >= PALABRAS_MAX or chars + 1 + len(vis) > CARACTERES_MAX:
                cortar = True
            elif actual[-1].negrita != p.negrita:
                cortar = True
            elif re.search(r"[.,;:?!…]$", actual[-1].texto.rstrip("\"”»'")):
                cortar = True
        if cortar:
            trozos.append(actual)
            actual, chars = [], 0
        actual.append(p)
        chars += len(vis) + (1 if chars else 0)
    if actual:
        trozos.append(actual)
    # Evita un monosílabo huérfano al final
    if len(trozos) >= 2 and len(trozos[-1]) == 1 and len(texto_visible(trozos[-1][0])) <= 3 \
            and len(trozos[-2]) < PALABRAS_MAX + 1 and trozos[-2][-1].negrita == trozos[-1][0].negrita \
            and not re.search(r"[.?!…]$", trozos[-2][-1].texto):
        huerfano = trozos.pop()
        trozos[-1] += huerfano
    return trozos


def rect_redondeado(w, h, r):
    w, h, r = int(w), int(h), int(r)
    k = int(r * 0.448)
    return (f"m {r} 0 l {w - r} 0 b {w - k} 0 {w} {k} {w} {r} "
            f"l {w} {h - r} b {w} {h - k} {w - k} {h} {w - r} {h} "
            f"l {r} {h} b {k} {h} 0 {h - k} 0 {h - r} "
            f"l 0 {r} b 0 {k} {k} 0 {r} 0")


def flecha(s):
    pts = [(30, 0), (70, 0), (70, 55), (100, 55), (50, 110), (0, 55), (30, 55)]
    pts = [(int(x * s), int(y * s)) for x, y in pts]
    return "m " + " l ".join(f"{x} {y}" for x, y in pts)


def envolver(texto, max_chars):
    lineas, actual = [], ""
    for w in texto.split():
        if actual and len(actual) + 1 + len(w) > max_chars:
            lineas.append(actual)
            actual = w
        else:
            actual = f"{actual} {w}".strip()
    if actual:
        lineas.append(actual)
    return lineas


class ASS:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.vertical = H > W
        self.fs = 92 if self.vertical else 86
        self.eventos = []

    def ev(self, capa, ini, fin, estilo, texto):
        if fin - ini < 0.02:
            return
        self.eventos.append(f"Dialogue: {capa},{ts(ini)},{ts(fin)},{estilo},,0,0,0,,{texto}")

    def cabecera(self):
        W, H, fs = self.W, self.H, self.fs
        return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{FUENTE_SUBS},{fs},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{7 if self.vertical else 6},3,5,70,70,0,1
Style: Caja,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Tarjeta,{FUENTE_TARJETA},50,&H00141414,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Grande,{FUENTE_SUBS},120,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,8,4,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # ── subtítulos palabra a palabra ─────────────────────────────────────
    def subtitulos(self, colocadas):
        cx = self.W // 2
        cy = int(self.H * (0.60 if self.vertical else 0.72))
        visibles = [c for c in colocadas if c.subs]
        for idx, c in enumerate(visibles):
            siguiente = visibles[idx + 1].t if idx + 1 < len(visibles) else c.t + c.linea.dur + 1.0
            trozos = trocear(c.linea.palabras)
            for k, tr in enumerate(trozos):
                ini = c.t + tr[0].ini
                if k + 1 < len(trozos):
                    fin = c.t + trozos[k + 1][0].ini
                else:
                    fin = min(c.t + tr[-1].fin + 0.4, siguiente - 0.03)
                partes = []
                for p in tr:
                    vis = esc_ass(texto_visible(p))
                    if not vis:
                        continue
                    partes.append(f"{{\\1c{COLOR_CLAVE}}}{vis}{{\\1c&H00FFFFFF&}}" if p.clave else vis)
                if not partes:
                    continue
                texto = " ".join(partes)
                if any(p.negrita for p in tr):
                    anim = r"\fscx70\fscy70\t(0,90,\fscx128\fscy128)\t(90,220,\fscx112\fscy112)"
                else:
                    anim = r"\fscx86\fscy86\t(0,80,\fscx100\fscy100)"
                self.ev(1, ini, fin, "Sub", f"{{\\an5\\pos({cx},{cy}){anim}}}{texto}")

    # ── tarjeta: post de Reddit ──────────────────────────────────────────
    def tarjeta(self, titulo, subreddit, autor, ini, fin):
        W, H = self.W, self.H
        cw = int(W * 0.86) if self.vertical else int(W * 0.52)
        pad = 40 if self.vertical else 34
        fs = 52 if self.vertical else 46
        av = 76 if self.vertical else 64
        max_chars = max(12, int((cw - 2 * pad) / (fs * 0.52)))
        lineas = envolver(titulo, max_chars)
        lh = int(fs * 1.2)
        ch = pad + av + 22 + len(lineas) * lh - (lh - fs) + pad
        x0 = (W - cw) // 2
        y0 = int(H * 0.30) if self.vertical else (H - ch) // 2 - int(H * 0.04)
        fad = r"\fad(180,220)"

        def mov(x, y):
            return f"\\move({x},{y + 40},{x},{y},0,220)"

        def forma(capa, x, y, color, dibujo, extra=""):
            self.ev(capa, ini, fin, "Caja", f"{{\\an7{mov(x, y)}{fad}\\1c{color}{extra}\\p1}}{dibujo}{{\\p0}}")

        def texto(an, x, y, fs_, t, extra=""):
            self.ev(9, ini, fin, "Tarjeta", f"{{\\an{an}{mov(x, y)}{fad}\\fs{fs_}{extra}}}{esc_ass(t)}")

        # sombra + caja
        forma(5, x0 + 6, y0 + 12, "&H000000&", rect_redondeado(cw, ch, 30), r"\1a&H90&\blur10")
        forma(6, x0, y0, "&HFFFFFF&", rect_redondeado(cw, ch, 30))
        # avatar estilo Reddit: círculo naranja con una carita blanca
        ax, ay = x0 + pad, y0 + pad
        cara_w, cara_h, ojo = int(av * 0.64), int(av * 0.42), max(av // 9, 4)
        forma(7, ax, ay, "&H0045FF&", rect_redondeado(av, av, av / 2))
        forma(8, ax + (av - cara_w) // 2, ay + int(av * 0.36), "&HFFFFFF&", rect_redondeado(cara_w, cara_h, cara_h / 2))
        forma(8, ax + int(av * 0.56), ay + int(av * 0.12), "&HFFFFFF&", rect_redondeado(ojo * 1.4, ojo * 1.4, ojo * 0.7))
        for ox in (0.36, 0.64):
            forma(9, ax + int(av * ox) - ojo // 2, ay + int(av * 0.48), "&H0045FF&", rect_redondeado(ojo, ojo, ojo / 2))
        # cabecera: r/subreddit, u/usuario · hace X h, menú "•••"
        tx = ax + av + 20
        texto(7, tx, ay + 2, int(fs * 0.66), subreddit)
        texto(7, tx, ay + int(av * 0.54), int(fs * 0.56), autor, r"\b0\1c&H7C7C7C&")
        texto(9, x0 + cw - pad, ay - 4, int(fs * 0.7), "•••", r"\1c&H8C8C8C&")
        # título del post
        y = ay + av + 22
        for l in lineas:
            texto(7, x0 + pad, y, fs, l)
            y += lh

    def pastilla(self, texto, ini, fin, y=None, fs=None):
        W, H = self.W, self.H
        fs = fs or (46 if self.vertical else 40)
        y = y or int(H * (0.085 if self.vertical else 0.05))
        w = int(len(texto) * fs * 0.62) + 60
        h = int(fs * 1.6)
        self.ev(3, ini, fin, "Caja", f"{{\\an7\\pos({(W - w) // 2},{y})\\fad(200,200)\\1c&H000000&\\1a&H50&\\p1}}{rect_redondeado(w, h, h / 2)}{{\\p0}}")
        self.ev(4, ini, fin, "Tarjeta", f"{{\\an5\\pos({W // 2},{y + h // 2})\\fad(200,200)\\fs{fs}\\1c&HFFFFFF&}}{esc_ass(texto)}")

    def comenta(self, ini, fin):
        W, H = self.W, self.H
        y = int(H * (0.26 if self.vertical else 0.25))
        pulso = "".join(
            f"\\t({i * 600},{i * 600 + 300},\\fscx112\\fscy112)\\t({i * 600 + 300},{i * 600 + 600},\\fscx100\\fscy100)"
            for i in range(int((fin - ini) / 0.6) + 1))
        self.ev(9, ini, fin, "Grande", f"{{\\an5\\pos({W // 2},{y})\\fad(200,0)\\1c{COLOR_CLAVE}{pulso}}}¡COMENTA!")
        s = 0.9 if self.vertical else 0.75
        self.ev(9, ini, fin, "Caja", f"{{\\an8\\pos({W // 2},{y + 90})\\fad(200,0)\\1c{COLOR_CLAVE}\\3c&H000000&\\bord6\\p1}}{flecha(s)}{{\\p0}}")

    def final_corte(self, lineas_txt, ini, fin):
        W, H = self.W, self.H
        self.ev(20, ini, fin, "Caja", f"{{\\an7\\pos(0,0)\\fad(300,0)\\1c&H000000&\\1a&H38&\\p1}}m 0 0 l {W} 0 l {W} {H} l 0 {H}{{\\p0}}")
        y = int(H * 0.40)
        tam = [150, 96, 70] if self.vertical else [140, 90, 64]
        colores = [COLOR_CLAVE, "&H00FFFFFF&", "&H00FFFFFF&"]
        for i, t in enumerate(lineas_txt):
            fs = tam[min(i, 2)]
            self.ev(21, ini + 0.1 * i, fin, "Grande",
                    f"{{\\an5\\pos({W // 2},{y})\\fad(250,0)\\fs{fs}\\1c{colores[min(i, 2)]}\\fscx70\\fscy70\\t(0,200,\\fscx100\\fscy100)}}{esc_ass(t)}")
            y += int(fs * 1.25)

    def guardar(self, ruta: Path):
        ruta.write_text(self.cabecera() + "\n".join(self.eventos) + "\n", encoding="utf-8-sig")


def escribir_srt(colocadas, ruta: Path):
    out, n = [], 0
    for c in colocadas:
        if not c.subs:
            continue
        n += 1
        a = c.t + c.linea.palabras[0].ini
        b = c.t + c.linea.dur

        def f(s):
            ms = int(round(s * 1000))
            h, ms = divmod(ms, 3600000)
            m, ms = divmod(ms, 60000)
            s2, ms = divmod(ms, 1000)
            return f"{h:02d}:{m:02d}:{s2:02d},{ms:03d}"
        out.append(f"{n}\n{f(a)} --> {f(b)}\n{c.linea.texto_tts}\n")
    ruta.write_text("\n".join(out), encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────
#  5. Fondos y montaje con ffmpeg
# ──────────────────────────────────────────────────────────────────────────

_info_cache = {}


def info_clip(p):
    if p not in _info_cache:
        _info_cache[p] = ffprobe_info(p)
    return _info_cache[p]


def clips_de(etiqueta):
    d = CARPETA_FONDOS / etiqueta
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.suffix.lower() in EXT_VIDEO)


def todos_los_clips():
    if not CARPETA_FONDOS.is_dir():
        return []
    return sorted(p for p in CARPETA_FONDOS.rglob("*") if p.suffix.lower() in EXT_VIDEO)


def elegir_clip(etiqueta, rng, ultimo):
    clips = clips_de(etiqueta) or todos_los_clips()
    if not clips:
        return None
    largos = [c for c in clips if info_clip(c)[0] >= VIDEO_LARGO_MIN]
    if largos:  # vídeo largo: se sigue usando el mismo (otro trozo) en vez de cambiar de archivo
        return ultimo if ultimo in largos else rng.choice(largos)
    opciones = [c for c in clips if c != ultimo] or clips
    return rng.choice(opciones)


def tramos_de_fondo(tramos, total, rng, vertical, tema=None):
    """Cambia de clip cada DURACION_FONDO_* (no en cada escena). Devuelve [(ini, fin, carpeta)].
    Shorts: todos los clips de una misma temática (la que diga la nota, la primera escena con clips o una al azar).
    YouTube: la carpeta la marca la escena en curso."""
    if vertical:
        tema = tema if tema and clips_de(tema) else next((e.etiqueta for _, _, e in tramos if clips_de(e.etiqueta)), None)
        tema = tema or rng.choice([e for e in ETIQUETAS if clips_de(e)] or [""])
    out, t = [], 0.0
    while t < total - 0.01:
        fin = min(t + (DURACION_FONDO_VERTICAL if vertical else DURACION_FONDO_HORIZONTAL), total)
        if total - fin < 5:  # sin trozo final de pocos segundos
            fin = total
        out.append((t, fin, tema if vertical else next((e for a, b, e in tramos if a <= t < b), tramos[-1][2]).etiqueta))
        t = fin
    return out


# Solo NVIDIA: con una AMD (RX 6600, h264_amf) el montaje iba más lento que con el procesador (82 s frente a 50 s),
# porque lo que pesa son los filtros (desenfoque, subtítulos), no la codificación.
CODEC_GPU = ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "21", "-b:v", "0"]
_nvenc = None


def hay_nvenc():
    """¿Puede ffmpeg codificar con una gráfica NVIDIA en este PC? (se comprueba una vez)"""
    global _nvenc
    if _nvenc is None:
        _nvenc = shutil.which("ffmpeg") is not None and subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=s=640x360", "-frames:v", "5",
             *CODEC_GPU, "-f", "null", "-"], capture_output=True, creationflags=SIN_VENTANA).returncode == 0
    return _nvenc


def montar(nombre, W, H, tramos, voz_wav: Path, ass_path: Path, total, salida: Path,
           musica=None, rng=None, gpu=False, rapido=False, tema=None):
    trabajo = ass_path.parent
    tramos = tramos_de_fondo(tramos, total, rng, H > W, tema)
    relleno = RELLENO_VERTICAL if H > W else RELLENO_HORIZONTAL
    if rapido:
        W, H = (W // 2) // 2 * 2, (H // 2) // 2 * 2
    entradas, filtros, etiquetas_v = [], [], []
    ultimo = None
    siguiente = {}  # vídeo largo -> por dónde seguir, para no repetir trozos
    for i, (ini, fin, etiqueta) in enumerate(tramos):
        dur = fin - ini
        clip = elegir_clip(etiqueta, rng, ultimo)
        ultimo = clip
        if clip is None:
            entradas += ["-f", "lavfi", "-t", f"{dur + 0.5:.3f}", "-i", f"color=c=0x1d1f2b:s={W}x{H}:r={FPS}"]
            filtros.append(f"[{i}:v]setsar=1,trim=duration={dur:.3f},setpts=PTS-STARTPTS,format=yuv420p[v{i}]")
        else:
            cd, cw, chh = info_clip(clip)
            inicio = rng.uniform(0, cd - dur - 0.5) if cd > dur + 1 else (rng.uniform(0, max(cd - 1, 0)) if cd > 2 else 0)
            if cd >= VIDEO_LARGO_MIN:
                inicio = siguiente.get(clip, inicio)
                if inicio + dur + 0.5 > cd:
                    inicio = 0.0
                siguiente[clip] = inicio + dur + 1
            entradas += ["-stream_loop", "-1", "-ss", f"{inicio:.2f}", "-t", f"{dur + 0.5:.3f}", "-i", str(clip)]
            asp_clip = (cw / chh) if cw and chh else W / H
            asp_obj = W / H
            if relleno == "desenfocado" and max(asp_clip, asp_obj) / min(asp_clip, asp_obj) > 1.45:
                # Formato muy distinto (p. ej. clip vertical en vídeo 16:9): relleno desenfocado
                filtros.append(
                    f"[{i}:v]split=2[a{i}][b{i}];"
                    f"[a{i}]scale={W // 4}:{H // 4}:force_original_aspect_ratio=increase,crop={W // 4}:{H // 4},boxblur=12:2,scale={W}:{H},eq=brightness=-0.08[f{i}];"
                    f"[b{i}]scale={W}:{H}:force_original_aspect_ratio=decrease[c{i}];"
                    f"[f{i}][c{i}]overlay=(W-w)/2:(H-h)/2,setsar=1,fps={FPS},trim=duration={dur:.3f},setpts=PTS-STARTPTS,format=yuv420p[v{i}]")
            else:
                filtros.append(
                    f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS},"
                    f"eq=saturation=1.12,trim=duration={dur:.3f},setpts=PTS-STARTPTS,format=yuv420p[v{i}]")
        etiquetas_v.append(f"[v{i}]")
    n = len(tramos)
    fontsdir = ""
    if CARPETA_FUENTES.is_dir() and any(CARPETA_FUENTES.iterdir()):
        rel = os.path.relpath(CARPETA_FUENTES, trabajo).replace("\\", "/")
        fontsdir = f":fontsdir={rel}"
    filtros.append(f"{''.join(etiquetas_v)}concat=n={n}:v=1:a=0[bg];[bg]ass={ass_path.name}{fontsdir}[v]")

    entradas += ["-i", str(voz_wav)]
    iv = n
    if musica:
        entradas += ["-stream_loop", "-1", "-i", str(musica)]
        im = n + 1
        filtros.append(
            f"[{iv}:a]aresample=48000,asplit=2[vz][vs];"
            f"[{im}:a]aresample=48000,volume={VOLUMEN_MUSICA},atrim=duration={total:.3f}[m];"
            f"[m][vs]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=400[md];"
            f"[vz][md]amix=inputs=2:duration=first:normalize=0,afade=t=out:st={max(total - 1.5, 0):.3f}:d=1.5[a]")
    else:
        filtros.append(f"[{iv}:a]aresample=48000[a]")

    codec = CODEC_GPU if gpu else ["-c:v", "libx264", "-preset", "ultrafast" if rapido else PRESET, "-crf", str(CRF)]

    grafo = ";".join(filtros)
    (trabajo / "filtros.txt").write_text(grafo, encoding="utf-8")  # solo para depurar
    salida.parent.mkdir(parents=True, exist_ok=True)
    log(f"🎬 Montando {nombre} ({W}x{H}, {total:.1f} s)...")
    ffmpeg(*entradas, "-filter_complex", grafo, "-map", "[v]", "-map", "[a]",
           *codec, "-pix_fmt", "yuv420p", "-r", FPS, "-c:a", "aac", "-b:a", "192k",
           "-t", f"{total:.3f}", "-movflags", "+faststart", salida.resolve(),
           cwd=trabajo, duracion=total)


# ──────────────────────────────────────────────────────────────────────────
#  6. Programa principal
# ──────────────────────────────────────────────────────────────────────────

def guiones_de(carpeta: Path):
    """Notas .md y textos .txt de la carpeta, el más reciente primero."""
    if not carpeta.is_dir():
        return []
    return sorted((p for p in carpeta.iterdir() if p.suffix.lower() in (".md", ".txt")),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def ultimo_guion():
    return next(iter(guiones_de(CARPETA_GUIONES)), None)


def preparar_carpetas():
    for e in ETIQUETAS:
        (CARPETA_FONDOS / e).mkdir(parents=True, exist_ok=True)
    CARPETA_MUSICA.mkdir(parents=True, exist_ok=True)
    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)


def resumen(g: Guion):
    log(f"\n📄 {g.ruta.name}")
    log(f"   Título tarjeta: {g.titulo}")
    for e in g.escenas:
        aviso = "  ⚠️ sin clips en esa carpeta" if e.etiqueta and not clips_de(e.etiqueta) else ""
        log(f"   Escena {e.num:>2} {('· ' + e.titulo[:34]) if e.titulo else '':<36} [{e.etiqueta or '—'}] {len(e.lineas)} líneas"
            f"{'  claves: ' + ', '.join(e.claves) if e.claves else ''}{aviso}")
    if g.cortes and g.cortes[0].lineas:
        seq, t = linea_de_tiempo_estimada(g.escenas)
        log(f"   ✂️  Cortes automáticos (~{mmss(t[-1])} de voz en total):")
        for c in g.cortes:
            a, b = seq[c.lineas[0]][0].texto_tts, seq[c.lineas[1] - 1][0].texto_tts
            log(f"   ✂️  Short {c.parte}/{c.total} · ~{mmss(c.seg)} · «{a[:38]}…» → «…{b[-60:]}»"
                + (f"  [{c.fondo}]" if c.fondo else ""))
        resto = t[-1] - t[g.cortes[-1].lineas[1]]
        if resto > 1:
            log(f"   🎬 Solo en YouTube: el final (~{mmss(resto)})")
    elif g.cortes:
        for c in g.cortes:
            log(f"   ✂️  Short {c.parte}/{c.total}: escenas {c.desde}→{c.hasta}" + (f"  [{c.fondo}]" if c.fondo else ""))
        if fuera := solo_youtube(g):
            log(f"   🎬 Solo en YouTube (así lo dice el «Mapa de cortes»): escena{'s' * (len(fuera) > 1)} {lista(fuera)}")
    else:
        log("   ⚠️ No encuentro 'Mapa de cortes': solo se hará el vídeo de YouTube.")
    log("")


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Guion de Obsidian → vídeos de historias de Reddit")
    ap.add_argument("guion", nargs="?", help="Ruta al .md o .txt (por defecto, el último de la carpeta de guiones)")
    ap.add_argument("--solo", default="todo", help="todo | youtube | cortes | parte1 | parte2 ...")
    ap.add_argument("--voz", help="por defecto, la voz al azar que se eligió para este proyecto")
    ap.add_argument("--velocidad", default=VELOCIDAD, help='p. ej. "+10%%"')
    ap.add_argument("--musica", help="archivo de música (si no, una al azar de /musica)")
    ap.add_argument("--sin-musica", action="store_true")
    ap.add_argument("--gpu", action="store_true", help="codificar con NVIDIA NVENC")
    ap.add_argument("--rapido", action="store_true", help="prueba a media resolución")
    ap.add_argument("--semilla", type=int, default=None, help="fija la elección de fondos")
    ap.add_argument("--analizar", action="store_true", help="solo muestra lo que ha entendido del guion")
    a = ap.parse_args(argv)

    preparar_carpetas()
    ruta = Path(a.guion) if a.guion else ultimo_guion()
    if not ruta or not ruta.exists():
        sys.exit(f"❌ No encuentro el guion. Pásalo como argumento o revisa CARPETA_GUIONES:\n   {CARPETA_GUIONES}")

    g = parsear_guion(ruta)
    if not g.escenas:
        sys.exit("❌ No he encontrado texto que narrar en esa nota.")
    proyecto = datos_proyecto(g)
    g.titulo = proyecto["titulo"]
    voz = a.voz or proyecto["voz"]
    autor = f"{proyecto['usuario']} • {random.Random(g.slug).randint(2, 23)} h"
    resumen(g)
    log(f"   Voz: {VOCES.get(voz, '')} ({voz}) · Post: {proyecto['subreddit']} · {proyecto['usuario']}\n")
    if a.analizar:
        return

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        sys.exit("❌ Falta ffmpeg. En Windows: winget install Gyan.FFmpeg  (y abre una terminal nueva)")
    try:
        motor_voz()
    except ImportError:
        sys.exit(f"❌ No encuentro la app Texto a Voz (voz.py) en {CARPETA_TEXTO_VOZ}, o le falta edge-tts:\n"
                 "   ajusta CARPETA_TEXTO_VOZ o ejecuta  pip install edge-tts")
    if not todos_los_clips():
        log("⚠️  No hay clips en /fondos: se usará un fondo liso. Mete vídeos en fondos/JABON, fondos/SLIME, ...\n")
    if a.gpu and not hay_nvenc():
        log("⚠️  Este PC no tiene una gráfica NVIDIA que codifique vídeo: uso el procesador.\n")
        a.gpu = False

    musica = None
    if not a.sin_musica:
        if a.musica:
            musica = Path(a.musica)
        elif MUSICA_AUTOMATICA:
            pistas = [p for p in CARPETA_MUSICA.glob("*") if p.suffix.lower() in EXT_AUDIO]
            musica = random.choice(pistas) if pistas else None
        if musica:
            log(f"🎵 Música: {musica.name}")

    # Voz de todas las líneas (+ título y llamada final)
    intro = Linea(g.titulo, parsear_linea_narracion(g.titulo)[1])
    cta = Linea(VOZ_FINAL_CORTE, parsear_linea_narracion(VOZ_FINAL_CORTE)[1]) if VOZ_FINAL_CORTE else None
    todas = [l for e in g.escenas for l in e.lineas] + [intro] + ([cta] if cta else [])
    generar_voces(todas, voz, a.velocidad, TONO)
    if g.cortes and g.cortes[0].lineas:  # automáticos: se ajustan a la voz real (que ningún short pase de 3 min)
        g.cortes = cortes_automaticos(g.escenas, g.slug)
        log("✂️  Con la voz real: " + ", ".join(f"parte {c.parte} {mmss(c.seg)}" for c in g.cortes))

    semilla = a.semilla if a.semilla is not None else random.randrange(10 ** 6)
    solo = a.solo.lower().replace(" ", "")
    carpeta = CARPETA_SALIDA / g.slug
    hechos, partes_hechas, youtube_hecho = [], set(), False

    # ── Vídeo completo YouTube (16:9) ─────────────────────────────────────
    if solo in ("todo", "youtube"):
        W, H = FORMATOS["horizontal"]
        col, tramos, fin_voz, total = construir_linea_tiempo(
            g.escenas, intro=intro if LEER_TITULO_YOUTUBE else None, cola=COLA_NORMAL + 0.8)
        trabajo = CARPETA_CACHE / "trabajo" / f"{g.slug}_youtube"
        trabajo.mkdir(parents=True, exist_ok=True)
        ass = ASS(W, H)
        ass.tarjeta(g.titulo, proyecto["subreddit"], autor, 0,
                    TARJETA_SEG if not LEER_TITULO_YOUTUBE else col[1].t - 0.1)
        ass.subtitulos(col)
        ass.comenta(max(fin_voz - COMENTA_SEG, 0), total)
        ass.guardar(trabajo / "subs.ass")
        escribir_audio(col, total, trabajo / "voz.wav")
        salida = carpeta / f"{g.slug} - YouTube.mp4"
        montar("YouTube 16:9", W, H, tramos, trabajo / "voz.wav", trabajo / "subs.ass", total, salida,
               musica, random.Random(semilla), a.gpu, a.rapido)
        escribir_srt(col, salida.with_suffix(".srt"))
        hechos.append(salida)
        youtube_hecho = True

    # ── Cortes TikTok / Reels / Shorts (9:16) ─────────────────────────────
    for c in g.cortes:
        if solo not in ("todo", "cortes", f"parte{c.parte}"):
            continue
        W, H = FORMATOS["vertical"]
        escenas = escenas_del_corte(g, c)
        if not escenas:
            log(f"⚠️  Short {c.parte}: no hay escenas {c.desde}→{c.hasta}")
            continue
        ultimo = c.parte == c.total
        col, tramos, fin_voz, total = construir_linea_tiempo(
            escenas, final=cta if ultimo else None, cola=COLA_FINAL_CORTE if ultimo else COLA_NORMAL)
        trabajo = CARPETA_CACHE / "trabajo" / f"{g.slug}_parte{c.parte}"
        trabajo.mkdir(parents=True, exist_ok=True)
        ass = ASS(W, H)
        ass.tarjeta(g.titulo, proyecto["subreddit"], autor, 0, TARJETA_SEG)
        ass.subtitulos(col)
        if ultimo:
            ass.final_corte(TEXTO_FINAL_CORTE, fin_voz + 0.2, total)
        elif TEXTO_SIGUIENTE:
            ass.pastilla(TEXTO_SIGUIENTE, max(total - SIGUIENTE_PARTE_SEG, 0), total, y=int(H * 0.30), fs=58)
        ass.guardar(trabajo / "subs.ass")
        escribir_audio(col, total, trabajo / "voz.wav")
        salida = carpeta / f"{g.slug} - Parte {c.parte}de{c.total}.mp4"
        montar(f"Short {c.parte}/{c.total} 9:16", W, H, tramos, trabajo / "voz.wav", trabajo / "subs.ass",
               total, salida, musica, random.Random(semilla + c.parte * 101), a.gpu, a.rapido, c.fondo)
        hechos.append(salida)
        partes_hechas.add(c.parte)

    if hechos and not a.rapido:  # las pruebas rápidas no cuentan como clip hecho
        marcar_en_obsidian(g.ruta, partes_hechas, youtube_hecho)
    if hechos:
        log("\n✅ Listo:")
        for h in hechos:
            log(f"   {h}")
        log(f"   (semilla de fondos: {semilla} — usa --semilla {semilla} para repetir los mismos)")
    else:
        log("Nada que hacer con --solo " + a.solo)


if __name__ == "__main__":
    main()
