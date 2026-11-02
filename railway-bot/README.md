# EL CIRO · Bot privado en Railway

Este proyecto publica únicamente el bot de transmisiones que ya utilizas, sus comandos de agenda y FFmpeg. No incluye la plataforma web, el bot de Mini App, canales nuevos automáticos ni cambios en la forma de elegir las transmisiones. Los archivos originales de la computadora se conservan aparte.

## 1. Crear un repositorio privado en GitHub

1. Entra en https://github.com/new con tu cuenta.
2. Nombre sugerido: **el-ciro-bot**. Selecciona **Private** y pulsa **Create repository**.
3. En el repositorio vacío, pulsa **uploading an existing file** (o **Add file → Upload files**).
4. Extrae el ZIP preparado. Abre la carpeta extraída y arrastra su contenido, incluyendo la carpeta `assets`, al cargador de GitHub. Sube los archivos, no el ZIP ni toda tu carpeta original `telegram`.
5. Comprueba que **Dockerfile**, **entrypoint.py**, **railway.json** y **requirements.txt** aparecen en la raíz del repositorio, no dentro de otra carpeta.
6. Pulsa **Commit changes**. El paquete está limpio de tokens y claves de transmisión. No añadas archivos `.env`, configuraciones de tu computadora, sesiones, videos, registros ni bases de datos.

## 2. Crear el servicio en Railway

1. En la pantalla **New project**, selecciona **GitHub Repository**.
2. Autoriza la integración oficial de Railway con acceso al repositorio privado **el-ciro-bot** y selecciónalo.
3. Railway detectará el Dockerfile, que instala Python, las dependencias y FFmpeg. Si hay un Start Command personalizado de otra prueba, quítalo para que se utilice el comando del Dockerfile.
4. Añade un **Volume** al servicio y establece su ruta de montaje en **/data**. El proyecto exige ese montaje para conservar la configuración. El primer intento puede quedar pendiente o fallar hasta que el volumen exista; vuelve a desplegar cuando esté añadido.
5. Mantén **1 réplica** y desactivado **Serverless / App Sleeping**. El archivo `railway.json` ya declara ambos valores. Deja la política de reinicio y el healthcheck `/healthz` incluidos.

No necesitas publicar un dominio ni abrir la plataforma web: el bot utiliza conexiones salientes a Telegram. El pequeño servidor HTTP incluido sirve únicamente para comprobar el estado del proceso; no ofrece un panel ni comandos públicos.

## 3. Variables privadas

En el servicio, abre **Variables** y añade:

| Variable | Valor |
| --- | --- |
| `BOT_ENABLED` | `false` durante la preparación; `true` cuando estés listo para activarlo |
| `TELEGRAM_BOT_TOKEN` | El token del mismo bot de transmisiones que utilizas actualmente |
| `ADMIN_USER_IDS` | Tu identificador numérico de usuario de Telegram. Si hay varios, separados por comas |
| `BOT_CONFIG_PATH` | `/data/stream_config.json` |

El bot actual tiene `/id` para consultar tu identificador; también puedes obtenerlo de su configuración local. Debes poner el **ID de usuario**, no el ID del canal ni su nombre `@...`. No compartas el token en mensajes, capturas ni en GitHub: pégalo directamente en **Variables**.

Opcional: `INITIAL_STREAM_KEY` permite suministrar una clave inicial. También puedes utilizar `/key` en el chat privado del bot. La configuración que guardes después queda en el volumen; cambiar la variable inicial no sustituye una configuración ya guardada.

El logo EL CIRO va incluido. El perfil predeterminado prioriza la fluidez: sin marco, movimiento ni cambio de tono; codifica a 720p/30 FPS con `ultrafast`. El lector HLS nativo conserva listas maestras y segmentos de inicialización, reutiliza conexiones HTTP y lee al ritmo del video. Arranca tres segmentos detrás del borde del directo para absorber variaciones de red. Puedes cambiar la presentación con las variables `STREAM_*` de `.env.example`; las variables de Railway tienen prioridad sobre los valores del contenedor. Si ya configuraste efectos en Variables, usa `STREAM_FRAME_PERCENT=0`, `STREAM_LOGO_MOTION=0`, `STREAM_PITCH_PERCENT=100`, `STREAM_ROTATE_DEGREES=0`, `STREAM_COLOR_CORRECTION=0` y `STREAM_HIDE_LOGOS=0` para aplicar el perfil ligero. Reinicia el servicio y la emisión después de actualizar el código.

## 4. Activar y comprobar

1. Con `BOT_ENABLED=false`, el servicio estará en espera y **no consultará Telegram**. Los logs indicarán `Modo: standby`. Esto permite preparar el despliegue sin interferir con otra copia del bot.
2. Detén el bot y FFmpeg que estén ejecutándose en tu computadora antes de activar el servicio. No ejecutes dos copias del mismo bot ni dos emisiones con la misma clave a la vez. Si había un directo activo, planifica la interrupción: este paquete no traslada los procesos que ya estaban ejecutándose.
3. Cambia `BOT_ENABLED` a **true** y aplica los cambios para volver a desplegar.
4. En **Logs**, comprueba `Modo: active` e `Iniciando polling de Telegram...`.
5. En el chat privado del bot, prueba `/start`, `/partidos`, `/canales` y `/status`. Configura la clave y prueba una transmisión antes de apagar la computadora definitivamente.
6. Los permisos del bot y los ajustes de los canales en Telegram siguen siendo necesarios. Este despliegue no crea canales ni inicia directos de Telegram automáticamente.

Si ves **409**, suele haber otra copia del mismo bot consultando Telegram. Detén la otra instancia; no añadas réplicas. Si ves **401/404**, revisa el token. Si el proveedor rechaza una señal, Railway no garantiza que esa señal funcione ni evita restricciones de Telegram.

Al volver temporalmente a la computadora, primero cambia `BOT_ENABLED=false` en Railway y espera a que termine ese despliegue; después inicia la copia local.

## Consumo y límites

La captura de tu cuenta muestra una prueba de **30 días o USD 5**. No equivale a alojamiento gratuito indefinido: FFmpeg y el tráfico de video consumen recursos. Configura límites de gasto y revisa el plan. Las pruebas limitadas pueden restringir conexiones salientes; comprueba la verificación de tu cuenta si Telegram o la fuente no conectan.

## Validación y referencias

Se incluyen pruebas ejecutables con `python -m unittest test_deploy.py`. Validan configuración, acceso privado, ausencia de claves incrustadas, guardado de configuración y sintaxis compatible con Python 3.11. La construcción del contenedor y la conectividad real deben verificarse en Railway; no hay Docker instalado en esta computadora.

- GitHub y despliegues: https://docs.railway.com/quick-start
- Volúmenes: https://docs.railway.com/volumes
- Variables: https://docs.railway.com/variables
- Precios: https://docs.railway.com/pricing
