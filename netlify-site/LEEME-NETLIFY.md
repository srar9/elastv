# El Ciro en Netlify

Esta versión funciona con archivos estáticos, Netlify Functions (Node.js) y Netlify Blobs. No utiliza Flask, SQLite, un bot ni un servidor de Railway. El código anterior permanece separado.

## Crear el proyecto

1. En Netlify, elige **Add new project → Import an existing project → GitHub**, selecciona `srar9/elastv` y la rama **`codex/netlify-website`**. Esta rama contiene la versión para Netlify.
2. La configuración de `netlify.toml`, en la raíz del repositorio, establece:
   - Base directory: `netlify-site`
   - Build command: `npm run build`
   - Publish directory: `netlify-site/dist` desde la raíz (`dist` dentro de la base).
   - Functions: `netlify-site/functions` desde la raíz.
   - Node.js: 22.
3. Antes de desplegar, añade en **Project configuration → Environment variables**, con alcance **Functions**:
   - `HLS_PROXY_SECRET`: un valor aleatorio de al menos 32 caracteres. Firma los permisos de reproducción. Debe mantenerse estable entre despliegues.
   - `ADMIN_PASSWORD`: una contraseña privada de al menos 16 caracteres para `/estadisticas`. No debe compartirse con visitantes.
   Puedes generar cada valor en tu equipo con `node -p "require('node:crypto').randomBytes(32).toString('hex')"`. No subas estas claves al repositorio.
4. Publica el proyecto. Netlify entrega el dominio `nombre.netlify.app`; después puedes añadir un dominio propio.

No sirve arrastrar solamente `dist` a Netlify Drop: faltarán las funciones. Usa la importación del repositorio o Netlify CLI con funciones.

## Qué incluye

- Agenda ordenada por hora y búsqueda por equipo, competición o canal.
- Cada partido muestra todas sus señales publicadas antes de cargar el video.
- Cada señal se identifica por su URL completa. Opciones con el mismo nombre o parámetro `stream` pueden apuntar a distintos proveedores.
- Cambio manual de canal, reintento, controles de video y pantalla completa.
- Directorio de las señales de la agenda del día y enlace a `@elasdelfutbol`.
- Estadísticas privadas con sesiones del día y espectadores activos estimados (últimos 75 segundos), guardadas en Netlify Blobs. Un navegador puede generar varias sesiones y no representa necesariamente una persona.

Como el acceso ya es desde la web, las estadísticas usan una contraseña de administración; el ID de Telegram por sí solo no autentica al propietario de un navegador. El enlace de administración no aparece en el menú público.

La página no añade anuncios ni abre iframes publicitarios. Los anuncios incrustados en la señal de origen y su disponibilidad dependen del proveedor. No se garantiza reproducción de una fuente bloqueada, protegida o caída.

## Validación después del primer despliegue

1. `/api/agenda` debe devolver JSON con `events` y `channels`.
2. Abre un partido: no debe reproducirse nada hasta elegir canal. Elige dos opciones del mismo partido y confirma que cambia la señal.
3. Recarga directamente el enlace `/partido/...`: debe conservar la página.
4. `/api/statistics` sin contraseña debe devolver 403. `/estadisticas` requiere tu contraseña y no la guarda en el navegador.
5. Prueba en móvil el botón de reproducción y pantalla completa. Algunos navegadores exigen tocar reproducir para permitir sonido.

## Desarrollo

En `netlify-site`: `npm ci`, `npm test`, `npm run build`. Para la API real, usa Netlify Dev con el proyecto vinculado y sus variables configuradas; las funciones necesitan el contexto de Blobs. Nunca publiques la raíz completa del repositorio: solo `dist` contiene los archivos públicos.

Los segmentos HLS pasan por Functions para conservar las cabeceras requeridas por la fuente. Esto consume transferencia e invocaciones según audiencia y calidad; revisa el consumo en Netlify antes de abrir el sitio a una audiencia grande. Es un reproductor HLS, no un servidor que convierte o retransmite video con FFmpeg.

Documentación: [Functions](https://docs.netlify.com/build/functions/overview/), [límites de respuesta](https://docs.netlify.com/build/functions/api/), [Blobs](https://docs.netlify.com/build/data-and-storage/netlify-blobs/).
