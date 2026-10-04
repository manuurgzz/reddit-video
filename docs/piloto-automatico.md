# Piloto automático · cómo se conecta

Todo se configura en la app, con el botón **Piloto automático…** de abajo a la derecha. Las claves se guardan en `secretos.json`, junto a la app. Ese archivo no se sube a GitHub.

## 1 · Gemini (escribe las historias)

1. Entra en [aistudio.google.com/apikey](https://aistudio.google.com/apikey) con tu cuenta de Google y pulsa **Create API key**.
2. Cópiala y pégala en **Clave de Gemini**.

- **Modelo:** `gemini-3.8-flash` es gratuito. `gemini-3.1-pro-preview` escribe mejor, pero necesita activar la facturación en Google AI Studio.
- **Prompt:** Gemini sigue tu nota `00_Sistema/Prompt-historias-propias.md`. Si la cambias en Obsidian, el piloto escribe distinto desde la siguiente historia.

## 2 · YouTube (sube y programa los vídeos)

Esto se hace una sola vez, en [console.cloud.google.com](https://console.cloud.google.com):

1. Crea un proyecto, por ejemplo «Reddit Video».
2. En **APIs y servicios › Biblioteca**, busca **YouTube Data API v3** y pulsa **Habilitar**.
3. En **Google Auth Platform**, que es la pantalla de consentimiento de OAuth:
   - Ponle un nombre a la app y tu correo.
   - En **Público**, elige **Externo**.
   - Después pulsa **Publicar la app** para que quede **En producción**. Si se queda en «Prueba», el permiso caduca a los 7 días.
4. En **Clientes › Crear cliente**, elige **App de escritorio** y descarga el JSON.
5. En la app, pulsa **Conectar YouTube…**, elige ese JSON y entra con la cuenta del canal. Google avisará de que la app «no está verificada». Es tu propia app: pulsa **Configuración avanzada › Ir a…** y luego **Permitir**.

> **Importante:** mientras Google no apruebe la revisión de tu proyecto, los vídeos subidos por la API se quedan en **privado** aunque estén programados. Pídela en el [formulario de auditoría de la API de YouTube](https://support.google.com/youtube/contact/yt_api_form): explica que es una herramienta propia que sube vídeos a tu canal. Suele tardar días o semanas. Mientras tanto, puedes publicarlos a mano desde YouTube Studio.

## 3 · TikTok (manda los shorts como borrador)

1. En [developers.tiktok.com](https://developers.tiktok.com), en **Manage apps**, crea una app.
2. Añade los productos **Login Kit** y **Content Posting API**, con el permiso `video.upload`.
3. En **Login Kit**, añade la plataforma **Desktop** con esta Redirect URI, exactamente así:
   `http://127.0.0.1:8723/callback/`
4. Envía la app a revisión. TikTok tiene que aprobar `video.upload` antes de dejar subir vídeos.
5. Copia el **Client key** y el **Client secret** en la app y pulsa **Conectar TikTok…**.

Los shorts llegan a tu bandeja de TikTok como **borrador**: te avisa el móvil, escribes el texto y los publicas con un toque. Publicar sin tocar el móvil exige otra revisión de TikTok (*Direct Post*); el piloto todavía no lo hace.

## 4 · Activarlo

Marca **Piloto activado** y pulsa **Guardar**. Se crea una tarea de Windows que hace una pasada al día a la hora indicada. Si el PC estaba apagado a esa hora, la pasada se hace al encenderlo. Cada pasada:

1. **Escribe.** Si hay menos historias en marcha de las que has puesto, Gemini escribe una nueva. Aparece en la lista de la app como `pendiente`.
2. **Espera tu visto bueno.** La lees (botón **Abrir nota**) y pulsas **✓ Aprobar para el piloto**. Si desmarcas «Revisar yo cada historia», nace ya aprobada.
3. **Crea los vídeos** de la historia aprobada más antigua: el de YouTube y los shorts.
4. **Publica un short en cada hora** de «Publicar a las». El vídeo largo sale con el primer short y su enlace va en la descripción de los demás.

Al terminar, Windows te avisa con una notificación. El detalle queda en `.cache/piloto.log`. Si algo falla, la nota pasa a `estado: error` y el motivo queda en el campo `error:`. Para reintentarla, vuelve a ponerla en `aprobada`.

Con **▶ Hacer una pasada ahora** la pruebas sin esperar al día siguiente. Solo se publica una vez al día, así que repetir la pasada no duplica las subidas.

### Estados de una nota

`pendiente` → `aprobada` → `lista` (vídeos creados) → `programada` (publicándose) → `publicada`

Se ven en la lista de la app, en el frontmatter de la nota y en `00_Sistema/Registro.md`. El piloto también puede publicar tus historias hechas a mano: basta con aprobarlas.
