"""Texto a Voz: sirve la web y genera audio MP3 con las voces neuronales de Microsoft Edge (edge-tts).

Uso:  python server.py   ->  http://localhost:8000
"""
import base64
import os
import webbrowser
from pathlib import Path

import edge_tts
from aiohttp import web

from voz import sintetizar

ROOT = Path(__file__).parent
HOST = os.environ.get("HOST", "127.0.0.1")  # 0.0.0.0 al desplegar en un servidor
PORT = int(os.environ.get("PORT", 8000))
MAX_CHARS = 10_000

_voices_cache = None  # la lista de voces apenas cambia: se pide una vez por arranque


def error(status, message):
    return web.json_response({"error": message}, status=status)


async def index(_request):
    return web.FileResponse(ROOT / "index.html")


async def voices(_request):
    global _voices_cache
    if _voices_cache is None:
        try:
            raw = await edge_tts.list_voices()
        except Exception as exc:
            return error(502, f"No se pudo descargar la lista de voces ({exc}). Comprueba tu conexión a internet.")
        _voices_cache = [
            {"id": v["ShortName"], "locale": v["Locale"], "gender": v["Gender"]}
            for v in raw
        ]
    return web.json_response(_voices_cache)


async def tts(request):
    try:
        body = await request.json()
        text = str(body.get("text", "")).strip()
        voice = str(body.get("voice", ""))
        rate = max(-50, min(100, int(body.get("rate", 0))))
        pitch = max(-50, min(50, int(body.get("pitch", 0))))
    except (ValueError, TypeError, AttributeError):
        return error(400, "Petición mal formada.")

    if not text:
        return error(400, "Escribe algún texto antes de generar el audio.")
    if len(text) > MAX_CHARS:
        return error(413, f"El texto supera el máximo de {MAX_CHARS:,} caracteres.".replace(",", "."))

    try:
        audio, palabras = await sintetizar(text, voice, rate, pitch)
    except ValueError:
        return error(400, "La voz seleccionada no es válida.")
    except edge_tts.exceptions.NoAudioReceived:
        return error(422, "El servicio no devolvió audio. Prueba con otra voz o revisa el texto.")
    except Exception as exc:
        return error(502, f"El servicio de voz no respondió ({exc}). Comprueba tu conexión e inténtalo de nuevo.")

    words = []  # [segundo de inicio, índice inicial, índice final] de cada palabra en el texto
    cursor = 0
    for palabra, inicio, _ in palabras:
        start = text.find(palabra, cursor)
        if start == -1:  # palabra normalizada por el servicio: se omite el resaltado
            continue
        cursor = start + len(palabra)
        words.append([inicio, start, cursor])

    return web.json_response({"audio": base64.b64encode(audio).decode(), "words": words})


app = web.Application(client_max_size=1024 * 1024)
app.add_routes([
    web.get("/", index),
    web.get("/api/voices", voices),
    web.post("/api/tts", tts),
])

if __name__ == "__main__":
    url = f"http://localhost:{PORT}"
    print(f"Texto a Voz en {url}  (Ctrl+C para salir)")
    if not os.environ.get("NO_BROWSER"):
        webbrowser.open(url)
    web.run_app(app, host=HOST, port=PORT, print=None)
