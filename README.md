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
| ❌ Sacar otra foto | Foto movida/oscura, el GTIN no cierra o falta la serie | Subir otra foto en la misma tarjeta (o corregir a mano mirando el envase). No deja guardar hasta que el GTIN cierre y haya serie |

   - **Guardado automático**: las que salen ✅ (leídas del DataMatrix) se guardan solas apenas se cargan, y aparece "Se guardaron correctamente X foto(s)". Si alguna no se pudo leer (❌), un aviso dice cuál y pide sacar otra foto. Las ⚠️ esperan que alguien las compare con el envase y toque Guardar.
5. Al guardar, la tarjeta y la foto se borran y la pantalla queda lista para el próximo envase.
   - **Varias fotos a la vez**: arriba aparece un solo botón **Guardar X foto(s)** que guarda todas las que se leyeron bien (✅ y ⚠️). Si alguna no se leyó bien (❌), un aviso dice cuáles quedan afuera y que hay que volver a sacarlas; esas quedan abajo para subir otra foto.
6. Si ese envase (mismo GTIN + serie) **ya estaba cargado**, avisa quién y cuándo lo registró, y da dos opciones: **Reemplazar con estos datos** o **Descartar y dejar el anterior**.

### 📄 2. Registros y ✅ 3. Revisados (farmacéuticas)
Estas pestañas solo aparecen cuando se toca el nombre de **Claudia o Fernanda**. Los de mostrador solo ven "Leer fotos".

- **Registros**: lo que cargó todo el equipo y falta revisar. Por defecto se ve todo, y se puede filtrar por quién lo subió o buscar por GTIN, serie o lote. La farmacéutica tilda **✔ Revisado** en los que ya vio y toca **Pasar a Revisados**.
- **Revisados**: lo que ya revisó una farmacéutica, con quién y cuándo. Si se tildó uno por error, se puede volver a pendientes.
  - **📦 Archivar por mes**: pasa todos los revisados a un archivo de su mes (en la nube, una pestaña `Revisados AAAA-MM` en la planilla; en la PC, `registros/archivo/AAAA-MM.csv`). Abajo, en **Meses archivados**, se elige el mes para verlo y bajarlo en Excel. Un envase archivado se sigue detectando como duplicado.
  - **🗑️ Eliminar los revisados**: los borra para siempre. Pide escribir BORRAR para confirmar.
  - Cuando un mes ya terminó, en **Meses archivados** aparece un aviso y la opción **🗑️ Eliminar el archivo de ese mes** (también con BORRAR). El mes en curso no se puede eliminar.
- Las dos pestañas se descargan en **Excel** (GTIN y serie como texto, completos), con el nombre `Listado de registros sin revisar <fecha>` o `Listado de revisados <fecha>`. Columnas: GTIN, Serie, Lote, Vencimiento, Envió, Fecha de la foto y Guardado el; en Revisados también Revisado por y Revisado el.

Cada fila guarda: fecha de registro, fecha de la foto (y de dónde salió), usuario, rol, sucursal, nombre de la foto, GTIN, serie, lote, vencimiento, elaboración, si se leyó del DataMatrix o del texto, y si se corrigió a mano.

**Las fotos no se guardan**: se usan solo para leerlas y se descartan. El registro queda en `registros/registros.csv`, en la computadora donde corre la app (nunca se sube a GitHub).

## Dos formas de usarla

- **App con Android (en internet, sin instalar nada)**: se abre con un link desde el celular y los registros van a una planilla de Google Sheets. Paso a paso en [PUBLICAR_EN_LA_NUBE.md](PUBLICAR_EN_LA_NUBE.md).
- **App con Windows (en una PC de la farmacia)**: se instala en la PC y los celulares entran por el WiFi local. Los registros quedan en `registros/registros.csv`. Es la guía de abajo.

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
