# Lector de medicamentos con trazabilidad

App para Farmacia La Esquina (Sucursal Mitre) que lee los códigos de trazabilidad de los medicamentos desde una foto y los guarda en un registro, con la fecha de la foto y quién la envió. Así las farmacéuticas no tienen que copiar a mano GTIN, serie, lote y vencimiento.

La usan 6 personas: Fernanda y Claudia (farmacéuticas), y Omar, Yessi, Silvia y Maxi (mostrador). La lista está en [`usuarios.json`](usuarios.json), y los botones salen en ese mismo orden (mujeres primero y después hombres, cada grupo en orden alfabético).

## Qué hace (dos funciones)

### 📷 1. Leer fotos
1. Tocás tu nombre arriba (queda marcado).
2. Tocás **📷 Sacar foto** (abre directo la cámara del celular) o **🖼️ Galería** (están uno al lado del otro). **Se lee sola**, no hace falta tocar otro botón. En la PC, los dos botones abren la ventana para elegir un archivo.
3. La app busca el **DataMatrix** (el cuadradito). Si lo lee, el dato es exacto. Si no puede, lee el **texto impreso** al lado (OCR).
4. Cada envase aparece en una tarjeta con la foto, los datos y el botón **Guardar** justo debajo:

| Estado | Qué significa | Qué hacer |
|---|---|---|
| ✅ Lista | Se leyó del DataMatrix | Tocar **Guardar** |
| ⚠️ Revisar | Se leyó del texto impreso y los datos cierran | Comparar con el envase, corregir si hace falta y tocar **Coincide con el envase: guardar** |
| ❌ Sacar otra foto | Foto movida/oscura, el GTIN no cierra o falta la serie | Tocar **📷 Sacar de nuevo** en la misma tarjeta (abre la cámara), **🗑️ Cancelar y eliminar** para quitarla sin guardar, o corregir a mano mirando el envase. No deja guardar hasta que el GTIN cierre y haya serie |

   - **Guardado automático**: las que salen ✅ (leídas del DataMatrix) se guardan solas apenas se cargan, y aparece "Se guardaron correctamente X foto(s)". Si alguna no se pudo leer (❌), un aviso dice cuál y pide sacar otra foto. Las ⚠️ esperan que alguien las compare con el envase y toque Guardar.
5. Al guardar, la tarjeta y la foto se borran y la pantalla queda lista para el próximo envase.
   - **Varias fotos a la vez**: arriba aparece un solo botón **Guardar X foto(s)** que guarda todas las que se leyeron bien (✅ y ⚠️). Si alguna no se leyó bien (❌), un aviso dice cuáles quedan afuera y que hay que volver a sacarlas; esas quedan abajo para subir otra foto.
6. Si ese envase (mismo GTIN + serie) **ya estaba cargado**, avisa quién y cuándo lo registró, y da dos opciones: **Reemplazar con estos datos** o **Descartar y dejar el anterior**.

### 📄 2. Registros y ✅ 3. Revisados (farmacéuticas)
Estas pestañas solo aparecen cuando se toca el nombre de **Claudia o Fernanda**. Los de mostrador solo ven "Leer fotos".

- **Registros**: lo que cargó todo el equipo y falta revisar. Por defecto se ve todo, y se puede filtrar por quién lo subió o buscar por GTIN, serie o lote. La farmacéutica tilda **✔ Revisado** en los que ya vio y toca **Pasar a Revisados**.
- **Revisados**: lo que ya revisó una farmacéutica, con quién y cuándo. Si se tildó uno por error, se puede volver a pendientes.
  - **📦 Archivar por mes**: pasa todos los revisados a un archivo de su mes (en la nube, una pestaña `Revisados AAAA-MM` en la planilla; en la PC, `registros/archivo/AAAA-MM.csv`). Abajo, en **Meses archivados**, se elige el mes para verlo y bajarlo en Excel. Un envase archivado se sigue detectando como duplicado.
  - **🗑️ Eliminar los revisados**: los borra para siempre. Para evitar un borrado por error, pregunta dos veces antes de hacerlo.
  - Cuando un mes ya terminó, en **Meses archivados** aparece un aviso y la opción **🗑️ Eliminar el archivo de ese mes** (también pregunta dos veces). El mes en curso no se puede eliminar.
- Las dos pestañas se descargan en **Excel** (GTIN y serie como texto, completos), con el nombre `Listado de registros sin revisar <fecha>` o `Listado de revisados <fecha>`. Columnas: GTIN, Serie, Lote, Vencimiento, Envió, Fecha de la foto y Guardado el; en Revisados también Revisado por y Revisado el.

Cada fila guarda: fecha de registro, fecha de la foto (y de dónde salió), usuario, rol, sucursal, nombre de la foto, GTIN, serie, lote, vencimiento, elaboración, si se leyó del DataMatrix o del texto, y si se corrigió a mano.

**Las fotos no se guardan**: se usan solo para leerlas y se descartan. El registro queda en `registros/registros.csv`, en la computadora donde corre la app (nunca se sube a GitHub).

## Dos formas de usarla

- **App con Android (en internet, sin instalar nada)**: se abre con un link desde el celular y los registros van a una planilla de Google Sheets. Paso a paso en [PUBLICAR_EN_LA_NUBE.md](PUBLICAR_EN_LA_NUBE.md).
- **App con Windows (en una PC de la farmacia)**: se instala en la PC y los celulares entran por el WiFi local. Los registros quedan en `registros/registros.csv`. Es la guía de abajo.

### 💬 Consultas rápidas del mostrador
Abajo de las fotos hay una sección **💬 Consultas rápidas** (sin IA, no usa internet). Se escribe una palabra (OSDE, Galeno, Ctrl+V, PICC, "quién trabaja hoy") o se toca una categoría (Obras sociales, Horarios, Promos, Mostrador...). Solo muestra lo que está en [`consultas/Base_Consultas_Mostrador_Mitre.md`](consultas/Base_Consultas_Mostrador_Mitre.md) y sigue sus reglas: lo ⚠️ dice "a confirmar con Germán o la farmacéutica", las promos con fecha "Hasta" pasada salen como **vencida**, las consultas de salud (dosis, para qué sirve) se derivan a la farmacéutica, y si no hay dato lo dice.

**Cada viernes (horario nuevo)**: en el archivo `.md` se cambia la sección **2.1** (período y tabla). Después, en GitHub: abrir la carpeta `consultas` → **Add file → Upload files** → arrastrar el archivo nuevo con **el mismo nombre** → **Commit changes**. La app en la nube se actualiza sola en un par de minutos. Si hoy queda fuera del período cargado, la app responde "Todavía no está cargado el horario de esa fecha".

**Buscar**: se busca con **Enter** o con el botón **🔎**, y con **🎤** se dicta la consulta por voz (usa el reconocimiento de voz del navegador: en Chrome de Android funciona; si el 🎤 no aparece, se puede usar el micrófono del teclado del celular).

**▮▮ Escanear código o producto**: en Consultas, debajo del buscador (**Asistente La Esquina**, sin IA), el botón abre la cámara y se saca una foto del código de barras (o del DataMatrix) y la app muestra la oferta del producto, hasta cuándo vale y cuánto paga el cliente. Los datos salen de [`consultas/Ofertas_OTC_completo.xlsx`](consultas/Ofertas_OTC_completo.xlsx). Si el producto no tiene "Precio regular" dice "sin precio cargado"; si el código no está, "Producto no cargado". La categoría **🏷️ Ofertas** muestra las promociones de la semana (tarjetas, bancos, laboratorios) y la lista completa de productos en oferta. Para cargar precios o una oferta nueva, se edita el Excel y se sube igual que el `.md` (mismo nombre, carpeta `consultas`).

> **Por ahora está apagado** (hasta tener los códigos cargados). Para prenderlo: Streamlit Cloud → Manage app → ⋮ → Settings → Secrets, agregar `escaneo_activo = true`, Save y Reboot app. Para apagarlo de nuevo, borrar esa línea.

**🗄️ ¿En qué cajón está?**: al buscar un medicamento (aunque esté mal escrito: "glibencamida", "dexametazona", "tafirl") la app dice en qué cajón está, con el nombre tal como está anotado en [`consultas/CAJONES_corregido.xlsx`](consultas/CAJONES_corregido.xlsx). Los nombres que en la hoja "Cambios" dicen "A confirmar" salen con ⚠️. Si el producto tiene oferta OTC vigente, también la muestra (verificar la presentación exacta). La categoría **🗄️ Cajones** muestra el mapa completo. Formato del Excel: primera columna el cajón, las siguientes lo que hay adentro. Se reemplaza igual que los otros (mismo nombre, carpeta `consultas`).

**🛍️ Catálogo de productos**: el buscador también busca en [`consultas/Ventas_Producto_Categoria_Marcas.xlsx`](consultas/Ventas_Producto_Categoria_Marcas.xlsx) (SKU, producto, categoría y marca), por nombre, marca, categoría o código SKU, aunque tenga algún error de tipeo. Si hay muchos resultados muestra cuántos hay por categoría y por marca, y los primeros 10. Los que tienen oferta OTC salen con 🏷️. Se reemplaza igual que los otros (mismo nombre, carpeta `consultas`).

> Ojo: la app es pública, así que cualquiera con el link ve estos datos (horarios, token, códigos).

### 📝 Nota u observación
Al elegir tu nombre aparece, chiquito debajo de los botones de foto, **📝 Nota u observación** para dejar algo que haya que cambiar o agregar a la app. Cada uno ve las notas que escribió hasta que cierra la app. **Omar** (`"ve_notas": true` en `usuarios.json`) ve todas, con quién y cuándo, y las borra con **✅ Listo, borrar** a medida que aplica los cambios. Se guardan en la pestaña **Notas** de la planilla (en la PC, `registros/notas.csv`). Opcional: si se agrega `clave_notas = "..."` en Secrets, la app pide esa clave para ver las notas.

### ❓ Ayuda
La ayuda está dentro del **Asistente La Esquina** (siempre visible, debajo de las fotos) (sin IA, no usa internet): se escribe la duda en el mismo buscador ("la foto no se lee", "archivar", "descargar excel") Los únicos botones de categoría son Ofertas y Cajones; el resto de los datos (programas, PICC, obras sociales, horarios, etc.) se encuentra escribiendo.

### Reportar incidencia a Equipo TI
Al final de la app hay un botón con el logo de I.T. AREA, **Reportar incidencia a Equipo TI** (chico y discreto, con borde violeta y verde como su página), que abre el sistema de tickets (<https://area-t-i-tickets.vercel.app/>) en otra pestaña. Debajo, **Página oficial Farmacia La Esquina** abre <https://farmacialaesquina.com.ar/> en otra pestaña.

## Cómo se instala (paso a paso, en Windows)

Se hace una sola vez, en la computadora de la farmacia que va a hacer de "servidor".

1. **Instalar Python**: bajarlo de <https://www.python.org/downloads/> e instalarlo. En la primera pantalla tildar **"Add python.exe to PATH"**.
2. **Instalar Tesseract** (el lector de texto): bajar el instalador de <https://github.com/UB-Mannheim/tesseract/wiki> e instalarlo con las opciones por defecto. Si no se instala, la app funciona igual pero solo lee DataMatrix.
3. **Bajar este proyecto**: en GitHub, botón verde **Code → Download ZIP**, y descomprimirlo (por ejemplo en `Documentos\lector-trazabilidad`).
4. Abrir esa carpeta, hacer clic en la barra de dirección, escribir `cmd` y Enter. Se abre una ventana negra (la "terminal") ya ubicada en la carpeta.
5. Instalar las librerías (una sola vez):
   ```
   python -m pip install -r requirements.txt
   ```
6. Abrir la app:
   ```
   python -m streamlit run app.py
   ```
   Se abre sola en el navegador (`http://localhost:8501`). Para cerrarla, en la ventana negra apretar `Ctrl + C`.

> La app busca Tesseract sola en `C:\Program Files\Tesseract-OCR`. Si lo instalaste en otra carpeta, verás un aviso amarillo en el menú de la izquierda.
>
> La primera vez que se abre, Windows puede preguntar si permitís el acceso a la red a Python: elegí **Redes privadas** y **Permitir**. Eso hace falta para abrirla desde el celular.

### Usarla desde el celular
Con la app abierta en la PC, la terminal muestra una línea **Network URL** (por ejemplo `http://192.168.0.15:8501`). Desde un celular conectado **al mismo WiFi** de la farmacia, abrir esa dirección en el navegador. Ahí "Subir fotos" ofrece la cámara o la galería.

## Consejos para que la foto se lea bien
- **Un envase por foto**, de cerca, con el cuadradito y el texto bien enfocados.
- Buena luz, sin reflejos (las cajas brillantes reflejan mucho).
- **No dibujar ni marcar encima** del código.
- Si la mandan por WhatsApp, la foto pierde la fecha original y se comprime. Mejor subirla directo desde la galería.

## Prueba con las 8 fotos de muestra (22/11/2026)
Las muestras tienen marcador verde encima del DataMatrix y vienen comprimidas por WhatsApp (sin fecha EXIF), así que son un caso difícil:

- 1 se leyó por DataMatrix (exacta).
- 4 se leyeron completas y bien por el texto impreso.
- 2 salieron con algún dato mal: una con la serie con letras confundidas (H→W, S→5) y otra sin GTIN y con el lote mal.
- 1 no se pudo leer.

La que no tenía GTIN y la que no se pudo leer quedaron en ❌ y piden otra foto. **Ojo**: un error en la serie o el lote del texto impreso no siempre se puede detectar solo (el GTIN tiene dígito verificador, la serie y el lote no). Por eso los ⚠️ hay que compararlos con el envase antes de tildar.

## Para desarrolladores
```
lector/gs1.py       interpretar GS1 (DataMatrix) y el texto impreso
lector/imagen.py    leer la foto: DataMatrix (zxing-cpp), texto (Tesseract), fecha EXIF
lector/calidad.py   nitidez de la foto y decidir ✅ / ⚠️ / ❌
lector/registro.py  guardar en CSV y exportar a Excel
lector/consultas.py consultas rápidas del mostrador (busca en consultas/*.md)
lector/ofertas.py   ofertas OTC del Excel (consultas/Ofertas_OTC_completo.xlsx)
lector/cajones.py   ¿en qué cajón está? (consultas/CAJONES_corregido.xlsx)
lector/catalogo.py  catálogo de productos (consultas/Ventas_Producto_Categoria_Marcas.xlsx)
app.py              la app (Streamlit)
procesar_carpeta.py procesar una carpeta de fotos desde la terminal
tests/              pruebas automáticas:  python -m pytest
```

Probar una carpeta de fotos sin abrir la app:
```
python procesar_carpeta.py CARPETA_CON_FOTOS --usuario Omar
```

## Próximos pasos posibles
1. Probar con fotos reales del mostrador, sin marcas y sin pasar por WhatsApp.
2. Leer el DataMatrix en vivo con la cámara del celular (más rápido y exacto que una foto).
3. Si el texto impreso sigue fallando, usar Claude (IA con visión) para leer la foto.
4. Usuarios con contraseña y publicar la app para usarla fuera del WiFi del local.

## Privacidad
Este repositorio es **privado**. No se suben fotos ni registros (lo impide el `.gitignore`).

### Contacto de la sucursal y envío para imprimir
- **📤 Enviar para imprimir**: primero se saca la foto (o se elige de la galería, también PDF) y al tocar **Enviar** se abre el menú *Compartir* del celular con el texto "Te comparto un archivo para imprimir". Ahí se elige WhatsApp o Gmail y el contacto de la Mitre (la app no puede elegir el contacto sola). Funciona en Chrome de Android; si el navegador no deja compartir archivos, muestra un aviso.
- **WhatsApp Sucursal Mitre** (+54 9 385 475-0195) y **Correo esquinamitre@fesquina.com.ar**: accesos directos con el mensaje ya escrito (no adjuntan archivos).
- Fondo de la app: degradado lima, crema y lila.
- **Probar con otro número o correo** (sin tocar el código): en Streamlit Cloud → Manage app → ⋮ → Settings → Secrets, agregar
  `whatsapp_destino = "3856210820"` y/o `correo_destino = "alguien@ejemplo.com"` y guardar (la app agrega el 549 si falta). Para volver a los de la Mitre, borrar esas líneas y guardar.

### Lista de precios de la quincena (Word de comercial)
El asistente también busca en [`consultas/Precios_Quincena.docx`](consultas/Precios_Quincena.docx): el Word con las tablas por rubro (producto, código, precio regular, oferta y fechas). Aparece junto con las Ofertas OTC. Cuando llegue la lista nueva, se sube el Word con **el mismo nombre** `Precios_Quincena.docx` a la carpeta `consultas` (Add file → Upload files), igual que el Excel de ofertas.

### Cobertura de medicamentos (Vale Salud y PAMI)
En el buscador: **medicamento + "cobertura"** (ej.: "clinal cobertura"). Con "vale" o "vale salud" muestra solo Vale Salud; con "pami" solo PAMI (Alfabeta); sin nombrarla, las dos.
La app arma una tabla **obra social → %** con cada vademécum cargado en `consultas/` con el nombre `Vademecum_<Obra_social>.csv` (o `.xlsx`), por ejemplo `Vademecum_Vale_Salud.csv` (el que se baja con el ícono ⬇ de valesalud.ar). Para sumar otra obra social, se sube su archivo con ese formato de nombre; para actualizar, el archivo nuevo con el mismo nombre. PAMI se consulta por link a Alfabeta hasta tener un archivo.
