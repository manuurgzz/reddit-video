# Formato del guion y Obsidian

[← Volver al README](../README.md)

No hace falta ningún formato: una historia pegada en la app o un `.txt` valen, y la app [corta los shorts sola](cortes-automaticos.md). Este formato sirve para controlar a mano las escenas, los fondos, las palabras en amarillo y los cortes.

## Guion clásico

Parte de [`guiones/ejemplo_vecino-wifi.md`](../guiones/ejemplo_vecino-wifi.md). Un guion se ve así:

```markdown
---
subreddit: r/AITAH
---

Tarjeta inicial con el título "¿Soy el malo por cortarle el wifi a mi vecino…?"

### ESCENA 1 · Gancho
**Narración:**
Durante un año, mi vecino usó mi wifi gratis.
**me dijo que el tacaño era yo.**

**Fondo / edición:** [SLIME]. Palabras en amarillo: "gratis", "tacaño".

## Mapa de cortes

| Parte | Escenas | Duración aprox. |
|------|---------|-----------------|
| **Parte 1/2** | 1 → 2 | ~0:30 |
| **Parte 2/2** | 3 → 4 | ~0:30 |
```

| En el guion | En el vídeo |
|---|---|
| `### ESCENA N · Título (tiempo)` | Escenas: marcan la temática de fondo y los cortes. |
| Líneas de `**Narración:**` | Voz y subtítulos de 2 a 4 palabras, sincronizados palabra a palabra. |
| `**frase en negrita**` | Subtítulo con zoom. |
| `[JABÓN]`, `[SLIME]`… en `**Fondo / edición:**` | Carpeta de fondos (la primera etiqueta que aparezca). |
| `…en amarillo: "distante", "boca abajo"` | Esas palabras salen en amarillo. |
| «con el título» seguido del título entre comillas | Título del post de Reddit del principio (en YouTube, además, lo lee la voz). En un texto normal, el título es la línea `# Título`. |
| Tabla del *Mapa de cortes* | Shorts 9:16 (solo con las escenas de cada fila). Sin ella, [cortes automáticos](cortes-automaticos.md). |

Para comprobar qué ha entendido la app:

```text
$ python guion_a_video.py guiones/ejemplo_vecino-wifi.md --analizar
📄 ejemplo_vecino-wifi.md
   Título tarjeta: ¿Soy el malo por cortarle el wifi a mi vecino después de un año pagándolo yo?
   Escena  1 · Gancho                             [SLIME] 3 líneas  claves: gratis, tacaño
   Escena  2 · Cómo empezó                        [ARENA] 5 líneas
   Escena  3 · La factura                         [PARKOUR] 6 líneas  claves: la mitad
   Escena  4 · Cierre + pregunta                  [SLIME] 4 líneas
   ✂️  Short 1/2: escenas 1→2
   ✂️  Short 2/2: escenas 3→4
```

## Añadidos automáticos

- «Continúa en mi perfil» al final de los shorts intermedios.
- La pantalla «El FINAL en YouTube (link en bio)», con voz, al final del último short.
- «¡COMENTA!» en los últimos segundos del vídeo de YouTube.

**Todavía no se aplican** las notas de edición finas, como congelar la imagen 0,5 s, sincronizar el aplastamiento de la prensa con una frase o la pantalla partida.

## Obsidian

- **Conectar.** **Conectar Obsidian…** guarda la ruta de la bóveda en `ajustes.json` (solo en tu PC; no se sube a Git). La app lee `02_Clips` (o `03_Guiones`) y las notas de `01_Historias`.
- **Marcar clips hechos.** Al crear vídeos (salvo en *Prueba rápida*), la app marca `- [x]` en el checklist de la nota para los shorts (`Parte N/T`) y el vídeo de YouTube creados, y actualiza `clips_hechos` y `estado` (`en-produccion` o `hecha`).
- **Formato de las notas de clips** (`02_Clips`). Bloques con `[ESCENA N · FONDO: JABON]`, notas como `[Palabras en amarillo: a, b]` o `[Efecto: zoom en "frase"]` y el texto narrado debajo. Cada escena se lee una vez aunque aparezca en varios clips. La tabla de clips (`Parte 1/3 | JABÓN | 1 → 4 | …`) decide qué escenas y qué temática de fondo lleva cada short; las escenas que no estén en ninguna fila van solo en YouTube, y la app lo indica. Sin tabla, los cortes son automáticos.
