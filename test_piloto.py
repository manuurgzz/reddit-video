"""Comprueba el piloto automático sin conexión (Gemini, YouTube y TikTok simulados). Uso: python test_piloto.py"""
import json
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import automatizar as au
import guion_a_video as gv

sys.stdout.reconfigure(encoding="utf-8")
tmp = Path(tempfile.mkdtemp())
try:
    vault = tmp / "boveda"
    (vault / "00_Sistema").mkdir(parents=True)
    (vault / "01_Historias").mkdir()
    (vault / "01_Historias" / "2026-10-01_P007_la-reforma.md").write_text("---\nestado: pendiente\n---\n", encoding="utf-8")
    (vault / "00_Sistema" / "Registro.md").write_text(
        "# Registro\n\n| ID | Título | Subreddit | Fecha | Estado | Historia | Clips | Nota |\n"
        "|----|----|----|----|----|----|----|----|\n| P007 | La reforma | propia | 2026-10-01 | pendiente | [[x]] | — | |\n\nFin.\n",
        encoding="utf-8")
    (vault / "00_Sistema" / "Prompt-historias-propias.md").write_text("# Prompt\n```text\nMI PROMPT\n```\n", encoding="utf-8")
    gv.CARPETA_GUIONES = vault / "02_Clips"
    gv.CARPETA_SALIDA = tmp / "salida"
    au.boveda = lambda: vault

    # ── 1 · Gemini simulado: plan + 4 tandas (con el recuento de palabras que el prompt pide y que no debe leerse)
    llamadas = []

    def gemini_falso(cfg, sistema, turnos, esquema=None):
        llamadas.append((sistema, list(turnos)))
        if esquema:
            return {"titulo": "Mi jefe me robó el ascenso y no sabía con quién se metía", "subreddit": "r/ProRevenge",
                    "categoria": "trabajo", "resumen": "Línea 1.\nLínea 2.", "gancho": "Todo empezó con un correo.",
                    "escaleta": [f"Parte {i}" for i in range(1, 9)], "youtube_titulo": "Mi jefe me ROBÓ el ascenso",
                    "descripcion": "Un jefe, un ascenso y una venganza.", "hashtags": ["#venganza", "trabajo", "reddit historias"],
                    "pregunta": "¿Me pasé?"}
        a = int(turnos[-1].split("PARTES ")[1].split()[0])
        partes = []
        for p in (a, a + 1):
            frases = " ".join(f"Esta es la frase {k} de la parte {p} y la historia sigue avanzando sin parar." for k in range(40))
            partes.append(f"**PARTE {p}/8 · Título {p} · {p * 4} min**\n\n{frases}\n\nY entonces sonó el teléfono…")
        return "\n\n".join(partes) + "\n\n→ Palabras de esta tanda: 900 · Total acumulado: 1800"

    au.gemini = gemini_falso
    cfg = {**au.POR_DEFECTO, "revision_humana": True, "youtube": True, "tiktok": True}
    nota = au.nueva_historia(cfg)

    assert nota.name.startswith(f"{datetime.now():%Y-%m-%d}_P008_mi-jefe-me-robo"), nota.name
    assert llamadas[0][0].startswith("MI PROMPT") and "MODO AUTOMÁTICO" in llamadas[0][0], "usa el prompt de la bóveda"
    assert "la reforma" in llamadas[0][1][0], "le pasa las historias ya hechas para no repetirlas"
    g = gv.parsear_guion(nota)
    assert g.titulo == "Mi jefe me robó el ascenso y no sabía con quién se metía", g.titulo
    assert gv.subreddit_de(nota) == "r/ProRevenge"
    assert len(g.escenas) == 8 and g.escenas[0].titulo.startswith("PARTE 1/8"), [e.titulo for e in g.escenas]
    narrado = " ".join(l.texto_tts for e in g.escenas for l in e.lineas)
    assert "Palabras" not in narrado and "Gemini" not in narrado and "Escaleta" not in narrado and "Gancho" not in narrado
    assert g.cortes and g.cortes[0].lineas, "cortes automáticos"
    assert gv.estado_nota(nota) == "pendiente" and gv.campo(nota, "origen") == "gemini"
    assert gv.campo(nota, "hashtags") == "#venganza #trabajo #reddithistorias"
    assert gv.campo(nota, "descripcion").endswith("Historia de ficción inspirada en el estilo de Reddit.")
    assert "P008" in (vault / "00_Sistema" / "Registro.md").read_text(encoding="utf-8").split("\n\nFin.")[0], "fila nueva en la tabla"

    # ── campos del frontmatter
    gv.poner_campo(nota, "youtube", "https://youtu.be/abc")
    gv.poner_campo(nota, "nuevo", 'con "comillas"\ny salto')
    assert gv.campo(nota, "youtube") == "https://youtu.be/abc" and gv.campo(nota, "nuevo") == 'con "comillas"\ny salto'
    gv.poner_campo(nota, "youtube", "")
    assert gv.campo(nota, "youtube") == "" and gv.parsear_guion(nota).titulo == g.titulo

    # ── 2 · Aprobar → el estado cambia en la nota y en el Registro
    au.poner_estado(nota, "aprobada")
    fila = next(l for l in (vault / "00_Sistema" / "Registro.md").read_text(encoding="utf-8").splitlines() if nota.stem in l)
    assert fila.split("|")[5].strip() == "aprobada", fila
    assert au.notas("aprobada") == [nota]

    # ── 3 · Vídeos «creados» (3 shorts; quedan restos viejos de 5 que no deben contar)
    d = gv.CARPETA_SALIDA / g.slug
    d.mkdir(parents=True)
    for k in range(1, 6):
        (d / f"{g.slug} - Parte {k}de5.mp4").write_bytes(b"viejo")
    (d / f"{g.slug} - YouTube.mp4").write_bytes(b"largo")
    for k in range(1, 4):
        (d / f"{g.slug} - Parte {k}de3.mp4").write_bytes(b"corto")
    largo, cortos = au.videos(nota)
    assert largo and [p.name[-10:] for p in cortos] == ["Parte 1de3.mp4"[-10:], "Parte 2de3.mp4"[-10:], "Parte 3de3.mp4"[-10:]], cortos
    au.poner_estado(nota, "lista")

    # ── 4 · Publicar: dos huecos al día; el vídeo largo va con el primer short
    subidas = []

    def youtube_falso(video, titulo, desc, cuando, cfg):
        subidas.append(("yt", video.name, titulo, desc, cuando))
        return f"https://youtu.be/v{len(subidas)}"

    au.subir_youtube = youtube_falso
    au.subir_tiktok = lambda video: subidas.append(("tt", video.name))
    ahora = datetime.now().astimezone()
    cfg["horas_publicacion"] = [(ahora - timedelta(hours=1)).strftime("%H:%M"), (ahora + timedelta(minutes=30)).strftime("%H:%M")]
    h = au.huecos(cfg, ahora)
    assert h[0] == ahora and h[1] > ahora, "la hora que ya pasó se publica ya; la otra, programada"

    assert len(au.publicar(cfg)) == 2
    assert [s[:2] for s in subidas] == [("yt", f"{g.slug} - YouTube.mp4"), ("yt", f"{g.slug} - Parte 1de3.mp4"),
                                        ("tt", f"{g.slug} - Parte 1de3.mp4"), ("yt", f"{g.slug} - Parte 2de3.mp4"),
                                        ("tt", f"{g.slug} - Parte 2de3.mp4")], subidas
    assert subidas[0][2] == "Mi jefe me ROBÓ el ascenso" and "¿Me pasé?" in subidas[0][3]
    assert "(Parte 1/3)" in subidas[1][2] and "https://youtu.be/v1" in subidas[1][3] and "#shorts" in subidas[1][3]
    assert gv.campo(nota, "youtube") == "https://youtu.be/v1" and gv.estado_nota(nota) == "programada"
    assert gv.campo(nota, "youtube_shorts") == "2" and gv.campo(nota, "tiktok_shorts") == "2"

    au.publicar(cfg)  # al día siguiente: queda el 3 y la nota se da por publicada
    assert len(subidas) == 7 and gv.estado_nota(nota) == "publicada" and au.publicar(cfg) == []

    # ── TikTok: tamaños de trozo dentro de sus reglas (5-64 MB; el último, hasta 128 MB)
    for tam in (3_000_000, 64_000_000, 64_000_001, 150_000_000, 4_000_000_000):
        trozo, n = au.trozos_tiktok(tam)
        ultimo = tam - trozo * (n - 1)
        assert 1 <= n <= 1000 and (n == 1 and tam <= 64_000_000 or 5e6 <= trozo <= 64e6 and ultimo <= 128e6), (tam, trozo, n)

    # ── el JSON de Gemini respeta el esquema que se le pide
    assert set(au.PLAN["required"]) == set(au.PLAN["properties"])
    json.dumps(au.PLAN)
    print(f"OK · nota {nota.name} · {len(g.escenas)} partes · {len(g.cortes)} shorts · {len(subidas)} subidas simuladas")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
