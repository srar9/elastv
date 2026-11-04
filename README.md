# Transmisión a Telegram: estabilidad y diagnóstico

Bot multicanal, lanzador manual para PC y aplicación web. El motor comparte un perfil H.264/AAC de 720p a 30 FPS, con fotogramas clave cada dos segundos, límites de bitrate y corrección de audio. Requiere Python 3.11+ y FFmpeg 6.1+ con libx264 y la opción HLS `seg_max_retry`. Los Dockerfile usan Debian Trixie para disponer de esta opción.

Las fuentes HLS se leen con el demultiplexor nativo de FFmpeg: conserva las listas maestras, los segmentos de inicialización, el cifrado HLS compatible y las discontinuidades. Usa conexiones HTTP persistentes, descarga anticipada y lectura al ritmo del video para suavizar la entrega a Telegram. Arranca tres segmentos detrás del borde del directo para absorber variaciones de red; ese margen añade retraso según la duración de los segmentos. Se eliminó el descargador por stdin que descartaba segmentos tras un fallo y no interpretaba las etiquetas HLS.

El perfil normal desactiva rotación, corrección cromática y máscaras, usa el preset `ultrafast` y limita los hilos de codificación y filtros para reducir la carga al emitir varias pantallas. Los efectos siguen disponibles mediante configuración explícita. Los cambios se aplican al reiniciar el proceso del bot y volver a iniciar la emisión; no modifican un FFmpeg que ya está ejecutándose. La fluidez final también depende del origen, los recursos del servidor, la subida y el reproductor de Telegram.

## Si Telegram bloqueó el streaming

Un aviso por una reclamación de derechos de autor indica una restricción de la plataforma. **Este programa no elimina ni evita ese bloqueo.** La recuperación técnica solo sirve para fallos de red, fuentes caídas y procesos bloqueados. Si recibiste un aviso de Canal+ u otro titular, sigue el procedimiento del aviso y aporta tu autorización cuando corresponda. No hay una opción que garantice transmisiones sin cierres.

## Iniciar

### Bot público: @Elcirotv_bot

`public_bot.py` atiende al público con `PUBLIC_BOT_TOKEN` (o `ELCIRO_BOT_TOKEN`).
El arranque mantiene el bot de transmisiones separado y ejecuta este bot público para
el segundo token. No inicia FFmpeg ni permite cambiar claves o detener emisiones.
`/start` envía un solo mensaje con el menú principal, sin consultar ni enviar la agenda.
Elimina el antiguo teclado permanente e incorpora botones de Partidos, Canales y Buscar
al mismo mensaje. Cada listado muestra cinco resultados por página; Anterior, Siguiente,
Menú y Actualizar editan ese mensaje, sin enviar nuevas páginas al chat. Las búsquedas
combinan partidos y canales en un único listado. Las estadísticas del dueño también
están paginadas. Los listados conservan una copia estable durante 30 minutos, limitada
a 256 vistas en memoria; al caducar o reiniciar el proceso, muestran el menú para
actualizarlos en el mismo mensaje. Los botones de paginación se vinculan al chat y al
usuario que abrió la lista. El menú nativo de Telegram abre comandos.
Cada partido tiene un único botón que abre directamente su video en
`/ver/<canal>?mode=watch`: sin cabecera, agenda ni navegación del sitio. Las señales
alternativas permanecen en el selector del reproductor, conservando este modo, y
«Volver al bot» cierra la Mini App. Los eventos sin señal permanecen en el listado
como pendientes, sin prometer reproducción. Los navegadores pueden requerir tocar
reproducir o activar el sonido después de abrir el video.
`/partidos` muestra todos los eventos de las dos agendas compartidas, incluidos otros
deportes y eventos sin señal. `/buscar` o un nombre escrito directamente busca equipos,
torneos y canales. El botón de cada partido abre su video en la Mini App.
Configura `WEB_APP_BASE_URL` con la URL HTTPS pública; en Railway se utiliza el dominio
público del servicio si no se proporciona esa variable. Los botones Web App funcionan
en chats privados; en grupos se ofrecen enlaces web.

Solo la cuenta `6467102546`, en su chat privado, recibe la opción `/estadisticas` y el
botón del panel. El API del panel valida la firma HMAC de `initData` de Telegram y su
antigüedad, además del ID. Los IDs enviados como parámetros no autorizan el acceso.
El historial distingue usuarios e interacciones del bot, entradas a la Mini App,
entradas y visitantes por partido, y espectadores con video avanzando durante los
últimos 45 segundos. Es una estimación por navegador, no una prueba de atención humana.
Pausas, errores y cierres dejan de renovar la presencia; varios reproductores del mismo
navegador cuentan como un visitante por partido. Las entradas se registran por apertura
del reproductor y no por cada heartbeat.

Las estadísticas se guardan en SQLite, compartido entre el bot y los procesos web.
Para conservarlas entre despliegues monta un volumen y configura, por ejemplo,
`AUDIENCE_DB_PATH=/data/audience.db`. Sin volumen el historial puede perderse al
reemplazar el contenedor. Ejecuta una sola instancia del servicio por token.

El reproductor nativo usa Safari HLS o Hls.js, sin filtros, marca añadida, Clappr,
P2P, anuncios propios ni HTML ejecutable de terceros. El proxy conserva Referer,
listas anidadas, claves HLS, mapas fMP4 y solicitudes Range; sus enlaces secundarios
están firmados. La reproducción intenta reconectar con espera progresiva. No elimina
anuncios incluidos en el video de origen ni garantiza disponibilidad o fluidez cuando
la señal o la red falla. Las alternativas corresponden a las señales de cada evento.

Pruebas del bot público: `python -m unittest discover -s tests -p public_checks.py -v`.

En PC:

- `iniciar_stream.bat`: lanzador manual con monitor de salida y recuperación.
- `ejecutar_bot_en_pc.bat`: bot local con perfil de codificación compartido.
- `python bot_stream_multicanal.py`: bot multicanal con supervisión por pantalla.

En Railway/VPS, el contenedor instala FFmpeg y ejecuta `start.sh`, que inicia los dos bots y la web. Configura `TELEGRAM_BOT_TOKEN` para el bot multicanal y `ADMIN_USER_IDS` con los administradores adicionales separados por comas. Usa una única instancia del bot por token y evita ejecutar el bot de PC y el de nube simultáneamente con la misma clave de transmisión.

Usa la URL de servidor y la clave que Telegram muestre para tu sala. El bot acepta una URL RTMP/RTMPS completa como destino; si solo recibe una clave, usa su servidor predeterminado. Las credenciales guardadas en los archivos de configuración locales no deben publicarse.

## Bot multicanal

- `/partidos`, `/agenda` o `/hoy`: agenda completa publicada para el día de Venezuela, incluidos eventos sin canal anunciado.
- `/canales`, `/deportes` o `/menu`: directorio del proveedor, señales de la agenda y otros canales configurados, identificados por grupo.
- `/canales ESPN` o `/espn`: filtrar el directorio.
- `/buscar EQUIPO_O_LIGA`: buscar todos los eventos y canales coincidentes, sin truncar a seis resultados.
- `/stream <URL_O_CANAL> <CLAVE_O_URL_RTMPS>`: iniciar o sustituir una señal.
- `/status` o `/logs`: consultar estado, fotogramas, velocidad del codificador, reintentos y último incidente.
- `/stop <NUMERO>`: detener una pantalla e impedir que el supervisor la reactive.
- `/stopall`: detener todas las pantallas.
- `/key <CLAVE>`: actualizar el destino predeterminado.
- `/ayuda`: consultar los comandos disponibles.

El menú nativo de comandos de Telegram se actualiza al iniciar el bot. Se admiten mayúsculas, barras repetidas y menciones al propio bot como `/partidos@Elciro_bot`. Los mensajes largos se dividen automáticamente. Los listados no incluyen la clave de emisión: `/stream CANAL` usa la clave guardada con `/key`.

### Agenda compartida

El bot multicanal, la Mini App y la web usan `agenda_service.py`. La fuente pública actual es `https://api.wqxag.com/diaries.json`, identificada en la configuración de la agenda de la web indicada por el usuario; puede sustituirse con `AGENDA_URL`. Los horarios de ese proveedor están en Lima (UTC−5) y se convierten a Venezuela (UTC−4), filtrando la fecha después de la conversión y ordenando por hora. Se conservan eventos sin canales, señales desconocidas y opciones alternativas publicadas.

La agenda se conserva en memoria durante 90 segundos. Ante un fallo temporal se puede mostrar una copia del mismo día de hasta 30 minutos de antigüedad, con un aviso; nunca se usa la de ayer como agenda de hoy. Una agenda vacía y una fuente caída producen mensajes diferentes. La lista contiene todos los eventos que publique el proveedor, no una garantía de cobertura de todos los partidos del mundo ni de disponibilidad de cada señal.

El supervisor mide el avance de fotogramas y de tiempo de salida, en vez del tamaño del registro. Un FFmpeg que escribe errores sin producir video no se considera saludable. La detección de arranque tiene un margen de 60 segundos; una salida ya iniciada se considera bloqueada tras 40 segundos sin avance. La comprobación se realiza cada tres segundos. El estado «video enviándose» describe la salida de FFmpeg: no confirma lo que ven los espectadores en Telegram.

El bot multicanal y la web comparten los 20 canales identificados en el directorio `rojadirectatvmas.net` indicado por el usuario. También consultan los enlaces de las señales de la agenda actual. Siguen hasta tres niveles de enlaces de reproductor estáticos en dominios conocidos y conservan el Referer inmediato. Si falla, intentan el resolvedor anterior. Esto no modifica el directorio del bot local clásico. No se ejecutan scripts del sitio ni se resuelven desafíos; la integración no garantiza disponibilidad ni permisos de retransmisión.

Si no se obtiene señal, el bot muestra el diagnóstico del origen. Un HTTP 403 de una fuente significa que ese servidor rechazó la solicitud; no demuestra un rechazo de Telegram ni un problema del logo. Una página de inicio HTML no es una URL directa de video: para usar una fuente propia por URL, envía `/stream URL_DIRECTA_M3U8_O_TS CLAVE_DE_TELEGRAM`.

Los reintentos esperan 3, 6, 12, 24, 48 y hasta 60 segundos. El contador de fallos consecutivos se restablece después de dos minutos de funcionamiento; el total queda visible. Cada pantalla se recupera por separado. Los rechazos explícitos de publicación o autenticación pausan los reintentos. Un cierre por derechos de autor puede no aparecer como tal en RTMP: el aviso de Telegram es necesario para identificarlo.

## Ajustes opcionales

### Logo sobre la transmisión

Los tres lanzadores admiten una marca de agua sobre el video original. Usa tu archivo PNG (recomendado con transparencia), JPG o WebP estático. El logo conserva su proporción y su transparencia, se limita a 180 píxeles de alto y no sustituye el audio de origen. Es una personalización visual: no evita reclamaciones ni elimina restricciones de Telegram.

El proyecto incluye `assets/el-ciro.png`, con el texto **EL CIRO**, y lo usa automáticamente en la esquina superior derecha. Reinicia el programa o vuelve a iniciar la transmisión para aplicarlo. Una ruta personalizada en `STREAM_LOGO_PATH` tiene prioridad; configura la variable como una cadena vacía para desactivar la marca.

Ejemplo en PowerShell, antes de iniciar el programa:

```powershell
$env:STREAM_LOGO_PATH = 'C:\ruta\a\tu-logo.png'
$env:STREAM_LOGO_POSITION = 'top-right'
$env:STREAM_LOGO_WIDTH = '160'
$env:STREAM_LOGO_OPACITY = '85'
python bot_stream_multicanal.py
```

En un contenedor, incluye el logo en el despliegue o monta el archivo en un volumen y configura su ruta dentro del contenedor. La ruta de Windows no es válida allí.

`STREAM_LOGO_POSITION` admite `top-left`, `top-right`, `bottom-left` y `bottom-right`. `STREAM_LOGO_WIDTH` acepta entre 40 y 400 píxeles; `STREAM_LOGO_OPACITY`, entre 10 y 100; y `STREAM_LOGO_MARGIN`, entre 0 y 100 píxeles (24 por defecto). Si la posición no es válida, se usa la esquina superior derecha. Sin `STREAM_LOGO_PATH`, se usa el logo incluido; si ese archivo no existe, se transmite sin marca de agua. Una ruta personalizada configurada que no existe produce un error de configuración en lugar de ignorar el logo.

### Marco, movimiento y efectos de audio

En Windows, abre `iniciar_con_estilo.bat` y selecciona el bot multicanal, el lanzador manual o el bot local. El archivo carga `estilo_el_ciro.env`: imagen reducida con marco azul oscuro, logo EL CIRO semitransparente con movimiento suave, tono de audio al 102 %, eco suave y ruido de amplitud baja. Si ya tenías el programa abierto, detén esa instancia antes de iniciar la nueva.

Los efectos son una presentación visual y sonora; no prueban titularidad, no impiden el reconocimiento de contenido y no garantizan evitar reclamaciones o cierres. No dependen de cambiar el hash de un archivo.

Para un contenedor Docker, los valores públicos de `estilo_el_ciro.env` pueden pasarse con `--env-file estilo_el_ciro.env`. En un panel de despliegue, copia esos valores en las variables del servicio. Este archivo no contiene tokens y no sustituye las credenciales del bot.

| Variable | Sin perfil | Uso |
| --- | --- | --- |
| `STREAM_FRAME_PERCENT` | `0` | Margen a cada lado como porcentaje de 1280 × 720; 0–15 |
| `STREAM_FRAME_COLOR` | `102A43` | Color del marco en RRGGBB; admite `#` inicial |
| `STREAM_LOGO_MOTION` | `0` | Movimiento suave, amplitud de 0–20 píxeles, limitado al área visible |
| `STREAM_PITCH_PERCENT` | `100` | Tono del audio, 95–105; compensa la duración para evitar desfase |
| `STREAM_PLAYBACK_PERCENT` | `100` | Velocidad conjunta de audio y video, 95–105; solo archivos locales |
| `STREAM_AUDIO_ECHO` | `0` | `1` activa eco suave de 40 ms; `0` lo desactiva |
| `STREAM_AUDIO_NOISE` | `0` | Ruido de amplitud 0–0,005; valores enteros 0–5 |

Las fuentes de red en directo deben usar `STREAM_PLAYBACK_PERCENT=100`: aumentar la velocidad agotaría el material recibido y produciría cortes. En archivos locales, se acelera también la lectura de entrada. Audio y video mantienen la misma velocidad; cambiar el tono conserva la duración. Eco y ruido modifican el sonido y pueden reducir su claridad. Sin audio de origen, el codificador sigue produciendo video.

Sin cargar el perfil, estos efectos están desactivados y se conserva el logo configurado previamente. Para desactivar un efecto del perfil, usa `0` (marco, movimiento, eco o ruido) o `100` (tono y velocidad). Reinicia la transmisión después de cambiar los valores.

### Codificación y recuperación

| Variable | Predeterminado | Uso |
| --- | --- | --- |
| `STREAM_VIDEO_KBPS` | `1800` | Bitrate de video, entre 300 y 5000 kbps; audio adicional de 128 kbps |
| `STREAM_ENCODER_THREADS` | `2` | Hilos de codificación por pantalla, entre 1 y 16; 0 permite selección automática |
| `STREAM_ENCODER_PRESET` | `ultrafast` | Preset de libx264; los más lentos requieren más CPU |
| `STREAM_STALL_SECONDS` | `40` | Tiempo sin avance antes de recuperar, entre 15 y 300 segundos |
| `STREAM_STARTUP_SECONDS` | `60` | Margen de arranque, entre 20 y 300 segundos |

Reinicia el programa para aplicar cambios. El bot local clásico comparte el perfil, pero la supervisión descrita corresponde al bot multicanal y al lanzador manual. La recuperación no se conserva después de reiniciar el contenedor: inicia de nuevo las transmisiones. La calidad y el número de pantallas dependen de la CPU y de la conexión disponibles.

## Validación local

```powershell
python -m unittest discover -s tests -p '*_checks.py' -v
```

Las pruebas comprueban bloqueos, cancelaciones, errores de arranque, espera entre intentos, ocultación de credenciales y rechazos explícitos. Con FFmpeg y ffprobe instalados también generan señales sintéticas con y sin audio y verifican la salida real de video. No emiten a Telegram ni contactan las fuentes de canales.

La prueba HTTP de HLS sirve una lista maestra desde localhost, exige Referer y simula un HTTP 503 durante la descarga de un segmento. Comprueba recuperación sin huecos de audio/video tanto con MPEG-TS como con fMP4. Para ejecutar solo las pruebas del motor y del codificador: `python -m unittest discover -s tests -p streaming_checks.py -k RuntimeChecks -v` y después el mismo comando con `-k EncoderChecks`.

Opciones de referencia: [FFmpeg](https://ffmpeg.org/ffmpeg.html) y [protocolos de FFmpeg](https://ffmpeg.org/ffmpeg-protocols.html).
