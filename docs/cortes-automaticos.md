# Cortes automáticos de los shorts

[← Volver al README](../README.md)

Si la nota no trae *Mapa de cortes* (o es un texto normal), la app parte la historia ella sola en shorts verticales que terminan en cliffhanger.

## Cómo decide

| | |
|---|---|
| **Duración** | Busca shorts de ~2:30 de voz: mínimo 1:01, que es lo que paga TikTok, y máximo 2:50, para que YouTube los trate como Shorts (llegan hasta 3:00). |
| **Dónde corta** | Entre frases, nunca a mitad, y prefiere los puntos de suspense: frases que acaban en «…», «?» o «:», remates cortos («Eso fue mi primer error.»), finales de sección o justo antes de un giro («Pero…», «De repente…», «Hasta que…»). |
| **El final, solo en YouTube** | Los shorts llegan hasta el mejor cliffhanger hacia el 80 % de la historia. El resto solo está en el vídeo largo, y el último short acaba con «El FINAL en YouTube». |
| **Fondos** | Un único tema por short, distinto del anterior. |

## Pistas que ayudan (opcionales)

- Secciones con `#` o líneas tipo «PARTE 2/8 · El giro» o «Capítulo 3»: no se leen en voz alta y la app las tiene en cuenta como buenos sitios para cortar.
- En las notas de `01_Historias` lee desde «## Historia adaptada».
- Arregla solo los textos mal pegados de la web (párrafos convertidos en espacios, «frase.Otra» sin espacio).

## Estimación y voz real

Antes de crear, los cortes se calculan con una estimación de la voz (calibrada: ~0,05 s por letra). Al crear se recalculan con la voz real, así que puede moverse algún corte un par de frases.

## Dónde verlos

- **En la app:** debajo de la historia ves cuánto dura, cuántos shorts salen y qué parte va solo en YouTube. Al crear, el registro muestra cada short con su duración, cómo empieza y en qué frase termina.
- **En la terminal:**

  ```bash
  python guion_a_video.py "historia.txt" --analizar
  ```

## Ajustes

En el bloque `CONFIGURACIÓN` de [`guion_a_video.py`](../guion_a_video.py):

| Ajuste | Por defecto | Para qué sirve |
|---|---|---|
| `CORTE_OBJETIVO` | `150` | Segundos de voz que se buscan por short. |
| `CORTE_MIN` | `61` | Duración mínima de un short. |
| `CORTE_MAX` | `170` | Duración máxima de un short. |
| `FINAL_SOLO_YOUTUBE` | `0.2` | Parte final que no sale en los shorts; con `0`, los shorts cuentan la historia entera. |

`python test_cortes.py` comprueba que todo sigue cortando bien.
