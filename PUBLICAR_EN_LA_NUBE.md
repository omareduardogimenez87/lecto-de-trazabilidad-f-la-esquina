# App con Android: publicarla en internet (sin instalar nada en la PC)

Con esta guía la app queda en internet, en **Streamlit Community Cloud** (gratis). Cada persona la abre con un link desde el celular, y los registros se guardan en una **planilla de Google Sheets**.

La **app con Windows** sigue funcionando igual: si la app no encuentra una planilla configurada, guarda en `registros/registros.csv` como siempre. La versión exacta que está instalada en la PC quedó guardada en la rama `app-con-windows`.

**Costo: $0.** Se necesitan tres cuentas que ya tenés o son gratis: GitHub, Google (Gmail) y Streamlit (se entra con GitHub).

Tiempo estimado: 40 minutos, una sola vez.

---

## Parte 1. Crear el "robot" de Google que escribe en la planilla

La app no puede usar tu contraseña de Google. En su lugar se crea una **cuenta de servicio**: un usuario robot con su propio mail, al que le compartís solo la planilla de registros. Si algún día querés cortarle el acceso, dejás de compartirle la planilla.

1. Entrá a <https://console.cloud.google.com/> con tu cuenta de Google. Si te pide aceptar condiciones, aceptá. **No hace falta cargar tarjeta.**
2. Arriba a la izquierda, al lado del logo, tocá el selector de proyecto → **Proyecto nuevo**. Nombre: `lector-trazabilidad`. Tocá **Crear** y esperá unos segundos. Asegurate de que arriba quede elegido ese proyecto.
3. Activá las dos "APIs" que usa la app (son los permisos para hablar con Sheets y Drive):
   - Abrí <https://console.cloud.google.com/apis/library/sheets.googleapis.com> → **Habilitar**.
   - Abrí <https://console.cloud.google.com/apis/library/drive.googleapis.com> → **Habilitar**.
4. Abrí <https://console.cloud.google.com/iam-admin/serviceaccounts> → **Crear cuenta de servicio**.
   - Nombre: `lector-app`. Tocá **Crear y continuar**.
   - Los pasos de "rol" y "acceso de usuarios" dejalos vacíos: **Continuar** → **Listo**.
5. En la lista aparece la cuenta, con un mail parecido a `lector-app@lector-trazabilidad.iam.gserviceaccount.com`. **Copiá ese mail**, lo usás en la Parte 2.
6. Tocá esa cuenta → pestaña **Claves** → **Agregar clave** → **Crear clave nueva** → **JSON** → **Crear**. Se descarga un archivo `.json`.

> ⚠️ Ese archivo `.json` es como una llave. **No lo mandes por WhatsApp ni lo subas a GitHub.** Solo se pega en Streamlit (Parte 3). Después podés borrarlo de Descargas.

> Si Google te dice que la creación de claves está bloqueada por una "política de la organización", es porque la cuenta es de una empresa. Usá una cuenta personal de Gmail.

## Parte 2. Crear la planilla de registros

1. Entrá a <https://sheets.new> (crea una planilla en blanco). Ponele de nombre `Registros trazabilidad - Mitre`.
2. Tocá **Compartir** (arriba a la derecha), pegá el mail del robot (Parte 1, paso 5), elegí **Editor**, destildá "Notificar" y tocá **Compartir**.
3. **Copiá el link** de la planilla desde la barra del navegador (empieza con `https://docs.google.com/spreadsheets/d/...`).

No hace falta escribir nada en la planilla: la app pone los títulos de las columnas la primera vez que guarda. **No cambies el orden de las columnas ni escribas a mano en ella**, para eso están las pestañas Registros y Revisados de la app. Si Claudia o Fernanda quieren mirarla directo, compartísela solo como **Lector**.

## Parte 3. Publicar la app en Streamlit

1. Entrá a <https://share.streamlit.io/> → **Continue with GitHub** y aceptá los permisos. Como el repositorio es privado, cuando te pregunte, autorizá el acceso a repositorios privados.
2. Tocá **Create app** y elegí desplegar desde GitHub (si te pregunta si es pública o privada, no importa: en la Parte 4 la dejamos privada).
   - **Repository**: `omareduardogimenez87/lecto-de-trazabilidad-f-la-esquina`
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **App URL**: elegí un nombre, por ejemplo `trazabilidad-la-esquina`.
3. Tocá **Advanced settings**:
   - **Python version**: `3.12`.
   - En **Secrets** pegá esto, reemplazando las dos partes indicadas:

   ```toml
   planilla_url = "PEGÁ ACÁ EL LINK DE LA PLANILLA"

   cuenta_google = '''
   PEGÁ ACÁ TODO EL CONTENIDO DEL ARCHIVO .json
   '''
   ```

   Para copiar el contenido del `.json`: clic derecho sobre el archivo → **Abrir con** → **Bloc de notas** → `Ctrl + A` (seleccionar todo) → `Ctrl + C` (copiar). Pegalo entre las dos líneas de `'''`.
4. Tocá **Save** y después **Deploy**. La primera vez tarda unos 5 minutos (instala todo, incluido el lector de texto Tesseract, que sale del archivo `packages.txt`).
5. Probala: elegí tu nombre, sacá una foto y guardá. Fijate que aparezca una fila nueva en la planilla de Google.

Si ves un cartel rojo **"No se pudo abrir la planilla de registros"**, casi siempre es una de estas tres cosas: la planilla no está compartida con el mail del robot como Editor, faltó habilitar alguna de las dos APIs (Parte 1, paso 3), o el `.json` no quedó pegado completo. Se corrige en la app → **⋮** → **Settings** → **Secrets**.

## Parte 4. Hacerla privada e invitar a las 6 personas

1. En <https://share.streamlit.io/>, al lado de la app tocá **⋮** → **Settings** → **Sharing**.
2. En "Who can view this app" elegí **Only specific people can view this app**.
3. Escribí el mail de cada persona (Claudia, Fernanda, Silvia, Yessi, Maxi, Omar) y guardá. A cada una le llega una invitación.
4. La primera vez, cada una entra con su cuenta de Google o con el link que le llega al mail. Después queda recordado en ese celular.

> El plan gratis permite una app privada. Para esta app alcanza.

## Parte 5. Ponerla como ícono en el Android

1. Abrí el link de la app en **Chrome** del celular.
2. Tocá **⋮** (arriba a la derecha) → **Agregar a la pantalla principal** (o **Instalar app**) → **Agregar**.
3. Queda un ícono como cualquier otra app.

## Cosas para saber

- **Se duerme si nadie la usa.** Si pasan unas 12 horas sin visitas, el primero que entra ve un botón para despertarla y tarda alrededor de un minuto.
- **Necesita internet** en el celular (WiFi o datos).
- **Los datos** quedan en tu cuenta de Google (la planilla) y la app corre en servidores de Streamlit. Las fotos siguen sin guardarse en ningún lado.
- **Hora**: la app usa siempre la hora de Argentina, aunque el servidor esté en otro país.
- **Actualizar la app**: cuando se cambia algo en la rama `main` de GitHub, Streamlit se actualiza solo en uno o dos minutos. No hay que hacer nada en los celulares.
- **Clave común (opcional)**: si alguna vez preferís una clave en vez de la lista de mails, agregá `clave_acceso = "la-clave"` en Secrets y la app la pide al entrar.
