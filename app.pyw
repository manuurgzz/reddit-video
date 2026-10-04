"""Ventana para crear los vídeos sin terminal. Doble clic en crear_video.bat (o en este archivo)."""
import os
import queue
import random
import re
import threading
import tkinter as tk
import webbrowser
import winsound
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, font, messagebox, ttk
from urllib.parse import quote

import automatizar as au
import guion_a_video as gv

try:  # texto nítido en pantallas con escalado
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# Paleta: el modo oscuro de Reddit
FONDO, TARJETA, CAMPO, CAMPO_ACTIVO, BORDE = "#0E1113", "#181C1F", "#22292D", "#2C353A", "#2E363B"
TEXTO, SUAVE, APAGADO, CONSOLA = "#F2F4F5", "#8BA2AD", "#5F6E76", "#0A0C0D"
NARANJA, NARANJA_ACTIVO, NARANJA_PULSADO = "#FF4500", "#FF5F24", "#D93A00"
VERDE, AMARILLO, ROJO = "#46D160", "#FFB000", "#FF585B"

LISTO = "Elige una historia y pulsa «Crear vídeos»."
MARCAS_LOG = (("❌", "error"), ("⚠", "aviso"), ("✅", "ok"))  # color de cada línea del registro
TILDES = {"Alvaro": "Álvaro", "Salome": "Salomé", "Tomas": "Tomás"}


def nombre_voz(v):
    """es-ES-AlvaroNeural -> Álvaro"""
    n = v.split("-")[-1].removesuffix("Neural")
    return TILDES.get(n, n)


def etiqueta_voz(v):
    return f"{nombre_voz(v)}  ·  {gv.VOCES[v]}" if v in gv.VOCES else v


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Reddit Video")
        self.configure(bg=FONDO)
        self.q = queue.Queue()
        gv.log = lambda m="": self.q.put(("log", str(m)))
        gv.al_progresar = lambda f: self.q.put(("prog", f))
        gv.preparar_carpetas()
        self.g = None
        self.rutas = []
        escala = self.winfo_fpixels("1i") / 96
        self.px = px = lambda n: round(n * escala)
        self.estilos()
        self.icono()
        L = self.letra

        self.raiz = raiz = ttk.Frame(self, style="Fondo.TFrame", padding=(px(24), px(18)))
        raiz.pack(fill="both", expand=True)
        raiz.columnconfigure((0, 1), weight=1, uniform="col")

        # Cabecera
        cab = ttk.Frame(raiz, style="Fondo.TFrame")
        cab.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, px(14)))
        self.cuadro(cab, "", NARANJA, "white", 44).pack(side="left")
        marca = ttk.Frame(cab, style="Fondo.TFrame")
        marca.pack(side="left", padx=px(14))
        ttk.Label(marca, text="Reddit Video", style="Marca.TLabel").pack(anchor="w")
        ttk.Label(marca, text="Convierte tus guiones en vídeos de historias de Reddit", style="Lema.TLabel").pack(anchor="w")

        # 1 · Historia
        cab, c = self.tarjeta(1, 0, "1", "Historia", "Pega una historia o elige una nota: los cortes se calculan solos", span=2)
        ttk.Button(cab, text="Conectar Obsidian…", command=self.conectar).pack(side="right")
        self.origen = ttk.Label(cab, style="Suave.TLabel")
        self.origen.pack(side="right", padx=(0, px(14)))
        self.punto = ttk.Label(cab, text="●", style="Suave.TLabel")
        self.punto.pack(side="right", padx=(0, px(5)))
        c.columnconfigure(0, weight=1)
        self.combo_guion = ttk.Combobox(c, state="readonly", font=(L, 10))
        self.combo_guion.grid(row=0, column=0, sticky="ew")
        self.combo_guion.bind("<<ComboboxSelected>>", lambda e: self.cargar(self.rutas[self.combo_guion.current()]))
        ttk.Button(c, text="＋  Pegar historia…", style="Acento.TButton", command=self.pegar_historia).grid(row=0, column=1, sticky="ns", padx=(px(8), 0))
        ttk.Button(c, text="Abrir nota", command=self.abrir_nota).grid(row=0, column=2, sticky="ns", padx=(px(8), 0))
        ttk.Button(c, text="Otro archivo…", command=self.elegir_archivo).grid(row=0, column=3, sticky="ns", padx=(px(8), 0))
        self.info = ttk.Label(c, style="Suave.TLabel")
        self.info.grid(row=1, column=0, columnspan=3, sticky="w", pady=(px(10), 0))
        self.btn_aprobar = ttk.Button(c, text="✓  Aprobar para el piloto", style="Acento.TButton", command=self.aprobar)
        self.btn_aprobar.grid(row=1, column=1, columnspan=3, sticky="e", pady=(px(10), 0))
        self.btn_aprobar.grid_remove()

        # 2 · Post de Reddit: campos a la izquierda, vista previa de la tarjeta a la derecha
        cab, c = self.tarjeta(2, 0, "2", "Post de Reddit", "La tarjeta con la que arranca el vídeo", span=2)
        c.columnconfigure(0, weight=3)
        c.columnconfigure(1, weight=2)
        self.subreddit, self.usuario, self.titulo = tk.StringVar(), tk.StringVar(), tk.StringVar()
        campos = ttk.Frame(c)
        campos.grid(row=0, column=0, sticky="new", padx=(0, px(28)))
        campos.columnconfigure((0, 1), weight=1, uniform="campos")
        ttk.Label(campos, text="Subreddit", style="Campo.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(campos, textvariable=self.subreddit, font=(L, 10)).grid(row=1, column=0, sticky="ew", padx=(0, px(12)), pady=(px(5), 0))
        ttk.Label(campos, text="Usuario", style="Campo.TLabel").grid(row=0, column=1, sticky="w")
        u = ttk.Frame(campos)
        u.grid(row=1, column=1, sticky="ew", pady=(px(5), 0))
        u.columnconfigure(0, weight=1)
        ttk.Entry(u, textvariable=self.usuario, font=(L, 10)).grid(row=0, column=0, sticky="ew")
        ttk.Button(u, text="🎲", width=3, command=lambda: self.usuario.set(gv.usuario_al_azar())).grid(row=0, column=1, sticky="ns", padx=(px(6), 0))
        ttk.Label(campos, text="Título", style="Campo.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(px(14), 0))
        ttk.Entry(campos, textvariable=self.titulo, font=(L, 10)).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(px(5), 0))

        vista = ttk.Frame(c)
        vista.grid(row=0, column=1, sticky="nsew")
        ttk.Label(vista, text="Vista previa", style="Campo.TLabel").pack(anchor="w")
        post = tk.Frame(vista, bg="white", padx=px(16), pady=px(12))
        post.pack(fill="x", pady=(px(5), 0))
        fila = tk.Frame(post, bg="white")
        fila.pack(fill="x")
        tk.Label(fila, text="", fg=NARANJA, bg="white", font=(self.iconos, 20)).pack(side="left")  # avatar
        col = tk.Frame(fila, bg="white")
        col.pack(side="left", padx=(px(6), 0))
        self.v_sub = tk.Label(col, bg="white", fg="#141414", font=(self.negrita, 10))
        self.v_sub.pack(anchor="w")
        self.v_autor = tk.Label(col, bg="white", fg="#7C7C7C", font=(L, 9))
        self.v_autor.pack(anchor="w")
        tk.Label(fila, text="•••", bg="white", fg="#8C8C8C", font=(self.negrita, 10)).pack(side="right", anchor="n")
        self.v_titulo = tk.Label(post, bg="white", fg="#141414", font=(self.negrita, 11),
                                 wraplength=px(320), justify="left", anchor="w")
        self.v_titulo.pack(fill="x", pady=(px(8), 0))
        for v in (self.subreddit, self.usuario, self.titulo):
            v.trace_add("write", lambda *_: self.pintar_post())

        # 3 · Voz: quién narra, con su ficha
        cab, c = self.tarjeta(3, 0, "3", "Voz", "Se sortea en cada proyecto nuevo y se recuerda")
        c.columnconfigure(1, weight=1)
        self.cuadro(c, "", CAMPO, NARANJA, 48).grid(row=0, column=0, rowspan=2, padx=(0, px(14)))
        self.voz_nombre = ttk.Label(c, style="Voz.TLabel")
        self.voz_nombre.grid(row=0, column=1, sticky="sw")
        self.voz_detalle = ttk.Label(c, style="Suave.TLabel")
        self.voz_detalle.grid(row=1, column=1, sticky="nw")
        self.btn_escuchar = ttk.Button(c, text="▶  Escuchar", style="Acento.TButton", command=self.escuchar)
        self.btn_escuchar.grid(row=0, column=2, rowspan=2)
        fila = ttk.Frame(c)
        fila.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(px(16), 0))
        fila.columnconfigure(0, weight=1)
        self.combo_voz = ttk.Combobox(fila, state="readonly", font=(L, 10))
        self.combo_voz.grid(row=0, column=0, sticky="ew")
        self.combo_voz.bind("<<ComboboxSelected>>", lambda e: (self.pintar_voz(), self.guardar()))
        ttk.Button(fila, text="🎲  Otra al azar", command=self.voz_azar).grid(row=0, column=1, sticky="ns", padx=(px(8), 0))

        # 4 · Qué crear
        cab, c = self.tarjeta(3, 1, "4", "Qué crear", "Formatos y opciones")
        self.op = {k: tk.BooleanVar(value=v) for k, v in
                   [("youtube", True), ("shorts", True), ("musica", True), ("rapido", False), ("gpu", False)]}
        c.columnconfigure((0, 1), weight=1, uniform="formatos")
        self.formato(c, "youtube", "YouTube", "Vídeo completo · 16:9", 16, 9).grid(row=0, column=0, sticky="nsew", padx=(0, px(6)))
        self.formato(c, "shorts", "Shorts", "TikTok · Reels · 9:16", 9, 16).grid(row=0, column=1, sticky="nsew", padx=(px(6), 0))
        for i, (k, txt) in enumerate([("musica", "Música de fondo"), ("gpu", "Usar gráfica NVIDIA"),
                                      ("rapido", "Prueba rápida (media calidad)")]):
            casilla = ttk.Checkbutton(c, text=txt, variable=self.op[k])
            casilla.grid(row=1 + i // 2, column=i % 2, sticky="w", pady=(px(10) if i < 2 else px(2), 0))
            if k == "gpu" and not gv.hay_nvenc():
                casilla.configure(text="Gráfica NVIDIA (no hay)", state="disabled")

        # Barra de acción: estado + progreso a la izquierda, botón principal a la derecha
        acciones = ttk.Frame(raiz, style="Fondo.TFrame")
        acciones.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(px(2), 0))
        acciones.columnconfigure(0, weight=1)
        self.estado = ttk.Label(acciones, text=LISTO, style="Estado.TLabel")
        self.estado.grid(row=0, column=0, sticky="sw", padx=(px(2), px(24)))
        pista = tk.Frame(acciones, height=px(6), bg=CAMPO)  # barra de progreso fina (la de clam no baja de ~12 px)
        pista.grid(row=1, column=0, sticky="ew", padx=(0, px(24)), pady=(px(8), px(4)))
        self.relleno = tk.Frame(pista, bg=NARANJA)
        self.relleno.place(x=0, y=0, relheight=1, relwidth=0)
        self.btn_piloto = ttk.Button(acciones, command=self.piloto)
        self.btn_piloto.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(0, px(10)))
        self.btn_crear = ttk.Button(acciones, text="Crear vídeos", width=18, style="Primario.TButton", command=self.crear)
        self.btn_crear.grid(row=0, column=2, rowspan=2, sticky="nsew")

        # Registro (detalle de lo que va haciendo) + accesos a carpetas
        marco = tk.Frame(raiz, bg=TARJETA, highlightthickness=1, highlightbackground=BORDE)
        marco.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(px(16), 0))
        raiz.rowconfigure(5, weight=1)
        cab = ttk.Frame(marco, padding=(px(20), px(8), px(12), px(8)))
        cab.pack(fill="x")
        ttk.Label(cab, text="Registro", style="Seccion.TLabel").pack(side="left")
        carpetas = ttk.Frame(cab)
        carpetas.pack(side="right")
        ttk.Label(carpetas, text="Abrir carpeta:", style="Suave.TLabel").pack(side="left", padx=(0, px(4)))
        ttk.Button(carpetas, text="Vídeos creados", style="Enlace.TButton", command=self.abrir_salida).pack(side="left")
        ttk.Button(carpetas, text="Fondos", style="Enlace.TButton", command=lambda: os.startfile(gv.CARPETA_FONDOS)).pack(side="left")
        ttk.Button(carpetas, text="Música", style="Enlace.TButton", command=lambda: os.startfile(gv.CARPETA_MUSICA)).pack(side="left")
        consola = tk.Frame(marco, bg=CONSOLA)
        consola.pack(fill="both", expand=True)
        self.texto = tk.Text(consola, height=6, font=(self.mono, 9), wrap="word", relief="flat", bd=0,
                             highlightthickness=0, bg=CONSOLA, fg="#C3CED4", insertbackground=TEXTO,
                             selectbackground=NARANJA, selectforeground="white", padx=px(18), pady=px(12))
        desliz = ttk.Scrollbar(consola, command=self.texto.yview)
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
        self.geometry(f"{px(1040)}x{min(px(960), self.winfo_screenheight() - px(80))}")
        self.minsize(px(900), px(720))
        self.barra_oscura()
        self.after(100, self.bucle)

    # ── aspecto ──────────────────────────────────────────────────────────
    def estilos(self):
        px = self.px
        familias = set(font.families(self))
        elige = lambda *ns: next((n for n in ns if n in familias), ns[-1])  # Windows 11, si no Windows 10
        self.letra = L = elige("Segoe UI Variable Text", "Segoe UI")
        self.negrita = B = elige("Segoe UI Variable Text Semibold", "Segoe UI Semibold")
        self.titular = T = elige("Segoe UI Variable Display Semib", "Segoe UI Semibold")
        self.iconos = elige("Segoe Fluent Icons", "Segoe MDL2 Assets")
        self.mono = elige("Cascadia Mono", "Consolas")

        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure(".", background=TARJETA, foreground=TEXTO, font=(L, 10), bordercolor=BORDE,
                     lightcolor=CAMPO, darkcolor=CAMPO, troughcolor=CAMPO, focuscolor=SUAVE, arrowcolor=SUAVE,
                     insertcolor=TEXTO, selectbackground=NARANJA, selectforeground="white")
        st.configure("Fondo.TFrame", background=FONDO)
        st.configure("Marca.TLabel", background=FONDO, font=(T, 18))
        st.configure("Lema.TLabel", background=FONDO, foreground=SUAVE)
        st.configure("Estado.TLabel", background=FONDO, foreground=SUAVE)
        st.configure("Paso.TLabel", foreground=NARANJA, font=(T, 13))
        st.configure("Seccion.TLabel", font=(T, 13))
        st.configure("Suave.TLabel", foreground=SUAVE, font=(L, 9))
        st.configure("Campo.TLabel", foreground=SUAVE, font=(B, 9))
        st.configure("Voz.TLabel", font=(T, 15))

        def boton(nombre, fondo, activo, pulsado, texto, borde, **extra):
            st.configure(nombre, **{"background": fondo, "foreground": texto, "bordercolor": borde, "lightcolor": fondo,
                                    "darkcolor": fondo, "padding": (px(14), px(7)), "font": (B, 9), **extra})
            colores = [("disabled", CAMPO), ("pressed", pulsado), ("active", activo)]
            st.map(nombre, background=colores, lightcolor=colores, darkcolor=colores,
                   bordercolor=[("disabled", CAMPO)], foreground=[("disabled", APAGADO)])
        boton("TButton", CAMPO, CAMPO_ACTIVO, BORDE, TEXTO, BORDE)
        boton("Acento.TButton", "#3B1D12", "#4A2416", "#2E160D", "#FF8A5C", "#5A2A18")
        boton("Enlace.TButton", TARJETA, CAMPO, BORDE, SUAVE, TARJETA, padding=(px(8), px(4)), focuscolor=TARJETA)
        boton("Primario.TButton", NARANJA, NARANJA_ACTIVO, NARANJA_PULSADO, "white", NARANJA,
              padding=(px(16), px(12)), font=(T, 13), focuscolor="white")

        # Casillas con check de verdad (la de «clam» dibuja un aspa que parece una X)
        self._casillas = vacia, marcada = self.casilla(False), self.casilla(True)
        st.element_create("Casilla.indicator", "image", vacia, ("selected", marcada),
                          width=vacia.width() + px(8), sticky="w")
        st.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("Casilla.indicator", {"side": "left", "sticky": ""}),
            ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [("Checkbutton.label", {"sticky": "nswe"})]})]})])
        st.configure("TCheckbutton", padding=px(2))
        st.map("TCheckbutton", background=[("active", TARJETA)])
        st.configure("Formato.TCheckbutton", background=CAMPO, font=(T, 12))
        st.map("Formato.TCheckbutton", background=[("active", CAMPO)])

        campo = dict(fieldbackground=CAMPO, background=CAMPO, foreground=TEXTO, bordercolor=BORDE,
                     lightcolor=CAMPO, darkcolor=CAMPO, padding=(px(9), px(6)))
        st.configure("TEntry", **campo)
        st.map("TEntry", bordercolor=[("focus", NARANJA)], lightcolor=[("focus", CAMPO)])
        st.configure("TCombobox", arrowsize=px(14), **campo)
        st.map("TCombobox", fieldbackground=[("readonly", CAMPO)], foreground=[("readonly", TEXTO)],
               background=[("active", CAMPO_ACTIVO), ("readonly", CAMPO)], arrowcolor=[("active", TEXTO)],
               selectbackground=[("readonly", CAMPO)], selectforeground=[("readonly", TEXTO)],
               bordercolor=[("focus", NARANJA), ("active", SUAVE)], lightcolor=[("focus", CAMPO)])
        for opcion, valor in (("background", CAMPO), ("foreground", TEXTO), ("selectBackground", NARANJA),
                              ("selectForeground", "white"), ("font", f"{{{L}}} 10")):
            self.option_add(f"*TCombobox*Listbox.{opcion}", valor)

        st.configure("Vertical.TScrollbar", background=CAMPO, troughcolor=CONSOLA, bordercolor=CONSOLA,
                     lightcolor=CAMPO, darkcolor=CAMPO, gripcount=0, arrowsize=px(12))
        st.map("Vertical.TScrollbar", background=[("active", CAMPO_ACTIVO)])

    def casilla(self, marcada):
        """Casilla de 16 px dibujada píxel a píxel; la marcada lleva un check blanco suavizado."""
        s = self.px(16)
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

    def icono(self, n=64):
        """Icono de la ventana: círculo naranja con un «play» blanco."""
        img = tk.PhotoImage(width=n, height=n)
        r, alto = n / 2, n * 0.24
        for y in range(n):
            dy = abs(y + 0.5 - r)
            if dy < r:
                dx = (r * r - dy * dy) ** 0.5
                img.put(NARANJA, to=(round(r - dx), y, round(r + dx), y + 1))
            if dy < alto:
                x0 = round(n * 0.38)
                img.put("white", to=(x0, y, x0 + max(round(n * 0.42 * (1 - dy / alto)), 1), y + 1))
        self.iconphoto(True, img)
        self._icono = img

    def barra_oscura(self):
        """Barra de título oscura en Windows 10/11 (si no se puede, se queda la normal)."""
        try:
            self.update_idletasks()
            ctypes.windll.dwmapi.DwmSetWindowAttribute(int(self.wm_frame(), 16), 20, ctypes.byref(ctypes.c_int(1)), 4)
        except Exception:
            pass

    def cuadro(self, padre, glifo, fondo, color, lado):
        """Cuadrado de color con un icono de Segoe Fluent Icons centrado."""
        f = tk.Frame(padre, bg=fondo, width=self.px(lado), height=self.px(lado))
        tk.Label(f, text=glifo, bg=fondo, fg=color, font=(self.iconos, round(lado * 0.34))).place(relx=0.5, rely=0.5, anchor="center")
        return f

    def tarjeta(self, fila, col, paso, titulo, lema, span=1):
        """Tarjeta con borde fino y cabecera «paso  Título  lema». Devuelve (cabecera, cuerpo)."""
        px = self.px
        marco = tk.Frame(self.raiz, bg=TARJETA, highlightthickness=1, highlightbackground=BORDE)
        marco.grid(row=fila, column=col, columnspan=span, sticky="nsew", pady=(0, px(12)),
                   padx=0 if span == 2 else ((0, px(7)) if col == 0 else (px(7), 0)))
        cab = ttk.Frame(marco, padding=(px(20), px(14), px(20), 0))
        cab.pack(fill="x")
        ttk.Label(cab, text=paso, style="Paso.TLabel").pack(side="left", padx=(0, px(10)))
        ttk.Label(cab, text=titulo, style="Seccion.TLabel").pack(side="left")
        ttk.Label(cab, text=lema, style="Suave.TLabel").pack(side="left", padx=(px(12), 0), pady=(px(4), 0))
        cuerpo = ttk.Frame(marco, padding=(px(20), px(12), px(20), px(16)))
        cuerpo.pack(fill="both", expand=True)
        return cab, cuerpo

    def formato(self, padre, clave, titulo, detalle, ancho, alto):
        """Casilla grande (YouTube / Shorts) con el dibujo de su proporción; se marca con clic en cualquier parte."""
        px, var = self.px, self.op[clave]
        marco = tk.Frame(padre, bg=CAMPO, highlightthickness=px(2), cursor="hand2")
        lado = px(30)
        w, h = (lado, lado * alto // ancho) if ancho > alto else (lado * ancho // alto, lado)
        lienzo = tk.Canvas(marco, width=lado, height=lado, bg=CAMPO, highlightthickness=0)
        rect = lienzo.create_rectangle((lado - w) // 2 + 1, (lado - h) // 2 + 1, (lado + w) // 2 - 1, (lado + h) // 2 - 1, width=px(2))
        lienzo.grid(row=0, column=0, rowspan=2, padx=(px(14), px(12)), pady=px(10))
        ttk.Checkbutton(marco, text=titulo, variable=var, style="Formato.TCheckbutton").grid(row=0, column=1, sticky="sw", pady=(px(10), 0))
        sub = tk.Label(marco, text=detalle, bg=CAMPO, fg=SUAVE, font=(self.letra, 9))
        sub.grid(row=1, column=1, sticky="nw", padx=(px(2), px(10)), pady=(0, px(10)))

        def pintar(*_):
            color = NARANJA if var.get() else BORDE
            marco.configure(highlightbackground=color, highlightcolor=color)
            lienzo.itemconfigure(rect, outline=NARANJA if var.get() else SUAVE)
        var.trace_add("write", pintar)
        pintar()
        for w in (marco, lienzo, sub):
            w.bind("<Button-1>", lambda e: var.set(not var.get()))
        return marco

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

    # ── guion y proyecto ─────────────────────────────────────────────────
    def cargar_lista(self, elegida=None):
        d = gv.CARPETA_GUIONES
        boveda = gv.leer_ajustes().get("boveda")
        self.punto.configure(foreground=VERDE if boveda else SUAVE)
        self.origen["text"] = f"Obsidian · {Path(boveda).name} › {d.name}" if boveda else f"Carpeta local · {d}"
        self.rutas = gv.guiones_de(d)
        if elegida and elegida not in self.rutas:
            self.rutas.insert(0, elegida)
        self.refrescar_nombres()
        if self.rutas:
            self.combo_guion.current(self.rutas.index(elegida) if elegida else 0)
            self.cargar(self.rutas[self.combo_guion.current()])
        else:
            self.info.configure(text=f"⚠ No hay notas en {d}. Conecta Obsidian o elige otro archivo.", foreground=AMARILLO)

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
        px, L = self.px, self.letra
        v = tk.Toplevel(self, bg=TARJETA)
        v.title("Pegar historia")
        v.transient(self)
        v.grab_set()
        c = ttk.Frame(v, padding=px(20))
        c.pack(fill="both", expand=True)
        c.columnconfigure(0, weight=1)
        c.rowconfigure(3, weight=1)
        titulo, sub = tk.StringVar(), tk.StringVar(value="r/AITAH")
        ttk.Label(c, text="Título del post", style="Campo.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(c, text="Subreddit", style="Campo.TLabel").grid(row=0, column=1, sticky="w", padx=(px(12), 0))
        campo_titulo = ttk.Entry(c, textvariable=titulo, font=(L, 10))
        campo_titulo.grid(row=1, column=0, sticky="ew", pady=(px(5), px(14)))
        ttk.Entry(c, textvariable=sub, width=16, font=(L, 10)).grid(row=1, column=1, sticky="ew", padx=(px(12), 0), pady=(px(5), px(14)))
        ttk.Label(c, text="Historia: pégala tal cual. Si tiene secciones con «#», se usan como pistas para los cortes.",
                  style="Campo.TLabel").grid(row=2, column=0, columnspan=2, sticky="w")
        texto = tk.Text(c, width=90, height=22, wrap="word", font=(L, 10), bg=CAMPO, fg=TEXTO, insertbackground=TEXTO,
                        selectbackground=NARANJA, selectforeground="white", relief="flat", padx=px(12), pady=px(10),
                        highlightthickness=1, highlightbackground=BORDE, highlightcolor=NARANJA)
        texto.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(px(5), px(16)))

        def guardar():
            t, cuerpo, s = titulo.get().strip(), texto.get("1.0", "end").strip(), sub.get().strip()
            if not t or not cuerpo:
                return messagebox.showwarning("Falta algo", "Escribe el título del post y pega la historia.", parent=v)
            nombre = re.sub(r"[^a-z0-9]+", "-", gv.quitar_tildes(t.lower())).strip("-")[:40] or "historia"
            ruta, n = gv.CARPETA_GUIONES / f"{date.today()}_{nombre}.md", 2
            while ruta.exists():
                ruta, n = gv.CARPETA_GUIONES / f"{date.today()}_{nombre}-{n}.md", n + 1
            ruta.parent.mkdir(parents=True, exist_ok=True)
            cabecera = f"---\nsubreddit: r/{s.removeprefix('r/')}\n---\n" if s else ""
            ruta.write_text(f"{cabecera}# {t}\n\n{cuerpo}\n", encoding="utf-8")
            v.destroy()
            self.cargar_lista(ruta)

        botones = ttk.Frame(c)
        botones.grid(row=4, column=0, columnspan=2, sticky="e")
        ttk.Button(botones, text="Cancelar", command=v.destroy).pack(side="left")
        ttk.Button(botones, text="Guardar y usar", style="Acento.TButton", command=guardar).pack(side="left", padx=(px(8), 0))
        campo_titulo.focus_set()

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
            os.startfile(self.g.ruta)

    def elegir_archivo(self):
        r = filedialog.askopenfilename(title="Elige un guion", filetypes=[("Historia o guion", "*.md *.txt")],
                                       initialdir=gv.CARPETA_GUIONES if gv.CARPETA_GUIONES.is_dir() else None)
        if r:
            self.cargar_lista(Path(r))

    def cargar(self, ruta):
        self.g = gv.parsear_guion(ruta)
        self.texto.delete("1.0", "end")
        self.btn_aprobar.grid() if gv.estado_nota(ruta) == "pendiente" else self.btn_aprobar.grid_remove()
        if not self.g.escenas:
            self.info.configure(text="⚠ No encuentro texto que narrar en esta nota.", foreground=AMARILLO)
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
                                 + (f"      ⚠ Sin clips en {', '.join(sin_clips)}: se usarán otros fondos" if sin_clips else ""),
                            foreground=AMARILLO if sin_clips else SUAVE)
        gv.resumen(self.g)

    def guardar(self):
        """Guarda lo que hay en pantalla para este proyecto (lo lee guion_a_video al crear)."""
        if not self.g:
            return
        d = {"voz": self.voces[self.combo_voz.current()], "subreddit": self.subreddit.get().strip(),
             "usuario": self.usuario.get().strip()}
        if self.titulo.get().strip() != self.g.titulo:
            d["titulo"] = self.titulo.get().strip()
        gv.guardar_proyecto(self.g.slug, d)

    def voz_azar(self):
        actual = self.voces[self.combo_voz.current()]
        nueva = actual
        while nueva == actual:
            nueva = gv.voz_al_azar()
        self.combo_voz.current(self.voces.index(nueva))
        self.pintar_voz()
        self.guardar()

    def escuchar(self):
        if not self.g:
            return
        voz = self.voces[self.combo_voz.current()]
        frase = self.g.escenas[0].lineas[0].texto_tts
        self.btn_escuchar["state"] = "disabled"
        self.estado.configure(text="Preparando la muestra de voz…", foreground=SUAVE)

        def trabajo():
            try:
                self.q.put(("sonar", gv.muestra_voz(voz, frase)))
            except Exception as e:
                self.q.put(("log", f"❌ No se pudo generar la muestra: {e}"))
                self.q.put(("sonar", None))
        threading.Thread(target=trabajo, daemon=True).start()

    # ── crear ────────────────────────────────────────────────────────────
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
        self.btn_crear.config(state="disabled", text="Creando vídeos…")
        self.estado.configure(foreground=TEXTO)
        self.texto.delete("1.0", "end")
        self.relleno.place_configure(relwidth=0)

        def trabajo():
            ok = False
            try:
                gv.main(args)
                ok = True
            except SystemExit as e:
                self.q.put(("log", str(e.code or "")))
            except Exception as e:
                self.q.put(("log", f"\n❌ Error: {e}"))
            self.q.put(("fin", ok))
        threading.Thread(target=trabajo, daemon=True).start()

    def abrir_salida(self):
        d = gv.CARPETA_SALIDA / self.g.slug if self.g else gv.CARPETA_SALIDA
        os.startfile(d if d.is_dir() else gv.CARPETA_SALIDA)

    # ── piloto automático (automatizar.py) ───────────────────────────────
    def aprobar(self):
        """La historia pasa a «aprobada»: el piloto creará y publicará sus vídeos en la próxima pasada."""
        au.poner_estado(self.g.ruta, "aprobada")
        self.refrescar_nombres()
        self.btn_aprobar.grid_remove()
        self.estado.configure(text="✓ Aprobada: el piloto creará y publicará sus vídeos en la próxima pasada.", foreground=VERDE)

    def pintar_piloto(self):
        activo = au.ajustes()["activo"]
        self.btn_piloto.configure(text="●  Piloto activo" if activo else "Piloto automático…",
                                  style="Acento.TButton" if activo else "TButton")

    def piloto(self):
        """Ajustes del piloto: Gemini escribe las historias y la app crea y publica los vídeos sola cada día."""
        px, L = self.px, self.letra
        cfg, sec = au.ajustes(), au.secretos()
        v = tk.Toplevel(self, bg=TARJETA)
        v.title("Piloto automático")
        v.transient(self)
        v.grab_set()
        v.resizable(False, False)
        c = ttk.Frame(v, padding=(px(24), px(16), px(24), px(20)))
        c.pack(fill="both", expand=True)
        c.columnconfigure(1, weight=1)
        fila = [0]

        def seccion(titulo, lema):
            ttk.Label(c, text=titulo, style="Seccion.TLabel").grid(row=fila[0], column=0, columnspan=3, sticky="w",
                                                                  pady=(px(16) if fila[0] else 0, 0))
            ttk.Label(c, text=lema, style="Suave.TLabel").grid(row=fila[0] + 1, column=0, columnspan=3, sticky="w", pady=(0, px(6)))
            fila[0] += 2

        def linea(texto, widget, extra=None):
            if isinstance(texto, str):
                texto = ttk.Label(c, text=texto, style="Campo.TLabel")
            texto.grid(row=fila[0], column=0, sticky="w", padx=(0, px(16)), pady=px(4))
            widget.grid(row=fila[0], column=1, sticky="ew", pady=px(4))
            if extra:
                extra.grid(row=fila[0], column=2, sticky="ew", padx=(px(8), 0), pady=px(4))
            fila[0] += 1

        def entrada(var, **kw):
            return ttk.Entry(c, textvariable=var, font=(L, 10), **kw)

        var = {k: tk.BooleanVar(value=bool(cfg[k])) for k in ("activo", "revision_humana", "gpu", "youtube", "tiktok", "sintetico")}
        clave, modelo = tk.StringVar(value=sec.get("gemini", "")), tk.StringVar(value=cfg["modelo"])
        cola, hora = tk.StringVar(value=str(cfg["cola"])), tk.StringVar(value=cfg["hora"])
        horas = tk.StringVar(value=", ".join(cfg["horas_publicacion"]))
        tt = sec.get("tiktok") or {}
        tt_clave, tt_secreto = tk.StringVar(value=tt.get("client_key", "")), tk.StringVar(value=tt.get("client_secret", ""))
        guia = lambda: os.startfile(gv.BASE / "docs" / "piloto-automatico.md")

        seccion("1 · Historias", "Gemini las escribe con tu «Prompt-historias-propias» de Obsidian")
        linea("Clave de Gemini", entrada(clave, show="•"),
              ttk.Button(c, text="Conseguir clave ↗", command=lambda: webbrowser.open("https://aistudio.google.com/apikey")))
        linea("Modelo", ttk.Combobox(c, textvariable=modelo, font=(L, 10), values=["gemini-3.8-flash", "gemini-3.1-pro-preview"]))
        linea("Historias en marcha", ttk.Combobox(c, textvariable=cola, values=[1, 2, 3, 4, 5], state="readonly", width=4, font=(L, 10)),
              ttk.Label(c, text="a la vez, como mucho", style="Suave.TLabel"))
        ttk.Checkbutton(c, text="Revisar yo cada historia antes de crear los vídeos (botón «✓ Aprobar»)",
                        variable=var["revision_humana"]).grid(row=fila[0], column=0, columnspan=3, sticky="w", pady=px(4))
        fila[0] += 1

        seccion("2 · Vídeos", "Cada día: escribe si hace falta, crea los vídeos de una historia aprobada y publica")
        gpu = ttk.Checkbutton(c, text="Usar gráfica NVIDIA", variable=var["gpu"])
        if not gv.hay_nvenc():
            var["gpu"].set(False)
            gpu.configure(text="Gráfica NVIDIA (no hay en este PC)", state="disabled")
        linea("Pasada diaria a las", entrada(hora, width=8), gpu)

        seccion("3 · Publicar", "Un short en cada hora; el vídeo largo sale con el primero")
        linea("Publicar a las", entrada(horas), ttk.Button(c, text="¿Cómo se conecta?", style="Enlace.TButton", command=guia))
        conectado = lambda ok: ("✓ Conectado", VERDE) if ok else ("Sin conectar", SUAVE)
        estado_yt = ttk.Label(c, style="Suave.TLabel", wraplength=px(330))
        estado_yt.configure(text=conectado(sec.get("youtube"))[0], foreground=conectado(sec.get("youtube"))[1])
        estado_tt = ttk.Label(c, style="Suave.TLabel", wraplength=px(330))
        estado_tt.configure(text=conectado(tt.get("refresh_token"))[0], foreground=conectado(tt.get("refresh_token"))[1])

        def conectar(funcion, etiqueta):
            etiqueta.configure(text="Inicia sesión en el navegador que se ha abierto…", foreground=AMARILLO)

            def trabajo():
                try:
                    funcion()
                    texto, color = "✓ Conectado", VERDE
                except Exception as e:
                    texto, color = f"✗ {e}", ROJO
                self.q.put(("llamar", lambda: etiqueta.winfo_exists() and etiqueta.configure(text=texto, foreground=color)))
            threading.Thread(target=trabajo, daemon=True).start()

        def conectar_youtube():
            ruta = filedialog.askopenfilename(parent=v, title="El JSON del cliente OAuth de Google Cloud (App de escritorio)",
                                              filetypes=[("Cliente OAuth", "*.json")])
            if ruta:
                conectar(lambda: au.conectar_youtube(ruta), estado_yt)

        def conectar_tiktok():
            au.guardar_secretos(tiktok={**(au.secretos().get("tiktok") or {}), "client_key": tt_clave.get().strip(),
                                        "client_secret": tt_secreto.get().strip()})
            conectar(au.conectar_tiktok, estado_tt)

        linea(ttk.Checkbutton(c, text="YouTube", variable=var["youtube"]), estado_yt,
              ttk.Button(c, text="Conectar YouTube…", command=conectar_youtube))
        linea(ttk.Checkbutton(c, text="TikTok", variable=var["tiktok"]), estado_tt,
              ttk.Button(c, text="Conectar TikTok…", command=conectar_tiktok))
        claves_tt = ttk.Frame(c)
        claves_tt.columnconfigure((0, 1), weight=1, uniform="tt")
        ttk.Entry(claves_tt, textvariable=tt_clave, font=(L, 10)).grid(row=0, column=0, sticky="ew", padx=(0, px(6)))
        ttk.Entry(claves_tt, textvariable=tt_secreto, show="•", font=(L, 10)).grid(row=0, column=1, sticky="ew")
        linea("   Client key · secret", claves_tt)
        ttk.Label(c, text="En TikTok llegan como borrador: te avisa el móvil y lo publicas con un toque.",
                  style="Suave.TLabel").grid(row=fila[0], column=1, columnspan=2, sticky="w")
        fila[0] += 1
        ttk.Checkbutton(c, text="Avisar a YouTube de que la historia y la voz están hechas con IA",
                        variable=var["sintetico"]).grid(row=fila[0], column=0, columnspan=3, sticky="w", pady=(px(6), 0))
        fila[0] += 1

        n = au.cola()
        textos = {"pendiente": "por aprobar", "aprobada": "aprobada", "lista": "con vídeos", "programada": "publicándose",
                  "error": "con error"}
        partes = [f"{n[k]} {t}{'s' * (k == 'aprobada' and n[k] > 1)}" for k, t in textos.items() if n.get(k)]
        ttk.Label(c, text="En la carpeta:  " + "  ·  ".join(partes) if partes else "Todavía no hay historias en marcha.",
                  style="Suave.TLabel").grid(
            row=fila[0], column=0, columnspan=3, sticky="w", pady=(px(18), px(10)))
        fila[0] += 1

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
                        style="Formato.TCheckbutton").grid(row=fila[0], column=0, columnspan=3, sticky="w")
        fila[0] += 1
        botones = ttk.Frame(c)
        botones.grid(row=fila[0], column=0, columnspan=3, sticky="ew", pady=(px(16), 0))
        ttk.Button(botones, text="▶  Hacer una pasada ahora", command=lambda: guardar() and self.pasada()).pack(side="left")
        ttk.Button(botones, text="Guardar", style="Acento.TButton", command=guardar).pack(side="right")
        ttk.Button(botones, text="Cancelar", command=v.destroy).pack(side="right", padx=(0, px(8)))
        v.update_idletasks()  # centrado sobre la ventana principal
        v.geometry(f"+{self.winfo_rootx() + (self.winfo_width() - v.winfo_reqwidth()) // 2}"
                   f"+{max(self.winfo_rooty() + (self.winfo_height() - v.winfo_reqheight()) // 2, 0)}")

    def pasada(self):
        """Una pasada del piloto ahora mismo, con su detalle en el registro."""
        self.btn_crear.config(state="disabled", text="Piloto en marcha…")
        self.btn_piloto["state"] = "disabled"
        self.estado.configure(foreground=TEXTO)
        self.texto.delete("1.0", "end")
        self.relleno.place_configure(relwidth=0)

        def trabajo():
            ok = "piloto"
            try:
                au.pasada()
            except Exception as e:
                self.q.put(("log", f"\n❌ Error: {e}"))
                ok = False
            self.q.put(("fin", ok))
        threading.Thread(target=trabajo, daemon=True).start()

    # ── mensajes del hilo de trabajo ─────────────────────────────────────
    def bucle(self):
        while not self.q.empty():
            tipo, dato = self.q.get()
            if tipo == "log":
                self.texto.insert("end", dato + "\n", next((t for s, t in MARCAS_LOG if s in dato), ""))
                self.texto.see("end")
                if dato.strip() and self.btn_crear.instate(["disabled"]):
                    self.estado["text"] = dato.strip().splitlines()[0]
            elif tipo == "prog":
                self.relleno.place_configure(relwidth=dato)
            elif tipo == "sonar":
                self.btn_escuchar["state"] = "normal"
                self.estado["text"] = ""
                if dato:
                    winsound.PlaySound(str(dato), winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif tipo == "llamar":
                dato()
            elif tipo == "fin":
                self.btn_crear.config(state="normal", text="Crear vídeos")
                self.btn_piloto["state"] = "normal"
                if dato == "piloto":  # puede haber notas nuevas o con otro estado: se refresca la lista sin borrar el registro
                    actual = self.g.ruta if self.g else None
                    self.rutas = gv.guiones_de(gv.CARPETA_GUIONES)
                    if actual and actual not in self.rutas:
                        self.rutas.insert(0, actual)
                    self.refrescar_nombres()
                    if actual:
                        self.combo_guion.current(self.rutas.index(actual))
                        self.btn_aprobar.grid() if gv.estado_nota(actual) == "pendiente" else self.btn_aprobar.grid_remove()
                    self.relleno.place_configure(relwidth=1.0)
                    self.estado.configure(text="✓ Pasada del piloto terminada: lo que ha hecho está en el registro.", foreground=VERDE)
                elif dato:
                    self.relleno.place_configure(relwidth=1.0)
                    self.estado.configure(text="✓ Vídeos listos. Te abro la carpeta.", foreground=VERDE)
                    self.refrescar_nombres()  # el estado de la nota puede haber cambiado
                    self.abrir_salida()
                else:
                    self.estado.configure(text="No se pudo terminar. Tienes el detalle en el registro.", foreground=ROJO)
        self.after(100, self.bucle)


if __name__ == "__main__":
    App().mainloop()
