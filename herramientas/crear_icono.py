"""Genera assets/icono.ico (varios tamaños) y assets/icono.png: círculo naranja con un «play» blanco.
Solo hace falta ejecutarlo si se cambia el diseño:  python herramientas/crear_icono.py"""
from pathlib import Path

from PIL import Image, ImageDraw

SALIDA = Path(__file__).resolve().parent.parent / "assets"
NARANJA = (255, 69, 0, 255)


def dibujar(n=1024):
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, n - 1, n - 1), fill=NARANJA)
    # triángulo de «play», algo a la derecha para que parezca centrado
    x0, x1, h = n * 0.385, n * 0.80, n * 0.50
    d.polygon([(x0, n * 0.5 - h / 2), (x1, n * 0.5), (x0, n * 0.5 + h / 2)], fill="white")
    return img


if __name__ == "__main__":
    SALIDA.mkdir(exist_ok=True)
    grande = dibujar()
    grande.resize((256, 256), Image.LANCZOS).save(SALIDA / "icono.png")
    grande.save(SALIDA / "icono.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print("Iconos creados en", SALIDA)
