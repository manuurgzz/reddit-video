"""Motor de voz de Texto a Voz (voces neuronales de Microsoft Edge vía edge-tts).

Lo usan la web (server.py) y otras apps, como Reddit Video. Solo depende de edge-tts.
"""
import edge_tts


async def sintetizar(texto, voz, velocidad=0, tono=0):
    """Devuelve el MP3 y [(palabra, inicio_s, duración_s)] de cada palabra dicha.
    velocidad en % (-50…100) y tono en Hz (-50…50). ValueError si la voz no es válida."""
    com = edge_tts.Communicate(texto, voz, rate=f"{velocidad:+d}%", pitch=f"{tono:+d}Hz", boundary="WordBoundary")
    audio, palabras = bytearray(), []
    async for trozo in com.stream():
        if trozo["type"] == "audio":
            audio += trozo["data"]
        elif trozo["type"] == "WordBoundary":
            palabras.append((trozo["text"], trozo["offset"] / 1e7, trozo["duration"] / 1e7))
    return bytes(audio), palabras
