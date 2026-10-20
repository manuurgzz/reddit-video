"""Reddit Video: ventana para crear los vídeos sin terminal. También es lo que lanza la tarea programada (--una-vez)."""
import ctypes
import os
import queue
import random
import re
import sys
import threading
import tkinter as tk
import traceback
import webbrowser
import winsound
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from urllib.parse import quote

import automatizar as au
import guion_a_video as gv
from version import VERSION

try:  # texto nítido en pantallas con escalado
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# Paleta: gris casi negro, un único acento naranja (el color del tema sale solo en lo importante)
FONDO, TARJETA, CAMPO, CAMPO_ACTIVO, BORDE = "#0F1113", "#171A1D", "#21262A", "#2B3237", "#2F373D"
TEXTO, SUAVE, APAGADO, CONSOLA = "#ECEFF1", "#8D99A1", "#59656C", "#0B0D0E"
NARANJA, NARANJA_ACTIVO, NARANJA_PULSADO = "#FF4500", "#FF5F24", "#D93A00"
VERDE, AMARILLO, ROJO = "#46D160", "#FFB000", "#FF585B"

LISTO = "Elige una historia y pulsa «Crear vídeos»."
MARCAS_LOG = (("❌", "error"), ("⚠", "aviso"), ("✅", "ok"))  # color de cada línea del registro
TILDES = {"Alvaro": "Álvaro", "Salome": "Salomé", "Tomas": "Tomás"}
MAX_LINEAS_LOG = 2000     # el registro no crece sin fin
MENSAJES_POR_TURNO = 150  # lo máximo que se pinta de golpe: la ventana siempre responde
ESCALA = 1.0


def px(n):
    return round(n * ESCALA)


def nombre_voz(v):
    """es-ES-AlvaroNeural -> Álvaro"""
    n = v.split("-")[-1].removesuffix("Neural")
    return TILDES.get(n, n)


def etiqueta_voz(v):
    return f"{nombre_voz(v)}  ·  {gv.VOCES[v]}" if v in gv.VOCES else v


FUENTES = {}


class Pildora(tk.Canvas):
    """Botón en píldora. Estilos: primario (naranja), secundario (gris), acento (naranja tenue) y fantasma (solo texto)."""
    COLORES = {  # reposo, ratón encima, pulsado, texto
        "primario": (NARANJA, NARANJA_ACTIVO, NARANJA_PULSADO, "white"),
        "secundario": (CAMPO, CAMPO_ACTIVO, BORDE, TEXTO),
        "acento": ("#33190F", "#432114", "#27130B", "#FF8A5C"),
        "fantasma": (None, CAMPO, BORDE, SUAVE),
    }

    def __init__(self, padre, texto, comando, estilo="secundario", fondo=TARJETA, grande=False):
        self.fuente = FUENTES["titular" if grande else "negrita"]
        self.texto, self.comando, self.estilo, self.estado = texto, comando, estilo, "normal"
        self.grande = grande
        self._encima = self._pulsado = False
        super().__init__(padre, bg=fondo, highlightthickness=0, bd=0, cursor="hand2", takefocus=True)
        self._medir()
        self.bind("<Configure>", lambda e: self._pintar())
        self.bind("<Enter>", lambda e: self._cambiar(encima=True))
        self.bind("<Leave>", lambda e: self._cambiar(encima=False, pulsado=False))
        self.bind("<FocusIn>", lambda e: self._cambiar(encima=True))
        self.bind("<FocusOut>", lambda e: self._cambiar(encima=False))
        self.bind("<ButtonPress-1>", lambda e: self._cambiar(pulsado=True))
        self.bind("<ButtonRelease-1>", self._soltar)
        for tecla in ("<Return>", "<space>"):
            self.bind(tecla, lambda e: self._activar())

    def _medir(self):
        ancho = self.fuente.measure(self.texto) + px(40 if self.grande else 28)
        alto = self.fuente.metrics("linespace") + px(22 if self.grande else 14)
        self.configure(width=ancho, height=alto)

    def _cambiar(self, **kw):
        self._encima = kw.get("encima", self._encima)
        self._pulsado = kw.get("pulsado", self._pulsado)
        self._pintar()

    def _soltar(self, e):
        dentro = 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height()
        pulsado, self._pulsado = self._pulsado, False
        self._pintar()
        if pulsado and dentro:
            self._activar()

    def _activar(self):
        if self.estado == "normal":
            self.comando()

    def poner(self, texto=None, estado=None, estilo=None):
        self.texto = self.texto if texto is None else texto
        self.estado = estado or self.estado
        self.estilo = estilo or self.estilo
        self.configure(cursor="hand2" if self.estado == "normal" else "arrow")
        self._medir()
        self._pintar()

    def _pintar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        reposo, encima, pulsado, texto = self.COLORES[self.estilo]
        if self.estado != "normal":
            relleno, texto = (CAMPO if reposo else None), APAGADO
        else:
            relleno = pulsado if self._pulsado else (encima if self._encima else reposo)
        if relleno:
            self.create_oval(0, 0, h, h, fill=relleno, outline="")
            self.create_oval(w - h, 0, w, h, fill=relleno, outline="")
            self.create_rectangle(h / 2, 0, w - h / 2, h, fill=relleno, outline="")
        self.create_text(w / 2, h / 2, text=self.texto, fill=texto, font=self.fuente)


def una_sola_ventana():
    """False si ya hay otra ventana de la app abierta (dos a la vez se pisarían la caché y los vídeos)."""
    global _mutex
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "RedditVideo.App")
    return ctypes.windll.kernel32.GetLastError() != 183   # ERROR_ALREADY_EXISTS


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        global ESCALA
        ESCALA = self.winfo_fpixels("1i") / 96
        self.title("Reddit Video")
        self.configure(bg=FONDO)
        self.q = queue.Queue()
        self.ocupado = self.cancelando = False
        self.hilo = None
        self.mostrar_log = False
        self.g = None
        self.rutas = []
        gv.log = self.log_desde_hilo
        gv.al_progresar = lambda f: self.q.put(("prog", f))
        gv.preparar_carpetas()
        self.estilos()
        self.icono()
        L = self.letra

        self.raiz = raiz = ttk.Frame(self, style="Fondo.TFrame", padding=(px(32), px(24), px(32), px(16)))
        raiz.pack(fill="both", expand=True)
        raiz.columnconfigure(0, weight=3, uniform="col")
        raiz.columnconfigure(1, weight=2, uniform="col")
        raiz.rowconfigure(1, weight=1)

        # ── Cabecera: marca a la izquierda, accesos discretos a la derecha ──
        cab = ttk.Frame(raiz, style="Fondo.TFrame")
        cab.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, px(20)))
        if self.logo:
            tk.Label(cab, image=self.logo, bg=FONDO).pack(side="left", padx=(0, px(12)))
        ttk.Label(cab, text="Reddit Video", style="Marca.TLabel").pack(side="left")
        self.btn_piloto = Pildora(cab, "", self.piloto, "fantasma", FONDO)
        self.btn_piloto.pack(side="right")
        self.btn_carpetas = Pildora(cab, "Carpetas  ▾", self.menu_carpetas, "fantasma", FONDO)
        self.btn_carpetas.pack(side="right")

        # ── Columna izquierda: historia y post ──
        izq = ttk.Frame(raiz, style="Fondo.TFrame")
        izq.grid(row=1, column=0, sticky="nsew", padx=(0, px(8)))
        izq.columnconfigure(0, weight=1)

        marco, c, cab = self.tarjeta(izq, "Historia", "Pega una historia o elige una nota")
        marco.grid(row=0, column=0, sticky="ew", pady=(0, px(16)))
        c.columnconfigure(0, weight=1)
        self.combo_guion = ttk.Combobox(c, state="readonly", font=(L, 10))
        self.combo_guion.grid(row=0, column=0, columnspan=4, sticky="ew")
        self.combo_guion.bind("<<ComboboxSelected>>", lambda e: self.cargar(self.rutas[self.combo_guion.current()]))
        fila = ttk.Frame(c)
        fila.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(px(12), 0))
        Pildora(fila, "＋  Pegar historia", self.pegar_historia, "acento").pack(side="left")
        Pildora(fila, "Abrir otra…", self.elegir_archivo).pack(side="left", padx=px(8))
        Pildora(fila, "Abrir nota", self.abrir_nota, "fantasma").pack(side="left")
        Pildora(fila, "Conectar Obsidian", self.conectar, "fantasma").pack(side="right")
        self.info = ttk.Label(c, style="Suave.TLabel", wraplength=px(560), justify="left")
        self.info.grid(row=2, column=0, columnspan=3, sticky="w", pady=(px(12), 0))
        self.btn_aprobar = Pildora(c, "✓  Aprobar para el piloto", self.aprobar, "acento")
        self.btn_aprobar.grid(row=2, column=3, sticky="e", pady=(px(12), 0))
        self.btn_aprobar.grid_remove()
        origen = ttk.Frame(c)
        origen.grid(row=3, column=0, columnspan=4, sticky="w", pady=(px(6), 0))
        self.punto = ttk.Label(origen, text="●", style="Suave.TLabel")
        self.punto.pack(side="left", padx=(0, px(6)))
        self.origen = ttk.Label(origen, style="Suave.TLabel")
        self.origen.pack(side="left")

        marco, c, _ = self.tarjeta(izq, "Tarjeta del post", "Con la que arranca el vídeo")
        marco.grid(row=1, column=0, sticky="nsew")
        izq.rowconfigure(1, weight=1)
        c.columnconfigure(0, weight=3)
        c.columnconfigure(1, weight=2)
        self.subreddit, self.usuario, self.titulo = tk.StringVar(), tk.StringVar(), tk.StringVar()
        campos = ttk.Frame(c)
        campos.grid(row=0, column=0, sticky="new", padx=(0, px(24)))
        campos.columnconfigure((0, 1), weight=1, uniform="campos")
        ttk.Label(campos, text="Subreddit", style="Campo.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(campos, textvariable=self.subreddit, font=(L, 10)).grid(row=1, column=0, sticky="ew", padx=(0, px(10)), pady=(px(6), 0))
        ttk.Label(campos, text="Usuario", style="Campo.TLabel").grid(row=0, column=1, sticky="w")
        u = ttk.Frame(campos)
        u.grid(row=1, column=1, sticky="ew", pady=(px(6), 0))
        u.columnconfigure(0, weight=1)
        ttk.Entry(u, textvariable=self.usuario, font=(L, 10)).grid(row=0, column=0, sticky="ew")
        Pildora(u, "Al azar", lambda: self.usuario.set(gv.usuario_al_azar()), "fantasma").grid(row=0, column=1, padx=(px(4), 0))
        ttk.Label(campos, text="Título", style="Campo.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(px(16), 0))
        ttk.Entry(campos, textvariable=self.titulo, font=(L, 10)).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(px(6), 0))

        vista = ttk.Frame(c)
        vista.grid(row=0, column=1, sticky="nsew")
        ttk.Label(vista, text="Vista previa", style="Campo.TLabel").pack(anchor="w")
        post = tk.Frame(vista, bg="white", padx=px(16), pady=px(12))
        post.pack(fill="x", pady=(px(6), 0))
        fila = tk.Frame(post, bg="white")
        fila.pack(fill="x")
        if self.logo_pequeno:
            tk.Label(fila, image=self.logo_pequeno, bg="white").pack(side="left")
        col = tk.Frame(fila, bg="white")
        col.pack(side="left", padx=(px(8), 0))
        self.v_sub = tk.Label(col, bg="white", fg="#141414", font=(self.negrita, 10))
        self.v_sub.pack(anchor="w")
        self.v_autor = tk.Label(col, bg="white", fg="#7C7C7C", font=(L, 9))
        self.v_autor.pack(anchor="w")
        self.v_titulo = tk.Label(post, bg="white", fg="#141414", font=(self.negrita, 11),
                                 wraplength=px(200), justify="left", anchor="w")
        self.v_titulo.pack(fill="x", pady=(px(8), 0))
        for v in (self.subreddit, self.usuario, self.titulo):
            v.trace_add("write", lambda *_: self.pintar_post())

        def ajustar(e):  # el texto se parte al ancho real de la tarjeta, nunca se sale
            self.v_titulo["wraplength"] = max(e.width - px(34), px(80))
            self.v_autor["wraplength"] = max(e.width - px(80), px(60))
        post.bind("<Configure>", ajustar)

        # ── Columna derecha: voz y salida ──
        der = ttk.Frame(raiz, style="Fondo.TFrame")
        der.grid(row=1, column=1, sticky="nsew", padx=(px(8), 0))
        der.columnconfigure(0, weight=1)
        marco, c, _ = self.tarjeta(der, "Voz", "Se sortea en cada historia nueva y se recuerda")
        marco.grid(row=0, column=0, sticky="ew", pady=(0, px(16)))
        c.columnconfigure(0, weight=1)
        self.voz_nombre = ttk.Label(c, style="Voz.TLabel")
        self.voz_nombre.grid(row=0, column=0, sticky="sw")
        self.voz_detalle = ttk.Label(c, style="Suave.TLabel")
        self.voz_detalle.grid(row=1, column=0, sticky="nw")
        self.btn_escuchar = Pildora(c, "▶  Escuchar", self.escuchar, "acento")
        self.btn_escuchar.grid(row=0, column=1, rowspan=2, sticky="e")
        fila = ttk.Frame(c)
        fila.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(px(14), 0))
        fila.columnconfigure(0, weight=1)
        self.combo_voz = ttk.Combobox(fila, state="readonly", font=(L, 10))
        self.combo_voz.grid(row=0, column=0, sticky="ew")
        self.combo_voz.bind("<<ComboboxSelected>>", lambda e: (self.pintar_voz(), self.guardar()))
        Pildora(fila, "Otra al azar", self.voz_azar, "fantasma").grid(row=0, column=1, padx=(px(4), 0))

        marco, c, _ = self.tarjeta(der, "Qué crear", "Formatos y opciones")
        marco.grid(row=1, column=0, sticky="nsew")
        der.rowconfigure(1, weight=1)
        self.op = {k: tk.BooleanVar(value=v) for k, v in
                   [("youtube", True), ("shorts", True), ("musica", True), ("rapido", False), ("gpu", False)]}
        c.columnconfigure((0, 1), weight=1, uniform="formatos")
        self.formato(c, "youtube", "YouTube", "16:9", 16, 9).grid(row=0, column=0, sticky="nsew", padx=(0, px(6)))
        self.formato(c, "shorts", "Shorts", "9:16", 9, 16).grid(row=0, column=1, sticky="nsew", padx=(px(6), 0))
        ttk.Checkbutton(c, text="Música de fondo", variable=self.op["musica"]).grid(row=1, column=0, columnspan=2, sticky="w", pady=(px(16), 0))
        ttk.Checkbutton(c, text="Prueba rápida (media calidad)", variable=self.op["rapido"]).grid(row=2, column=0, columnspan=2, sticky="w", pady=(px(4), 0))
        self.casilla_gpu = ttk.Checkbutton(c, text="Comprobando gráfica NVIDIA…", variable=self.op["gpu"], state="disabled")
        self.casilla_gpu.grid(row=3, column=0, columnspan=2, sticky="w", pady=(px(4), 0))
        threading.Thread(target=lambda: self.q.put(("gpu", gv.hay_nvenc())), daemon=True).start()  # puede tardar: fuera del arranque

        # ── Barra de acción: estado y progreso a la izquierda, botón principal a la derecha ──
        acciones = ttk.Frame(raiz, style="Fondo.TFrame")
        acciones.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(px(20), 0))
        acciones.columnconfigure(0, weight=1)
        self.estado = ttk.Label(acciones, text=LISTO, style="Estado.TLabel")
        self.estado.grid(row=0, column=0, sticky="sw", padx=(px(2), px(24)))
        pista = tk.Frame(acciones, height=px(4), bg=CAMPO)  # barra de progreso fina (la de clam no baja de ~12 px)
        pista.grid(row=1, column=0, sticky="ew", padx=(0, px(24)), pady=(px(10), px(4)))
        self.relleno = tk.Frame(pista, bg=NARANJA)
        self.relleno.place(x=0, y=0, relheight=1, relwidth=0)
        self.btn_crear = Pildora(acciones, "Crear vídeos", self.accion, "primario", FONDO, grande=True)
        self.btn_crear.grid(row=0, column=1, rowspan=2, sticky="e")

        # ── Detalles (el registro) plegados por defecto ──
        pie = ttk.Frame(raiz, style="Fondo.TFrame")
        pie.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(px(8), 0))
        self.btn_detalles = Pildora(pie, "Mostrar detalles  ▾", self.alternar_log, "fantasma", FONDO)
        self.btn_detalles.pack(side="left")
        ttk.Label(pie, text=f"v{VERSION}", style="Apagado.TLabel").pack(side="right", padx=px(4))
        self.marco_log = tk.Frame(raiz, bg=CONSOLA)
        self.texto = tk.Text(self.marco_log, height=9, font=(self.mono, 9), wrap="word", relief="flat", bd=0,
                             highlightthickness=0, bg=CONSOLA, fg="#C3CED4", insertbackground=TEXTO,
                             selectbackground=NARANJA, selectforeground="white", padx=px(18), pady=px(12))
        desliz = ttk.Scrollbar(self.marco_log, command=self.texto.yview)
        self.texto.configure(yscrollcommand=desliz.set)
        desliz.pack(side="right", fill="y")
        self.texto.pack(side="left", fill="both", expand=True)
        for tag, color in (("error", ROJO), ("aviso", AMARILLO), ("ok", VERDE)):
            self.texto.tag_configure(tag, foreground=color)

        self.voces = list(gv.VOCES)
        self.combo_voz["values"] = [etiqueta_voz(v) for v in self.voces]
        self.cargar_lista()
        self.pintar_post()
        self.pintar_voz()
        self.pintar_piloto()
        self.alto = min(px(700), self.winfo_screenheight() - px(80))
        self.geometry(f"{px(1080)}x{self.alto}")
        self.minsize(px(940), px(660))
        self.barra_oscura()
        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.bind("<Control-Return>", lambda e: self.accion())
        self.after(50, self.bucle)

    # ── aspecto ──────────────────────────────────────────────────────────
    def estilos(self):
        familias = set(tkfont.families(self))
        elige = lambda *ns: next((n for n in ns if n in familias), ns[-1])  # Windows 11, si no Windows 10
        self.letra = L = elige("Segoe UI Variable Text", "Segoe UI")
        self.negrita = B = elige("Segoe UI Variable Text Semibold", "Segoe UI Semibold")
        self.titular = T = elige("Segoe UI Variable Display Semib", "Segoe UI Semibold")
        self.mono = elige("Cascadia Mono", "Consolas")
        FUENTES["negrita"] = tkfont.Font(self, family=B, size=9)
        FUENTES["titular"] = tkfont.Font(self, family=T, size=12)

        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure(".", background=TARJETA, foreground=TEXTO, font=(L, 10), bordercolor=BORDE,
                     lightcolor=CAMPO, darkcolor=CAMPO, troughcolor=CAMPO, focuscolor=SUAVE, arrowcolor=SUAVE,
                     insertcolor=TEXTO, selectbackground=NARANJA, selectforeground="white")
        st.configure("Fondo.TFrame", background=FONDO)
        st.configure("Marca.TLabel", background=FONDO, font=(T, 17))
        st.configure("Estado.TLabel", background=FONDO, foreground=SUAVE)
        st.configure("Apagado.TLabel", background=FONDO, foreground=APAGADO, font=(L, 9))
        st.configure("Seccion.TLabel", font=(T, 12))
        st.configure("Suave.TLabel", foreground=SUAVE, font=(L, 9))
        st.configure("Campo.TLabel", foreground=SUAVE, font=(B, 9))
        st.configure("Voz.TLabel", font=(T, 17))

        # Casillas con check de verdad (la de «clam» dibuja un aspa que parece una X)
        self._casillas = vacia, marcada = self.casilla(False), self.casilla(True)
        st.element_create("Casilla.indicator", "image", vacia, ("selected", marcada),
                          width=vacia.width() + px(8), sticky="w")
        st.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("Casilla.indicator", {"side": "left", "sticky": ""}),
            ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [("Checkbutton.label", {"sticky": "nswe"})]})]})])
        st.configure("TCheckbutton", padding=px(2))
        st.map("TCheckbutton", background=[("active", TARJETA)], foreground=[("disabled", APAGADO)])
        st.configure("Formato.TCheckbutton", background=CAMPO, font=(T, 12))
        st.map("Formato.TCheckbutton", background=[("active", CAMPO)])
        st.configure("Grande.TCheckbutton", font=(T, 11))

        campo = dict(fieldbackground=CAMPO, background=CAMPO, foreground=TEXTO, bordercolor=CAMPO,
                     lightcolor=CAMPO, darkcolor=CAMPO, padding=(px(10), px(7)))
        st.configure("TEntry", **campo)
        st.map("TEntry", bordercolor=[("focus", NARANJA)], lightcolor=[("focus", CAMPO)])
        st.configure("TCombobox", arrowsize=px(14), **campo)
        st.map("TCombobox", fieldbackground=[("readonly", CAMPO)], foreground=[("readonly", TEXTO)],
               background=[("active", CAMPO_ACTIVO), ("readonly", CAMPO)], arrowcolor=[("active", TEXTO)],
               selectbackground=[("readonly", CAMPO)], selectforeground=[("readonly", TEXTO)],
               bordercolor=[("focus", NARANJA)], lightcolor=[("focus", CAMPO)])
        for opcion, valor in (("background", CAMPO), ("foreground", TEXTO), ("selectBackground", NARANJA),
                              ("selectForeground", "white"), ("font", f"{{{L}}} 10")):
            self.option_add(f"*TCombobox*Listbox.{opcion}", valor)

        st.configure("Vertical.TScrollbar", background=CAMPO, troughcolor=CONSOLA, bordercolor=CONSOLA,
                     lightcolor=CAMPO, darkcolor=CAMPO, gripcount=0, arrowsize=px(12))
        st.map("Vertical.TScrollbar", background=[("active", CAMPO_ACTIVO)])

    def casilla(self, marcada):
        """Casilla de 16 px dibujada píxel a píxel; la marcada lleva un check blanco suavizado."""
        s = px(16)
        fondo, borde = (NARANJA, NARANJA) if marcada else (CAMPO, "#56646B")
        trazo = [(0.24 * s, 0.52 * s), (0.43 * s, 0.70 * s), (0.77 * s, 0.32 * s)]

        def distancia(x, y, a, b):
            (ax, ay), (bx, by) = a, b
            t = max(0, min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)))
            return ((x - ax - t * (bx - ax)) ** 2 + (y - ay - t * (by - ay)) ** 2) ** 0.5

        def mezcla(c, k):  # c hacia blanco en proporción k
            return "#" + "".join(f"{round(int(c[i:i + 2], 16) * (1 - k) + 255 * k):02X}" for i in (1, 3, 5))

        img = tk.PhotoImage(width=s, height=s)
        for y in range(s):
            for x in range(s):
                if x in (0, s - 1) and y in (0, s - 1):
                    continue  # esquinas transparentes: borde algo redondeado
                color = borde if x in (0, s - 1) or y in (0, s - 1) else fondo
                if marcada:
                    d = min(distancia(x + 0.5, y + 0.5, *trazo[:2]), distancia(x + 0.5, y + 0.5, *trazo[1:]))
                    color = mezcla(color, max(0.0, min(1.0, 0.085 * s + 0.5 - d)))
                img.put(color, (x, y))
        return img

    def icono(self):
        """Icono de la ventana (el del .exe ya lo lleva incrustado) y logos para la cabecera y la vista previa."""
        self.logo = self.logo_pequeno = None
        png = gv.RECURSOS / "assets" / "icono.png"
        try:
            img = tk.PhotoImage(file=str(png))
            self.iconphoto(True, img)
            self.logo = img.subsample(max(round(256 / px(34)), 1))
            self.logo_pequeno = img.subsample(max(round(256 / px(26)), 1))
        except tk.TclError:  # sin el archivo, la ventana lleva el icono genérico
            pass

    def barra_oscura(self):
        """Barra de título oscura en Windows 10/11 (si no se puede, se queda la normal)."""
        self.oscurecer(self)

    def oscurecer(self, ventana):
        try:
            ventana.update_idletasks()
            ctypes.windll.dwmapi.DwmSetWindowAttribute(int(ventana.wm_frame(), 16), 20, ctypes.byref(ctypes.c_int(1)), 4)
        except Exception:
            pass

    def tarjeta(self, padre, titulo, lema):
        """Tarjeta plana (sin borde) con título y lema. Devuelve (marco, cuerpo, cabecera)."""
        marco = tk.Frame(padre, bg=TARJETA)
        cab = ttk.Frame(marco, padding=(px(24), px(20), px(24), 0))
        cab.pack(fill="x")
        ttk.Label(cab, text=titulo, style="Seccion.TLabel").pack(side="left")
        ttk.Label(cab, text=lema, style="Suave.TLabel").pack(side="left", padx=(px(12), 0), pady=(px(3), 0))
        cuerpo = ttk.Frame(marco, padding=(px(24), px(14), px(24), px(22)))
        cuerpo.pack(fill="both", expand=True)
        return marco, cuerpo, cab

    def formato(self, padre, clave, titulo, detalle, ancho, alto):
        """Casilla grande (YouTube / Shorts) con el dibujo de su proporción; se marca con clic en cualquier parte."""
        var = self.op[clave]
        marco = tk.Frame(padre, bg=CAMPO, highlightthickness=px(2), cursor="hand2")
        lado = px(30)
        w, h = (lado, lado * alto // ancho) if ancho > alto else (lado * ancho // alto, lado)
        lienzo = tk.Canvas(marco, width=lado, height=lado, bg=CAMPO, highlightthickness=0)
        rect = lienzo.create_rectangle((lado - w) // 2 + 1, (lado - h) // 2 + 1, (lado + w) // 2 - 1, (lado + h) // 2 - 1, width=px(2))
        lienzo.grid(row=0, column=0, rowspan=2, padx=(px(14), px(10)), pady=px(12))
        ttk.Checkbutton(marco, text=titulo, variable=var, style="Formato.TCheckbutton").grid(row=0, column=1, sticky="sw", pady=(px(12), 0))
        sub = tk.Label(marco, text=detalle, bg=CAMPO, fg=SUAVE, font=(self.letra, 9))
        sub.grid(row=1, column=1, sticky="nw", padx=(px(2), px(10)), pady=(0, px(12)))

        def pintar(*_):
            color = NARANJA if var.get() else CAMPO
            marco.configure(highlightbackground=color, highlightcolor=color)
            lienzo.itemconfigure(rect, outline=NARANJA if var.get() else SUAVE)
        var.trace_add("write", pintar)
        pintar()
        for w in (marco, lienzo, sub):
            w.bind("<Button-1>", lambda e: var.set(not var.get()))
        return marco

    def dialogo(self, titulo):
        """Ventana modal centrada sobre la principal. Devuelve (ventana, marco interior)."""
        v = tk.Toplevel(self, bg=TARJETA)
        v.title(titulo)
        v.transient(self)
        v.grab_set()
        v.bind("<Escape>", lambda e: v.destroy())
        c = ttk.Frame(v, padding=(px(28), px(24), px(28), px(24)))
        c.pack(fill="both", expand=True)
        return v, c

    def centrar(self, v):
        v.update_idletasks()
        v.geometry(f"+{max(self.winfo_rootx() + (self.winfo_width() - v.winfo_reqwidth()) // 2, 0)}"
                   f"+{max(self.winfo_rooty() + (self.winfo_height() - v.winfo_reqheight()) // 2, 0)}")
        self.oscurecer(v)

    def pintar_post(self):
        """Vista previa de la tarjeta del principio (las horas son las mismas que saldrán en el vídeo)."""
        horas = random.Random(self.g.slug).randint(2, 23) if self.g else 5
        self.v_sub["text"] = self.subreddit.get().strip() or "r/subreddit"
        self.v_autor["text"] = f"{self.usuario.get().strip() or 'u/usuario'} • {horas} h"
        self.v_titulo["text"] = self.titulo.get().strip() or "Aquí aparecerá el título del post"

    def pintar_voz(self):
        i = self.combo_voz.current()
        v = self.voces[i] if i >= 0 else ""
        self.voz_nombre["text"] = nombre_voz(v) if v else "Sin voz todavía"
        self.voz_detalle["text"] = (f"{gv.VOCES.get(v, 'Voz personalizada')}  ·  {v}" if v
                                    else "Elige una historia y se le asigna una")

    def alternar_log(self):
        self.mostrar_log = not self.mostrar_log
        extra = px(250)
        if self.mostrar_log:
            self.marco_log.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(px(8), 0))
            self.raiz.rowconfigure(4, weight=1)
            self.geometry(f"{self.winfo_width()}x{min(self.winfo_height() + extra, self.winfo_screenheight() - px(60))}")
        else:
            self.marco_log.grid_remove()
            self.raiz.rowconfigure(4, weight=0)
            self.geometry(f"{self.winfo_width()}x{max(self.winfo_height() - extra, self.alto)}")
        self.btn_detalles.poner("Ocultar detalles  ▴" if self.mostrar_log else "Mostrar detalles  ▾")

    def menu_carpetas(self):
        m = tk.Menu(self, tearoff=0, bg=CAMPO, fg=TEXTO, activebackground=NARANJA, activeforeground="white",
                    bd=0, relief="flat", font=(self.letra, 10))
        m.add_command(label="Vídeos creados", command=self.abrir_salida)
        m.add_command(label="Fondos", command=lambda: self.abrir(gv.CARPETA_FONDOS))
        m.add_command(label="Música", command=lambda: self.abrir(gv.CARPETA_MUSICA))
        m.add_command(label="Datos de la app", command=lambda: self.abrir(gv.DATOS))
        b = self.btn_carpetas
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def abrir(self, ruta):
        try:
            Path(ruta).mkdir(parents=True, exist_ok=True)
            os.startfile(ruta)
        except OSError as e:
            self.aviso(f"No pude abrir la carpeta: {e}", ROJO)

    def aviso(self, texto, color=SUAVE):
        self.estado.configure(text=texto, foreground=color)

    # ── guion y proyecto ─────────────────────────────────────────────────
    def cargar_lista(self, elegida=None):
        d = gv.CARPETA_GUIONES
        boveda = gv.leer_ajustes().get("boveda")
        self.punto.configure(foreground=VERDE if boveda else SUAVE)
        self.origen["text"] = f"Obsidian · {Path(boveda).name} › {d.name}" if boveda else f"Carpeta local · {d.name}"
        self.rutas = gv.guiones_de(d)
        if elegida and elegida not in self.rutas:
            self.rutas.insert(0, elegida)
        self.refrescar_nombres()
        if self.rutas:
            self.combo_guion.current(self.rutas.index(elegida) if elegida else 0)
            self.cargar(self.rutas[self.combo_guion.current()])
        else:
            self.g = None
            self.info.configure(text=f"No hay historias en {d}. Pega una o conecta Obsidian.", foreground=AMARILLO)

    def refrescar_nombres(self):
        """Nombre de cada nota + su estado de Obsidian (pendiente, en-produccion, hecha…)."""
        actual = self.combo_guion.current()
        self.combo_guion["values"] = [f"{p.stem}" + (f"   ·   {e}" if (e := gv.estado_nota(p)) else "") for p in self.rutas]
        if actual >= 0:
            self.combo_guion.current(actual)

    def conectar(self):
        d = filedialog.askdirectory(title="Elige tu bóveda de Obsidian (o la carpeta con tus guiones)",
                                    initialdir=gv.leer_ajustes().get("boveda") or gv.CARPETA_GUIONES)
        if not d:
            return
        boveda, gv.CARPETA_GUIONES = gv.conectar_carpeta(Path(d))
        if not boveda:
            messagebox.showinfo("Carpeta conectada", "Esa carpeta no es una bóveda de Obsidian (no tiene .obsidian), "
                                                     "pero leeré los guiones que tenga dentro.")
        self.cargar_lista()

    def pegar_historia(self):
        """Pegar una historia tal cual: se guarda como nota .md en la carpeta de guiones y se carga."""
        L = self.letra
        v, c = self.dialogo("Pegar historia")
        c.columnconfigure(0, weight=1)
        c.rowconfigure(3, weight=1)
        titulo, sub = tk.StringVar(), tk.StringVar(value="r/AITAH")
        ttk.Label(c, text="Título del post", style="Campo.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(c, text="Subreddit", style="Campo.TLabel").grid(row=0, column=1, sticky="w", padx=(px(12), 0))
        campo_titulo = ttk.Entry(c, textvariable=titulo, font=(L, 10))
        campo_titulo.grid(row=1, column=0, sticky="ew", pady=(px(6), px(16)))
        ttk.Entry(c, textvariable=sub, width=16, font=(L, 10)).grid(row=1, column=1, sticky="ew", padx=(px(12), 0), pady=(px(6), px(16)))
        ttk.Label(c, text="Historia: pégala tal cual. Si tiene secciones con «#», se usan como pistas para los cortes.",
                  style="Suave.TLabel").grid(row=2, column=0, columnspan=2, sticky="w")
        texto = tk.Text(c, width=90, height=20, wrap="word", font=(L, 10), bg=CAMPO, fg=TEXTO, insertbackground=TEXTO,
                        selectbackground=NARANJA, selectforeground="white", relief="flat", padx=px(14), pady=px(12),
                        highlightthickness=1, highlightbackground=CAMPO, highlightcolor=NARANJA)
        texto.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(px(6), px(20)))

        def guardar():
            t, cuerpo, s = titulo.get().strip(), texto.get("1.0", "end").strip(), sub.get().strip()
            if not t or not cuerpo:
                return messagebox.showwarning("Falta algo", "Escribe el título del post y pega la historia.", parent=v)
            nombre = re.sub(r"[^a-z0-9]+", "-", gv.quitar_tildes(t.lower())).strip("-")[:40] or "historia"
            ruta, n = gv.CARPETA_GUIONES / f"{date.today()}_{nombre}.md", 2
            while ruta.exists():
                ruta, n = gv.CARPETA_GUIONES / f"{date.today()}_{nombre}-{n}.md", n + 1
            cabecera = f"---\nsubreddit: r/{s.removeprefix('r/')}\n---\n" if s else ""
            try:
                gv.escribir_texto(ruta, f"{cabecera}# {t}\n\n{cuerpo}\n")
            except OSError as e:
                return messagebox.showerror("No se pudo guardar", str(e), parent=v)
            v.destroy()
            self.cargar_lista(ruta)

        botones = ttk.Frame(c)
        botones.grid(row=4, column=0, columnspan=2, sticky="e")
        Pildora(botones, "Cancelar", v.destroy, "fantasma").pack(side="left")
        Pildora(botones, "Guardar y usar", guardar, "primario").pack(side="left", padx=(px(8), 0))
        campo_titulo.focus_set()
        self.centrar(v)

    def abrir_nota(self):
        if not self.g:
            return
        boveda = gv.leer_ajustes().get("boveda")
        try:
            if boveda and str(self.g.ruta).startswith(boveda):
                os.startfile("obsidian://open?path=" + quote(str(self.g.ruta)))
            else:
                os.startfile(self.g.ruta)
        except OSError:  # Obsidian no instalado: se abre con el editor de .md
            try:
                os.startfile(self.g.ruta)
            except OSError as e:
                self.aviso(f"No pude abrir la nota: {e}", ROJO)

    def elegir_archivo(self):
        r = filedialog.askopenfilename(title="Elige un guion", filetypes=[("Historia o guion", "*.md *.txt")],
                                       initialdir=gv.CARPETA_GUIONES if gv.CARPETA_GUIONES.is_dir() else None)
        if r:
            self.cargar_lista(Path(r))

    def cargar(self, ruta):
        self.texto.delete("1.0", "end")
        try:
            self.info.configure(text="Analizando la historia…", foreground=SUAVE)
            self.update_idletasks()
            self.g = gv.parsear_guion(ruta)
        except Exception as e:
            self.g = None
            self.info.configure(text=f"No pude leer esta nota: {e}", foreground=ROJO)
            return
        self.btn_aprobar.grid() if gv.estado_nota(ruta) == "pendiente" else self.btn_aprobar.grid_remove()
        if not self.g.escenas:
            self.info.configure(text="No encuentro texto que narrar en esta nota.", foreground=AMARILLO)
            return
        p = gv.datos_proyecto(self.g)
        self.subreddit.set(p["subreddit"])
        self.usuario.set(p["usuario"])
        self.titulo.set(p["titulo"])
        if p["voz"] not in self.voces:
            self.voces.append(p["voz"])
            self.combo_voz["values"] = [*self.combo_voz["values"], etiqueta_voz(p["voz"])]
        self.combo_voz.current(self.voces.index(p["voz"]))
        self.pintar_voz()
        sin_clips = sorted({e.etiqueta for e in self.g.escenas if e.etiqueta and not gv.clips_de(e.etiqueta)})
        cortes = self.g.cortes
        if cortes and cortes[0].lineas:  # cortes automáticos (la nota no trae «Mapa de cortes»)
            resumen = (f"~{gv.mmss(gv.linea_de_tiempo_estimada(self.g.escenas)[1][-1])} de voz  ·  {len(cortes)} shorts "
                       f"automáticos de ~{gv.mmss(sum(c.seg for c in cortes) / len(cortes))}"
                       + ("  ·  el final, solo en YouTube" if gv.FINAL_SOLO_YOUTUBE else ""))
        else:
            fuera = gv.solo_youtube(self.g)
            resumen = (f"{len(self.g.escenas)} escenas  ·  {len(cortes)} shorts"
                       + (f"  ·  escena{'s' * (len(fuera) > 1)} {gv.lista(fuera)}, solo en YouTube" if fuera else ""))
        self.info.configure(text=resumen
                                 + (f"\nSin clips en {', '.join(sin_clips)}: se usarán otros fondos" if sin_clips else ""),
                            foreground=AMARILLO if sin_clips else SUAVE)
        gv.resumen(self.g)

    def guardar(self):
        """Guarda lo que hay en pantalla para este proyecto (lo lee guion_a_video al crear)."""
        if not self.g or not self.g.escenas or self.combo_voz.current() < 0:
            return
        d = {"voz": self.voces[self.combo_voz.current()], "subreddit": self.subreddit.get().strip(),
             "usuario": self.usuario.get().strip()}
        if self.titulo.get().strip() != self.g.titulo:
            d["titulo"] = self.titulo.get().strip()
        try:
            gv.guardar_proyecto(self.g.slug, d)
        except OSError as e:
            self.aviso(f"No pude guardar los cambios: {e}", ROJO)

    def voz_azar(self):
        actual = self.voces[self.combo_voz.current()] if self.combo_voz.current() >= 0 else ""
        nueva = next((n for n in (gv.voz_al_azar() for _ in range(30)) if n != actual), None)
        if nueva is None:
            return
        if nueva not in self.voces:
            self.voces.append(nueva)
            self.combo_voz["values"] = [*self.combo_voz["values"], etiqueta_voz(nueva)]
        self.combo_voz.current(self.voces.index(nueva))
        self.pintar_voz()
        self.guardar()

    def escuchar(self):
        if not self.g or not self.g.escenas or not self.g.escenas[0].lineas or self.combo_voz.current() < 0:
            return self.aviso("Elige primero una historia para escuchar su voz.")
        voz = self.voces[self.combo_voz.current()]
        frase = self.g.escenas[0].lineas[0].texto_tts
        self.btn_escuchar.poner(estado="disabled")
        self.aviso("Preparando la muestra de voz…")

        def trabajo():
            try:
                self.q.put(("sonar", gv.muestra_voz(voz, frase)))
            except Exception as e:
                self.q.put(("log", f"❌ No se pudo generar la muestra: {e}"))
                self.q.put(("sonar", None))
        threading.Thread(target=trabajo, daemon=True).start()
        self.after(45000, lambda: self.btn_escuchar.estado == "disabled" and self.q.put(("sonar", None)))  # red de seguridad

    # ── crear ────────────────────────────────────────────────────────────
    def empezar(self, texto, hilo_trabajo):
        """Marca el programa como ocupado: el botón pasa a «Cancelar» y no se puede lanzar nada más."""
        self.ocupado, self.cancelando = True, False
        gv.cancelar_ya.clear()
        self.btn_crear.poner("Cancelar", estilo="secundario")
        self.btn_piloto.poner(estado="disabled")
        self.aviso(texto, TEXTO)
        self.texto.delete("1.0", "end")
        self.relleno.place_configure(relwidth=0)
        self.hilo = threading.Thread(target=hilo_trabajo, daemon=True)
        self.hilo.start()

    def accion(self):
        """El botón grande: crea, o cancela si ya hay algo en marcha."""
        if not self.ocupado:
            return self.crear()
        if not self.cancelando:
            self.cancelando = True
            self.btn_crear.poner("Cancelando…", estado="disabled")
            self.aviso("Cancelando: termina el paso en curso…", AMARILLO)
            gv.cancelar()

    def log_desde_hilo(self, m=""):
        """Lo que escribe el motor. Si el usuario canceló, el hilo de trabajo se corta en la siguiente línea."""
        self.q.put(("log", str(m)))
        if self.cancelando and threading.current_thread() is self.hilo:
            raise gv.Cancelado()

    def crear(self):
        if not self.g or not self.g.escenas:
            return messagebox.showwarning("Falta la historia", "Elige primero una historia con escenas.")
        yt, sh = self.op["youtube"].get(), self.op["shorts"].get()
        if not (yt or sh):
            return messagebox.showwarning("Nada que crear", "Marca YouTube, Shorts o los dos.")
        self.guardar()
        args = [str(self.g.ruta), "--solo", "todo" if yt and sh else ("youtube" if yt else "cortes")]
        args += ["--sin-musica"] * (not self.op["musica"].get())
        args += ["--rapido"] * self.op["rapido"].get() + ["--gpu"] * self.op["gpu"].get()

        def trabajo():
            ok = False
            try:
                gv.main(args)
                ok = True
            except gv.Cancelado:
                ok = "cancelado"
            except SystemExit as e:
                self.q.put(("log", str(e.code or "")))
            except Exception as e:
                self.q.put(("log", f"\n❌ Error: {e}\n{traceback.format_exc()}"))
            self.q.put(("fin", ok))
        self.empezar("Creando vídeos…", trabajo)

    def abrir_salida(self):
        d = gv.CARPETA_SALIDA / self.g.slug if self.g else gv.CARPETA_SALIDA
        self.abrir(d if d.is_dir() else gv.CARPETA_SALIDA)

    # ── piloto automático (automatizar.py) ───────────────────────────────
    def aprobar(self):
        """La historia pasa a «aprobada»: el piloto creará y publicará sus vídeos en la próxima pasada."""
        au.poner_estado(self.g.ruta, "aprobada")
        self.refrescar_nombres()
        self.btn_aprobar.grid_remove()
        self.aviso("✓ Aprobada: el piloto creará y publicará sus vídeos en la próxima pasada.", VERDE)

    def pintar_piloto(self):
        activo = au.ajustes()["activo"]
        self.btn_piloto.poner("●  Piloto activo" if activo else "Piloto automático", estilo="acento" if activo else "fantasma")

    def piloto(self):
        """Ajustes del piloto: Gemini escribe las historias y la app crea y publica los vídeos sola cada día."""
        L = self.letra
        cfg, sec = au.ajustes(), au.secretos()
        v, c = self.dialogo("Piloto automático")
        v.resizable(False, False)
        c.columnconfigure(0, weight=1)
        var = {k: tk.BooleanVar(value=bool(cfg[k])) for k in ("activo", "revision_humana", "gpu", "youtube", "tiktok", "sintetico")}
        clave, modelo = tk.StringVar(value=sec.get("gemini", "")), tk.StringVar(value=cfg["modelo"])
        cola, hora = tk.StringVar(value=str(cfg["cola"])), tk.StringVar(value=cfg["hora"])
        horas = tk.StringVar(value=", ".join(cfg["horas_publicacion"]))
        tt = sec.get("tiktok") or {}
        tt_clave, tt_secreto = tk.StringVar(value=tt.get("client_key", "")), tk.StringVar(value=tt.get("client_secret", ""))

        ttk.Label(c, text="Piloto automático", style="Voz.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(c, text="Gemini escribe las historias; la app crea los vídeos de las que apruebes y los publica sola.",
                  style="Suave.TLabel").grid(row=1, column=0, sticky="w", pady=(0, px(16)))
        pestanas = ttk.Frame(c)
        pestanas.grid(row=2, column=0, sticky="w")
        paginas, botones_p = [], []

        def pagina():
            f = ttk.Frame(c, padding=(0, px(18), 0, 0))
            f.columnconfigure(1, weight=1)
            paginas.append(f)
            return f

        def mostrar(i):
            for k, (f, b) in enumerate(zip(paginas, botones_p)):
                f.grid(row=3, column=0, sticky="ew") if k == i else f.grid_remove()
                b.poner(estilo="secundario" if k == i else "fantasma")

        def linea(f, fila, texto, widget, extra=None):
            ttk.Label(f, text=texto, style="Campo.TLabel").grid(row=fila, column=0, sticky="w", padx=(0, px(18)), pady=px(6))
            widget.grid(row=fila, column=1, sticky="ew", pady=px(6))
            if extra:
                extra.grid(row=fila, column=2, sticky="e", padx=(px(8), 0), pady=px(6))

        entrada = lambda f, v_, **kw: ttk.Entry(f, textvariable=v_, font=(L, 10), **kw)

        # Pestaña 1 · Historias
        f = pagina()
        linea(f, 0, "Clave de Gemini", entrada(f, clave, show="•", width=40),
              Pildora(f, "Conseguir clave ↗", lambda: webbrowser.open("https://aistudio.google.com/apikey"), "fantasma"))
        linea(f, 1, "Modelo", ttk.Combobox(f, textvariable=modelo, font=(L, 10), values=["gemini-3.8-flash", "gemini-3.1-pro-preview"]))
        linea(f, 2, "Historias en marcha", ttk.Combobox(f, textvariable=cola, values=[1, 2, 3, 4, 5], state="readonly", width=4, font=(L, 10)),
              ttk.Label(f, text="a la vez, como mucho", style="Suave.TLabel"))
        ttk.Checkbutton(f, text="Revisar yo cada historia antes de crear los vídeos (botón «Aprobar»)",
                        variable=var["revision_humana"]).grid(row=3, column=0, columnspan=3, sticky="w", pady=(px(10), 0))

        # Pestaña 2 · Vídeos
        f = pagina()
        linea(f, 0, "Pasada diaria a las", entrada(f, hora, width=8))
        gpu = ttk.Checkbutton(f, text="Usar gráfica NVIDIA", variable=var["gpu"])
        if not gv.hay_nvenc():
            var["gpu"].set(False)
            gpu.configure(text="Gráfica NVIDIA (no hay en este PC)", state="disabled")
        gpu.grid(row=1, column=0, columnspan=3, sticky="w", pady=(px(10), 0))
        n = au.cola()
        textos = {"pendiente": "por aprobar", "aprobada": "aprobada", "lista": "con vídeos", "programada": "publicándose",
                  "error": "con error"}
        partes = [f"{n[k]} {t}{'s' * (k == 'aprobada' and n[k] > 1)}" for k, t in textos.items() if n.get(k)]
        ttk.Label(f, text="En la carpeta:  " + "  ·  ".join(partes) if partes else "Todavía no hay historias en marcha.",
                  style="Suave.TLabel").grid(row=2, column=0, columnspan=3, sticky="w", pady=(px(18), 0))

        # Pestaña 3 · Publicar
        f = pagina()
        guia = lambda: self.abrir(gv.RECURSOS / "docs" / "piloto-automatico.md")
        linea(f, 0, "Publicar a las", entrada(f, horas), Pildora(f, "¿Cómo se conecta?", guia, "fantasma"))
        conectado = lambda ok: ("✓ Conectado", VERDE) if ok else ("Sin conectar", SUAVE)
        estado_yt, estado_tt = ttk.Label(f, style="Suave.TLabel", wraplength=px(300)), ttk.Label(f, style="Suave.TLabel", wraplength=px(300))
        estado_yt.configure(text=conectado(sec.get("youtube"))[0], foreground=conectado(sec.get("youtube"))[1])
        estado_tt.configure(text=conectado(tt.get("refresh_token"))[0], foreground=conectado(tt.get("refresh_token"))[1])

        def conectar(funcion, etiqueta, boton):
            etiqueta.configure(text="Inicia sesión en el navegador que se ha abierto…", foreground=AMARILLO)
            boton.poner(estado="disabled")

            def trabajo():
                try:
                    funcion()
                    texto, color = "✓ Conectado", VERDE
                except Exception as e:
                    texto, color = f"✗ {e}", ROJO

                def pintar():
                    if etiqueta.winfo_exists():
                        etiqueta.configure(text=texto, foreground=color)
                        boton.poner(estado="normal")
                self.q.put(("llamar", pintar))
            threading.Thread(target=trabajo, daemon=True).start()

        def conectar_youtube():
            ruta = filedialog.askopenfilename(parent=v, title="El JSON del cliente OAuth de Google Cloud (App de escritorio)",
                                              filetypes=[("Cliente OAuth", "*.json")])
            if ruta:
                conectar(lambda: au.conectar_youtube(ruta), estado_yt, btn_yt)

        def conectar_tiktok():
            au.guardar_secretos(tiktok={**(au.secretos().get("tiktok") or {}), "client_key": tt_clave.get().strip(),
                                        "client_secret": tt_secreto.get().strip()})
            conectar(au.conectar_tiktok, estado_tt, btn_tt)

        btn_yt, btn_tt = Pildora(f, "Conectar YouTube…", conectar_youtube), Pildora(f, "Conectar TikTok…", conectar_tiktok)
        linea(f, 1, "YouTube", estado_yt, btn_yt)
        ttk.Checkbutton(f, text="Publicar en YouTube", variable=var["youtube"]).grid(row=2, column=1, sticky="w")
        linea(f, 3, "TikTok", estado_tt, btn_tt)
        claves_tt = ttk.Frame(f)
        claves_tt.columnconfigure((0, 1), weight=1, uniform="tt")
        ttk.Entry(claves_tt, textvariable=tt_clave, font=(L, 10)).grid(row=0, column=0, sticky="ew", padx=(0, px(6)))
        ttk.Entry(claves_tt, textvariable=tt_secreto, show="•", font=(L, 10)).grid(row=0, column=1, sticky="ew")
        linea(f, 4, "Client key · secret", claves_tt)
        ttk.Checkbutton(f, text="Publicar en TikTok (llega como borrador: lo publicas con un toque desde el móvil)",
                        variable=var["tiktok"]).grid(row=5, column=0, columnspan=3, sticky="w", pady=(px(4), 0))
        ttk.Checkbutton(f, text="Avisar a YouTube de que la historia y la voz están hechas con IA",
                        variable=var["sintetico"]).grid(row=6, column=0, columnspan=3, sticky="w", pady=(px(14), 0))

        for i, nombre in enumerate(("Historias", "Vídeos", "Publicar")):
            b = Pildora(pestanas, nombre, lambda i=i: mostrar(i), "fantasma")
            b.pack(side="left", padx=(0, px(6)))
            botones_p.append(b)
        mostrar(0)

        def guardar(cerrar=True):
            try:
                lista = [datetime.strptime(h, "%H:%M").strftime("%H:%M") for h in re.split(r"[,;\s]+", horas.get()) if h]
                diaria = datetime.strptime(hora.get().strip(), "%H:%M").strftime("%H:%M")
            except ValueError:
                messagebox.showwarning("Hora no válida", "Escribe las horas así: 09:00 (y separa varias con comas).", parent=v)
                return False
            nuevo = {**cfg, **{k: b.get() for k, b in var.items()}, "modelo": modelo.get().strip() or au.POR_DEFECTO["modelo"],
                     "cola": int(cola.get()), "hora": diaria, "horas_publicacion": lista or au.POR_DEFECTO["horas_publicacion"]}
            au.guardar_secretos(gemini=clave.get().strip(), tiktok={**(au.secretos().get("tiktok") or {}),
                                                                   "client_key": tt_clave.get().strip(), "client_secret": tt_secreto.get().strip()})
            if nuevo["activo"] and not clave.get().strip():
                messagebox.showwarning("Falta la clave de Gemini", "Sin la clave, el piloto solo creará y publicará "
                                       "las historias que apruebes tú; no podrá escribir nuevas.", parent=v)
            if nuevo["activo"] != cfg["activo"] or (nuevo["activo"] and diaria != cfg["hora"]):
                try:
                    au.programar(nuevo["activo"], diaria)
                except Exception as e:
                    messagebox.showerror("No se pudo programar la tarea de Windows", str(e), parent=v)
                    nuevo["activo"] = cfg["activo"]
            au.guardar_ajustes(nuevo)
            self.pintar_piloto()
            if cerrar:
                v.destroy()
            return True

        ttk.Checkbutton(c, text="Piloto activado: una pasada al día, aunque la app esté cerrada", variable=var["activo"],
                        style="Grande.TCheckbutton").grid(row=4, column=0, sticky="w", pady=(px(22), 0))
        botones = ttk.Frame(c)
        botones.grid(row=5, column=0, sticky="ew", pady=(px(18), 0))
        Pildora(botones, "▶  Hacer una pasada ahora", lambda: guardar() and self.pasada(), "fantasma").pack(side="left")
        Pildora(botones, "Guardar", guardar, "primario").pack(side="right")
        Pildora(botones, "Cancelar", v.destroy, "fantasma").pack(side="right", padx=(0, px(8)))
        self.centrar(v)

    def pasada(self):
        """Una pasada del piloto ahora mismo, con su detalle en el registro."""
        if self.ocupado:
            return

        def trabajo():
            ok = "piloto"
            try:
                au.pasada()
            except gv.Cancelado:
                ok = "cancelado"
            except Exception as e:
                self.q.put(("log", f"\n❌ Error: {e}\n{traceback.format_exc()}"))
                ok = False
            self.q.put(("fin", ok))
        self.empezar("El piloto está trabajando…", trabajo)

    # ── cerrar y errores ─────────────────────────────────────────────────
    def cerrar(self):
        if self.ocupado:
            if not messagebox.askyesno("Hay un trabajo en marcha", "Se están creando vídeos. ¿Cancelar y salir?", parent=self):
                return
            self.cancelando = True
            gv.cancelar()
        self.destroy()

    def report_callback_exception(self, tipo, valor, tb):
        """Un error dentro de la ventana no la tumba ni se pierde: queda en error.log y se avisa."""
        detalle = "".join(traceback.format_exception(tipo, valor, tb))
        try:
            gv.DATOS.mkdir(parents=True, exist_ok=True)
            with open(gv.DATOS / "error.log", "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.now():%d/%m/%Y %H:%M:%S}\n{detalle}")
        except OSError:
            pass
        self.q.put(("log", f"❌ Error inesperado: {valor}"))
        self.aviso(f"Algo ha fallado ({valor}). Más detalle en «Carpetas › Datos de la app › error.log».", ROJO)

    # ── mensajes del hilo de trabajo ─────────────────────────────────────
    def bucle(self):
        """Pinta lo que llega del hilo de trabajo, por tandas: aunque lleguen miles de líneas, la ventana responde."""
        try:
            progreso = None
            for _ in range(MENSAJES_POR_TURNO):
                try:
                    tipo, dato = self.q.get_nowait()
                except queue.Empty:
                    break
                if tipo == "prog":
                    progreso = dato   # solo importa el último
                else:
                    self.mensaje(tipo, dato)
            if progreso is not None:
                self.relleno.place_configure(relwidth=progreso)
            if int(self.texto.index("end-1c").split(".")[0]) > MAX_LINEAS_LOG:
                self.texto.delete("1.0", f"{MAX_LINEAS_LOG // 4}.0")
        except Exception:
            self.report_callback_exception(*sys.exc_info())
        finally:
            self.after(40 if not self.q.empty() else 100, self.bucle)

    def mensaje(self, tipo, dato):
        if tipo == "log":
            self.texto.insert("end", dato + "\n", next((t for s, t in MARCAS_LOG if s in dato), ""))
            self.texto.see("end")
            if dato.strip() and self.ocupado and not self.cancelando:
                self.estado["text"] = dato.strip().splitlines()[0][:140]
        elif tipo == "sonar":
            self.btn_escuchar.poner(estado="normal")
            self.estado["text"] = ""
            if dato:
                winsound.PlaySound(str(dato), winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif tipo == "gpu":
            if dato:
                self.casilla_gpu.configure(text="Usar gráfica NVIDIA", state="normal")
            else:
                self.casilla_gpu.configure(text="Gráfica NVIDIA (no hay en este PC)")
        elif tipo == "llamar":
            dato()
        elif tipo == "fin":
            self.terminar(dato)

    def terminar(self, ok):
        self.ocupado = self.cancelando = False
        self.btn_crear.poner("Crear vídeos", estado="normal", estilo="primario")
        self.btn_piloto.poner(estado="normal")
        if ok == "cancelado":
            self.relleno.place_configure(relwidth=0)
            self.aviso("Cancelado. Lo que ya estaba hecho se queda guardado para la próxima vez.", AMARILLO)
        elif ok == "piloto":  # puede haber notas nuevas o con otro estado: se refresca la lista sin borrar el registro
            actual = self.g.ruta if self.g else None
            self.rutas = gv.guiones_de(gv.CARPETA_GUIONES)
            if actual and actual not in self.rutas:
                self.rutas.insert(0, actual)
            self.refrescar_nombres()
            if actual:
                self.combo_guion.current(self.rutas.index(actual))
                self.btn_aprobar.grid() if gv.estado_nota(actual) == "pendiente" else self.btn_aprobar.grid_remove()
            self.relleno.place_configure(relwidth=1.0)
            self.aviso("✓ Pasada del piloto terminada: lo que ha hecho está en los detalles.", VERDE)
        elif ok:
            self.relleno.place_configure(relwidth=1.0)
            self.aviso("✓ Vídeos listos. Te abro la carpeta.", VERDE)
            self.refrescar_nombres()  # el estado de la nota puede haber cambiado
            self.abrir_salida()
        else:
            self.aviso("No se pudo terminar. Mira los detalles.", ROJO)
            if not self.mostrar_log:
                self.alternar_log()


def principal():
    if sys.argv[1:2] == ["--crear"]:   # crear vídeos sin ventana:  "Reddit Video.exe" --crear historia.md --solo youtube
        if gv.INSTALADA:   # sin consola: lo que sale se guarda en un archivo
            gv.DATOS.mkdir(parents=True, exist_ok=True)
            sys.stdout = sys.stderr = open(gv.DATOS / "crear.log", "w", encoding="utf-8", buffering=1)
        try:
            return gv.main(sys.argv[2:])
        except SystemExit as e:   # un error esperado (falta ffmpeg…): su mensaje y código de salida, sin cuadro de PyInstaller
            print(e.code or "")
            os._exit(1 if e.code else 0)
        except BaseException:
            traceback.print_exc()
            os._exit(1)
    if any(a.startswith("--") for a in sys.argv[1:]):   # tarea programada o línea de comandos: sin ventana
        return au.main()
    if not una_sola_ventana():
        ctypes.windll.user32.MessageBoxW(0, "Reddit Video ya está abierto.", "Reddit Video", 0x40)
        return
    App().mainloop()


if __name__ == "__main__":
    try:
        principal()
    except Exception:   # que un fallo al arrancar deje rastro y un mensaje claro, no un cuadro técnico
        gv.DATOS.mkdir(parents=True, exist_ok=True)
        with open(gv.DATOS / "error.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now():%d/%m/%Y %H:%M:%S}\n{traceback.format_exc()}")
        ctypes.windll.user32.MessageBoxW(0, f"Reddit Video no ha podido arrancar.\nEl detalle está en:\n{gv.DATOS / 'error.log'}",
                                         "Reddit Video", 0x10)
