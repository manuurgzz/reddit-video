"""Comprobaciones de que la app no se cuelga ni se satura:  python test_robustez.py"""
import json
import tempfile
import threading
import time
from importlib.machinery import SourceFileLoader
from pathlib import Path

import guion_a_video as gv

tmp = Path(tempfile.mkdtemp())

# 1 · Cancelar corta ffmpeg en segundos y no deja un .mp4 a medias
salida = tmp / "largo.mp4"
gv.cancelar_ya.clear()
threading.Timer(2, gv.cancelar).start()
inicio = time.monotonic()
try:
    gv.ffmpeg("-re", "-f", "lavfi", "-i", "testsrc=s=320x240:r=30", "-t", "120", salida)
    raise AssertionError("ffmpeg debía cancelarse")
except gv.Cancelado:
    pass
assert time.monotonic() - inicio < 10, "cancelar tardó demasiado"
assert not salida.exists(), "quedó un vídeo a medias"
assert not gv._procesos, "quedó un ffmpeg vivo"
gv.cancelar_ya.clear()

# 2 · Escritura atómica: sin restos .tmp y el contenido nuevo reemplaza al viejo
datos = tmp / "ajustes.json"
gv.guardar_json(datos, {"a": 1})
gv.guardar_json(datos, {"a": 2})
assert json.loads(datos.read_text(encoding="utf-8")) == {"a": 2}
assert not list(tmp.glob("*.tmp"))

# 3 · La ventana pinta por tandas aunque lleguen decenas de miles de mensajes y el registro tiene tope
app = SourceFileLoader("app_rv", str(Path(__file__).with_name("app.pyw"))).load_module()
v = app.App()
for i in range(30000):
    v.q.put(("log", f"línea {i}"))
v.update()
turnos = 0
while not v.q.empty():
    antes = v.q.qsize()
    v.bucle()   # un turno a mano (reprograma el siguiente con after, que aquí no se espera)
    assert antes - v.q.qsize() <= app.MENSAJES_POR_TURNO
    turnos += 1
lineas = int(v.texto.index("end-1c").split(".")[0])
assert lineas <= app.MAX_LINEAS_LOG + 1, lineas
v.destroy()
print(f"OK · cancelar a los {time.monotonic() - inicio:.0f} s · {turnos} turnos para 30000 mensajes · registro limitado a {lineas} líneas")
