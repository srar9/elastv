# EL CIRO para Hostinger Web Premium y Telegram

El ZIP `el-ciro-hostinger-premium.zip` contiene la aplicación lista para subir: página compilada, reproductor HLS, agenda PHP, API, logo y configuración. No requiere Node.js, una base de datos ni claves del bot en Hostinger. No necesitas dejar esta computadora encendida para que la web funcione después de subirla.

## Reproductor mejorado · versión 1.1

- Un único botón central **Reproducir**; se retiró la superposición de controles nativos y personalizados.
- Pausa, sonido y pantalla completa en una barra dentro del video. Calidad automática y selector cuando la señal publica varias resoluciones.
- Búfer de 30 segundos como objetivo (depende del contenido disponible y la conexión), calidad adaptada al tamaño del reproductor y dos intentos limitados de reconexión. Ante un error, **Reintentar** o **Probar otra señal**.
- Compartir está en una sección plegable debajo de las señales y no forma parte de los controles de reproducción.
- El reproductor solo admite URLs de nuestra API. La política de la página limita conexiones y video a su propio dominio y prohíbe marcos de terceros. No ejecuta el reproductor ni los scripts publicitarios del proveedor. Esto no elimina anuncios que formen parte del video original ni controla extensiones instaladas en el navegador.
- Los archivos JS y CSS incluyen una versión en su URL para evitar que siga apareciendo el reproductor anterior después de subir la actualización.

Para probar en esta computadora: ejecuta **PROBAR-LOCAL.bat** y abre `http://127.0.0.1:8787/`. Deja la ventana del servidor abierta y detenla con Ctrl+C al terminar. El ZIP es un paquete completo actualizado; si ya personalizaste `lib/settings.php`, conserva tu configuración al actualizar.

## Subir a Hostinger

1. En hPanel entra en **Sitios web → Administrar/Panel → Administrador de archivos** del dominio elegido.
2. Abre **public_html**. Si ya tienes otra web, crea una carpeta **futbol** y entra allí para instalar esta plataforma sin reemplazar la anterior. También puedes usar un subdominio o la raíz de un sitio vacío.
3. Sube **el-ciro-hostinger-premium.zip** y utiliza **Extraer**. Si el administrador crea otra carpeta al extraer, mueve su contenido a la carpeta de instalación. `index.php`, `api.php`, `.htaccess`, `assets` y `lib` deben quedar juntos. El ZIP no contiene una carpeta `public_html` adicional.
4. En **Configuración PHP**, utiliza **PHP 8.2 o superior** y comprueba que estén habilitadas **curl** y **mbstring**. Estas opciones se administran en hPanel. No hace falta instalar paquetes con Composer.
5. Abre el sitio con HTTPS; por ejemplo, `https://TU-DOMINIO/futbol/`. La ruta de ejemplo debe reemplazarse por tu dominio real.
6. Abre `https://TU-DOMINIO/futbol/api.php?action=status`: debe mostrar `"ok":true`. Si indica un problema de escritura, revisa el propietario/permisos de la carpeta desde Hostinger; no uses permisos 777.

La aplicación crea su propia clave de reproducción y caché local en `.el-ciro` al utilizarla. Esa carpeta tiene bloqueo de acceso y archivos PHP protegidos. No se incluye en el ZIP. No necesitas configurar un token de Telegram.

Guías oficiales:

- Archivos y extracción: https://www.hostinger.com/support/1869114-how-to-upload-backups-with-file-manager-in-hostinger/
- Extensiones PHP: https://www.hostinger.com/support/4667515-how-to-manage-php-extensions-and-options-in-hostinger/

## Publicar enlaces en @elasdelfutbol

1. Entra en tu web y localiza el partido.
2. Pulsa **Copiar enlace** y pega el enlace en una publicación de **@elasdelfutbol**. También puedes pulsar **Telegram** para abrir el selector oficial de chats/canales y elegir el destino. Tú confirmas el envío en Telegram.
3. Quien abra el enlace llegará directamente al reproductor del partido y elegirá una señal. En el móvil puede ser necesario pulsar **Reproducir** para autorizar el audio.

Cada enlace incluye el identificador y la fecha del encuentro. Los enlaces de días anteriores muestran un aviso y la agenda actual, en lugar de abrir otro evento por error. Las vistas previas de Telegram reciben el título y horario del encuentro mediante etiquetas Open Graph; Telegram puede conservar vistas previas en su caché.

Los enlaces son páginas HTTPS normales: no hace falta registrar una Mini App para publicarlos en el canal. La apertura en el navegador interno o externo depende de la aplicación y las preferencias del visitante. La página se adapta a móvil y utiliza video `playsInline`, HLS nativo cuando está disponible y hls.js como alternativa.

El SDK oficial de Telegram también está preparado: si más adelante configuras esta URL como Mini App de un bot en BotFather, la página utiliza expansión, colores y botón de volver cuando existe una sesión real del SDK. Este paquete no registra esa Mini App ni cambia tu bot automáticamente. No se utiliza `initData` como autenticación y no se comparte en los enlaces.

## Agenda y señales

La agenda se consulta al abrir la página y cada 90 segundos mientras está visible. Los horarios son de **Venezuela**. El servidor almacena una caché breve y solo permite reutilizar datos del día actual si el proveedor falla. No hay publicaciones automáticas en tu canal.

Las señales son externas. Una prueba local de ESPN entregó manifiesto y fragmentos de video válidos y permitió decodificar 150 cuadros. Eso no verifica la conexión desde el servidor de Hostinger ni desde una aplicación Telegram real: esas dos pruebas deben hacerse después de subirlo. Los proveedores pueden rechazar el servidor, retirar señales o cambiar su formato. Los recursos y concurrencia disponibles dependen del plan de hosting.

La plataforma no añade publicidad ni carga reproductores externos con ventanas emergentes. Los anuncios que estén dentro del video original seguirán apareciendo. No evita reclamaciones de derechos ni garantiza disponibilidad.

Para añadir una señal propia/autorizada, edita `lib/settings.php`, en `custom_channels`, siguiendo el ejemplo comentado. Solo se aceptan fuentes configuradas en el servidor; la API no permite convertir una URL arbitraria enviada por el navegador en un proxy abierto. No desactives la verificación TLS ni las validaciones de destinos.

## Código y pruebas

Los archivos `src/` y `build.mjs` son para desarrollo local. Ya están compilados dentro del ZIP y no se suben a Hostinger. Para recompilar: Node.js moderno, `npm install`, `npm run build`. Pruebas: `php tests/core.php` y `npm test`.

Comprobaciones realizadas: 27 verificaciones PHP (fechas, agenda completa, firmas, expiración, destinos y reescritura HLS), 6 pruebas de enlaces/Telegram y reproducción, sintaxis PHP, compilación del cliente, respuestas HTTP, metadatos del partido y prueba local de video. La actualización verificó también la política de conexiones, el bloqueo de marcos externos y los archivos con versión. No fue posible realizar la inspección visual automatizada por indisponibilidad del navegador de pruebas; la interacción y fluidez en Telegram móvil aún deben comprobarse allí.

La versión anterior de Sites continúa publicada y no cambia al subir este ZIP. Comparte desde tu dominio de Hostinger una vez que hayas verificado su funcionamiento.
