"""Ventana para crear los vídeos sin terminal. Doble clic en crear_video.bat (o en este archivo)."""
import json
import os
import queue
import threading
import tkinter as tk
import winsound
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import guion_a_video as gv

try:  # texto nítido en pantallas con escalado
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

NARANJA = "#FF4500"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Reddit Video · creador de vídeos")
        self.geometry("900x780")
        self.minsize(780, 640)
        self.q = queue.Queue()
        gv.log = lambda m="": self.q.put(("log", str(m)))
        gv.al_progresar = lambda f: self.q.put(("prog", f))
        gv.preparar_carpetas()
        self.g = None
        self.rutas = []

        st = ttk.Style(self)
        st.configure("TLabelframe.Label", font=("Segoe UI", 11, "bold"))
        st.configure("Info.TLabel", foreground="#555")

        raiz = ttk.Frame(self, padding=14)
        raiz.pack(fill="both", expand=True)
        raiz.columnconfigure(0, weight=1)

        # 1 · Guion
        f = ttk.LabelFrame(raiz, text="1 · Guion", padding=10)
        f.grid(row=0, column=0, sticky="ew")
        f.columnconfigure(0, weight=1)
        self.combo_guion = ttk.Combobox(f, state="readonly", font=("Segoe UI", 10))
        self.combo_guion.grid(row=0, column=0, sticky="ew")
        self.combo_guion.bind("<<ComboboxSelected>>", lambda e: self.cargar(self.rutas[self.combo_guion.current()]))
        ttk.Button(f, text="Carpeta de guiones…", command=self.elegir_carpeta).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(f, text="Otro archivo…", command=self.elegir_archivo).grid(row=0, column=2, padx=(8, 0))
        self.info = ttk.Label(f, style="Info.TLabel", text="")
        self.info.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

        # 2 · Post de Reddit
        f = ttk.LabelFrame(raiz, text="2 · Post de Reddit (la tarjeta del principio)", padding=10)
        f.grid(row=1, column=0, sticky="ew", pady=10)
        f.columnconfigure(1, weight=1)
        f.columnconfigure(3, weight=2)
        self.subreddit, self.usuario, self.titulo = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Label(f, text="Subreddit").grid(row=0, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.subreddit).grid(row=0, column=1, sticky="ew", padx=(6, 14))
        ttk.Label(f, text="Usuario").grid(row=0, column=2, sticky="w")
        u = ttk.Frame(f)
        u.grid(row=0, column=3, sticky="ew", padx=(6, 0))
        u.columnconfigure(0, weight=1)
        ttk.Entry(u, textvariable=self.usuario).grid(row=0, column=0, sticky="ew")
        ttk.Button(u, text="🎲", width=3, command=lambda: self.usuario.set(gv.usuario_al_azar())).grid(row=0, column=1, padx=(4, 0))
        ttk.Label(f, text="Título").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(f, textvariable=self.titulo).grid(row=1, column=1, columnspan=3, sticky="ew", padx=(6, 0), pady=(8, 0))

        # 3 · Voz
        f = ttk.LabelFrame(raiz, text="3 · Voz (se elige al azar en cada proyecto nuevo)", padding=10)
        f.grid(row=2, column=0, sticky="ew")
        f.columnconfigure(0, weight=1)
        self.combo_voz = ttk.Combobox(f, state="readonly", font=("Segoe UI", 10))
        self.combo_voz.grid(row=0, column=0, sticky="ew")
        self.combo_voz.bind("<<ComboboxSelected>>", lambda e: self.guardar())
        ttk.Button(f, text="🎲 Otra al azar", command=self.voz_azar).grid(row=0, column=1, padx=(8, 0))
        self.btn_escuchar = ttk.Button(f, text="▶ Escuchar", command=self.escuchar)
        self.btn_escuchar.grid(row=0, column=2, padx=(8, 0))

        # 4 · Qué crear
        f = ttk.LabelFrame(raiz, text="4 · Qué crear", padding=10)
        f.grid(row=3, column=0, sticky="ew", pady=10)
        self.op = {k: tk.BooleanVar(value=v) for k, v in
                   [("youtube", True), ("shorts", True), ("musica", True), ("rapido", False), ("gpu", False)]}
        for i, (k, txt) in enumerate([("youtube", "Vídeo largo para YouTube (16:9)"),
                                      ("shorts", "Shorts / TikTok / Reels (9:16)"),
                                      ("musica", "Música de fondo"),
                                      ("rapido", "Prueba rápida (media calidad)"),
                                      ("gpu", "Usar gráfica NVIDIA")]):
            ttk.Checkbutton(f, text=txt, variable=self.op[k]).grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 24), pady=2)

        # Botón principal + progreso
        self.btn_crear = tk.Button(raiz, text="🎬  CREAR VÍDEOS", command=self.crear, bg=NARANJA, fg="white",
                                   activebackground="#d93a00", activeforeground="white", relief="flat",
                                   font=("Segoe UI", 13, "bold"), cursor="hand2", pady=8)
        self.btn_crear.grid(row=4, column=0, sticky="ew")
        self.barra = ttk.Progressbar(raiz, maximum=1.0)
        self.barra.grid(row=5, column=0, sticky="ew", pady=(10, 2))
        self.estado = ttk.Label(raiz, text="Elige un guion y pulsa «Crear vídeos».", style="Info.TLabel")
        self.estado.grid(row=6, column=0, sticky="w")

        # Detalles
        self.texto = ScrolledText(raiz, height=10, font=("Consolas", 9), wrap="word", relief="flat", background="#f6f6f6")
        self.texto.grid(row=7, column=0, sticky="nsew", pady=(8, 8))
        raiz.rowconfigure(7, weight=1)

        f = ttk.Frame(raiz)
        f.grid(row=8, column=0, sticky="ew")
        ttk.Button(f, text="📂 Vídeos creados", command=self.abrir_salida).pack(side="left")
        ttk.Button(f, text="📂 Fondos", command=lambda: os.startfile(gv.CARPETA_FONDOS)).pack(side="left", padx=6)
        ttk.Button(f, text="📂 Música", command=lambda: os.startfile(gv.CARPETA_MUSICA)).pack(side="left")

        self.voces = list(gv.VOCES)
        self.combo_voz["values"] = [f"{gv.VOCES[v]}  —  {v}" for v in self.voces]
        self.cargar_lista()
        self.after(100, self.bucle)

    # ── guion y proyecto ─────────────────────────────────────────────────
    def cargar_lista(self, elegida=None):
        d = gv.CARPETA_GUIONES
        self.rutas = sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True) if d.is_dir() else []
        if elegida and elegida not in self.rutas:
            self.rutas.insert(0, elegida)
        self.combo_guion["values"] = [p.name for p in self.rutas]
        if self.rutas:
            self.combo_guion.current(self.rutas.index(elegida) if elegida else 0)
            self.cargar(self.rutas[self.combo_guion.current()])
        else:
            self.info["text"] = f"No hay guiones en {d}. Usa «Otro archivo…»."

    def elegir_carpeta(self):
        d = filedialog.askdirectory(title="Carpeta donde guardas los guiones (.md)", initialdir=gv.CARPETA_GUIONES)
        if d:
            gv.CARPETA_GUIONES = Path(d)
            gv.AJUSTES.write_text(json.dumps({"carpeta_guiones": d}, ensure_ascii=False), encoding="utf-8")
            self.cargar_lista()

    def elegir_archivo(self):
        r = filedialog.askopenfilename(title="Elige un guion", filetypes=[("Guion", "*.md")],
                                       initialdir=gv.CARPETA_GUIONES if gv.CARPETA_GUIONES.is_dir() else None)
        if r:
            self.cargar_lista(Path(r))

    def cargar(self, ruta):
        self.g = gv.parsear_guion(ruta)
        self.texto.delete("1.0", "end")
        if not self.g.escenas:
            self.info["text"] = "⚠️ No encuentro escenas ('### ESCENA N · ...' con '**Narración:**')."
            return
        p = gv.datos_proyecto(self.g)
        self.subreddit.set(p["subreddit"])
        self.usuario.set(p["usuario"])
        self.titulo.set(p["titulo"])
        if p["voz"] not in self.voces:
            self.voces.append(p["voz"])
            self.combo_voz["values"] = [*self.combo_voz["values"], p["voz"]]
        self.combo_voz.current(self.voces.index(p["voz"]))
        sin_clips = sorted({e.etiqueta for e in self.g.escenas if e.etiqueta and not gv.clips_de(e.etiqueta)})
        self.info["text"] = (f"{len(self.g.escenas)} escenas · {len(self.g.cortes)} shorts"
                             + (f"   ⚠️ Carpetas de fondos vacías: {', '.join(sin_clips)} (se usarán otros clips)" if sin_clips else ""))
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
        self.guardar()

    def escuchar(self):
        if not self.g:
            return
        voz = self.voces[self.combo_voz.current()]
        frase = self.g.escenas[0].lineas[0].texto_tts
        self.btn_escuchar["state"] = "disabled"
        self.estado["text"] = "Generando muestra de voz…"

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
            return messagebox.showwarning("Falta el guion", "Elige un guion válido primero.")
        yt, sh = self.op["youtube"].get(), self.op["shorts"].get()
        if not (yt or sh):
            return messagebox.showwarning("Nada que crear", "Marca YouTube, Shorts o los dos.")
        self.guardar()
        args = [str(self.g.ruta), "--solo", "todo" if yt and sh else ("youtube" if yt else "cortes")]
        args += ["--sin-musica"] * (not self.op["musica"].get())
        args += ["--rapido"] * self.op["rapido"].get() + ["--gpu"] * self.op["gpu"].get()
        self.btn_crear.config(state="disabled", text="Creando…", bg="#999")
        self.texto.delete("1.0", "end")
        self.barra["value"] = 0

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

    # ── mensajes del hilo de trabajo ─────────────────────────────────────
    def bucle(self):
        while not self.q.empty():
            tipo, dato = self.q.get()
            if tipo == "log":
                self.texto.insert("end", dato + "\n")
                self.texto.see("end")
                if dato.strip() and self.btn_crear["state"] == "disabled":
                    self.estado["text"] = dato.strip().splitlines()[0]
            elif tipo == "prog":
                self.barra["value"] = dato
            elif tipo == "sonar":
                self.btn_escuchar["state"] = "normal"
                self.estado["text"] = ""
                if dato:
                    winsound.PlaySound(str(dato), winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif tipo == "fin":
                self.btn_crear.config(state="normal", text="🎬  CREAR VÍDEOS", bg=NARANJA)
                if dato:
                    self.barra["value"] = 1.0
                    self.estado["text"] = "✅ Vídeos listos."
                    self.abrir_salida()
                else:
                    self.estado["text"] = "❌ No se pudo terminar. Mira el detalle de abajo."
        self.after(100, self.bucle)


if __name__ == "__main__":
    App().mainloop()
