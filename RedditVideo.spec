# PyInstaller: carpeta con Reddit Video.exe (sin consola). Se lanza desde construir.ps1.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

datas = [("assets", "assets"), ("docs", "docs"), ("guiones", "guiones")]
if Path("build/ffmpeg/ffmpeg.exe").exists():   # lo deja construir.ps1
    datas.append(("build/ffmpeg", "ffmpeg"))

a = Analysis(
    ["app.pyw"],
    pathex=["Texto_Voz"],   # el motor de voz (voz.py) se importa con sys.path, PyInstaller no lo vería solo
    datas=datas,
    hiddenimports=["voz", *collect_submodules("edge_tts")],
    excludes=["pytest", "unittest", "pydoc", "test", "pydantic", "pydantic_core", "setuptools", "pkg_resources"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Reddit Video", console=False, icon="assets/icono.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="Reddit Video")
