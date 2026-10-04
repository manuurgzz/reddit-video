"""Comprueba los cortes automáticos y que las notas con «Mapa de cortes» no cambian. Uso: python test_cortes.py"""
import tempfile
from pathlib import Path

import guion_a_video as gv

# Historia de ~13 min: párrafos de ~10 s; cada 7 párrafos (~70 s) uno acaba en suspense («…»)
parrafos = []
for i in range(80):
    frases = [f"Esta es la frase {k} del párrafo {i} y sigue contando cosas normales de la historia." for k in range(2)]
    if i % 7 == 6:
        frases[-1] = "Y entonces abrí la puerta y vi lo que había dentro…"
    parrafos.append(" ".join(frases))
texto = "---\nsubreddit: r/prueba\n---\n# Mi vecino y el túnel\n\n" + "\n\n".join(parrafos) + "\n"

with tempfile.TemporaryDirectory() as d:
    ruta = Path(d) / "2026-10-04_prueba.md"
    ruta.write_text(texto, encoding="utf-8")
    g = gv.parsear_guion(ruta)
    assert g.titulo == "Mi vecino y el túnel", g.titulo
    assert gv.subreddit_de(ruta) == "r/prueba"

seq, t = gv.linea_de_tiempo_estimada(g.escenas)
cortes = g.cortes
assert len(cortes) >= 3 and all(c.lineas for c in cortes), cortes
assert cortes[0].lineas[0] == 0 and all(a.lineas[1] == b.lineas[0] for a, b in zip(cortes, cortes[1:])), "huecos entre shorts"
assert all(gv.CORTE_MIN <= c.seg <= gv.CORTE_MAX for c in cortes), [round(c.seg) for c in cortes]
assert all(seq[c.lineas[1] - 1][0].texto_tts.endswith("…") for c in cortes), "cada short debe acabar en suspense"
fin = t[cortes[-1].lineas[1]] / t[-1]
assert 0.7 <= fin <= 0.9, f"los shorts deberían llegar hasta ~80 % de la historia, llegan al {fin:.0%}"
partes = gv.escenas_del_corte(g, cortes[1])
assert [l for e in partes for l in e.lineas] == [l for l, _, _ in seq[slice(*cortes[1].lineas)]]

# Una nota con «Mapa de cortes» sigue usando su tabla
ej = gv.parsear_guion(gv.BASE / "guiones" / "ejemplo_vecino-wifi.md")
assert [(c.desde, c.hasta, c.lineas) for c in ej.cortes] == [(1, 2, ()), (3, 4, ())], ej.cortes
assert gv.solo_youtube(ej) == [] and gv.solo_youtube(g) == []
ej.cortes = ej.cortes[:1]  # si la tabla solo cubre las escenas 1-2, el resto va solo en YouTube
assert gv.solo_youtube(ej) == [3, 4] and gv.lista([3, 4]) == "3 y 4" and gv.lista([2, 3, 4]) == "2, 3 y 4"

print(f"OK · {len(cortes)} shorts de {', '.join(gv.mmss(c.seg) for c in cortes)} · el final ({gv.mmss(t[-1] * (1 - fin))}) solo en YouTube")
