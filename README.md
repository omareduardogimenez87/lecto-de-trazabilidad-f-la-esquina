# Lector de medicamentos con trazabilidad

App para Farmacia La Esquina (Sucursal Mitre) que lee los códigos de trazabilidad de los medicamentos desde una foto y los guarda en un registro, con la fecha de la foto y quién la envió. Así las farmacéuticas no tienen que copiar a mano GTIN, serie, lote y vencimiento.

La usan 6 personas: Fernanda y Claudia (farmacéuticas), y Omar, Yessi, Silvia y Maxi (mostrador). La lista está en [`usuarios.json`](usuarios.json), y los botones salen en ese mismo orden (mujeres primero y después hombres, cada grupo en orden alfabético).

## Qué hace (dos funciones)

### 📷 1. Leer fotos
1. Tocás tu nombre arriba (queda marcado).
2. Tocás **📷 Sacar foto** (abre directo la cámara del celular) o **🖼️ Elegir de la galería**. **Se lee sola**, no hace falta tocar otro botón. En la PC, los dos botones abren la ventana para elegir un archivo.
3. La app busca el **DataMatrix** (el cuadradito). Si lo lee, el dato es exacto. Si no puede, lee el **texto impreso** al lado (OCR).
4. Cada envase aparece en una tarjeta con la foto, los datos y el botón **Guardar** justo debajo:

| Estado | Qué significa | Qué hacer |
|---|---|---|
| ✅ Lista | Se leyó del DataMatrix | Tocar **Guardar** |
| ⚠️ Revisar | Se leyó del texto impreso y los datos cierran | Comparar con el envase, corregir si hace falta y tocar **Coincide con el envase: guardar** |
| ❌ Sacar otra foto | Foto movida/oscura, el GTIN no cierra o falta la serie | Subir otra foto en la misma tarjeta (o corregir a mano mirando el envase). No deja guardar hasta que el GTIN cierre y haya serie |

5. Al guardar, la tarjeta y la foto se borran y la pantalla queda lista para el próximo envase.
6. Si ese envase (mismo GTIN + serie) **ya estaba cargado**, avisa quién y cuándo lo registró, y da dos opciones: **Reemplazar con estos datos** o **Descartar y dejar el anterior**.

### 📄 2. Registros y ✅ 3. Revisados (solo farmacéuticas)
Estas pestañas solo aparecen para **Fernanda y Claudia**, y piden un **PIN**. La primera vez que cada una toca su nombre y abre "ingresá tu PIN", la app le pide que lo cree (4 a 6 números). El PIN no queda escrito en ningún lado: se guarda una huella en `registros/claves.json`. Si alguna se olvida el PIN, se borra ese archivo y cada una crea uno nuevo.

- **Registros**: lo que cargó todo el equipo y falta revisar. Por defecto se ve todo, y se puede filtrar por quién lo subió o buscar por GTIN, serie o lote. La farmacéutica tilda **✔ Revisado** en los que ya vio y toca **Pasar a Revisados**.
- **Revisados**: lo que ya revisó una farmacéutica, con quién y cuándo. Si se tildó uno por error, se puede volver a pendientes.
- Las dos pestañas se descargan en **Excel** o **CSV**, con las columnas GTIN, Serie, Lote, Vencimiento, Envió, Fecha de la foto, Estado y Guardado el (y en Revisados, también Revisado por y Revisado el).

Cada fila guarda: fecha de registro, fecha de la foto (y de dónde salió), usuario, rol, sucursal, nombre de la foto, GTIN, serie, lote, vencimiento, elaboración, si se leyó del DataMatrix o del texto, y si se corrigió a mano.

**Las fotos no se guardan**: se usan solo para leerlas y se descartan. El registro queda en `registros/registros.csv`, en la computadora donde corre la app (nunca se sube a GitHub).

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
