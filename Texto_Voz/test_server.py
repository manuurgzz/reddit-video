"""Comprobación rápida del servidor: python test_server.py (necesita internet para la parte de voz)."""
import asyncio

from aiohttp.test_utils import TestClient, TestServer

from server import app


async def main():
    async with TestClient(TestServer(app)) as client:
        res = await client.post("/api/tts", json={"text": "   ", "voice": "es-ES-ElviraNeural"})
        assert res.status == 400, res.status

        res = await client.post("/api/tts", json={"text": "hola", "voice": "no valida"})
        assert res.status == 400, res.status

        text = "Hola, ¿qué tal? Esto es una prueba & algo más."
        res = await client.post("/api/tts", json={"text": text, "voice": "es-ES-ElviraNeural", "rate": 10})
        assert res.status == 200, await res.text()
        data = await res.json()
        assert len(data["audio"]) > 1000
        spoken = [text[s:e] for _, s, e in data["words"]]
        assert spoken[:3] == ["Hola", "qué", "tal"], spoken
        assert all(a[0] <= b[0] for a, b in zip(data["words"], data["words"][1:])), "tiempos desordenados"
        print("OK:", len(spoken), "palabras con tiempo")


asyncio.run(main())
