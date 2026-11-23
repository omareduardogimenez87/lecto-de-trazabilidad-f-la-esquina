"""Lector de trazabilidad - Farmacia La Esquina.

Para abrirla:  streamlit run app.py

Función 1 (📷 Leer fotos): se toca el nombre, se sube o se saca la foto y la
app lee los datos sola. Avisa si la foto no sirve y pide otra. Al lado de cada
lectura está el botón Guardar; al guardar se limpia la pantalla para la próxima.
Función 2 (📄 Registros): queda guardado cada registro con quién envió la
foto y la fecha. Se puede descargar en Excel. Las fotos NO se guardan.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import re
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from lector import cajones, consultas, ofertas, registro
from lector.calidad import ESTADO_OK, ESTADO_OTRA_FOTO, estado, medir
from lector.gs1 import gtin_es_valido
from lector.imagen import abrir, analizar, fecha_de_la_foto, leer_codigos_de_producto, ocr_disponible

CONFIG = json.loads((Path(__file__).parent / "usuarios.json").read_text(encoding="utf-8"))
USUARIOS = {u["nombre"]: u for u in CONFIG["usuarios"]}
SUCURSAL = CONFIG.get("sucursal", "")
CAMPOS = [("gtin", "GTIN (01)"), ("serie", "Serie (21)"), ("lote", "Lote (10)"), ("vencimiento", "Vencimiento"), ("elaboracion", "Elaboración")]
EN_MAYUSCULAS = ("gtin", "serie", "lote")
# Columnas que se ven en Registros y Revisados y salen en el Excel, con su título.
# "Estado" no se muestra (pedido de Edu), pero se sigue guardando en el registro.
COLUMNAS_REGISTRO = {
    "gtin": "GTIN",
    "serie": "Serie",
    "lote": "Lote",
    "vencimiento": "Vencimiento",
    "usuario": "Envió",
    "fecha_foto": "Fecha de la foto",
    "fecha_registro": "Guardado el",
}

IMAGENES = Path(__file__).parent / "imagenes"
ICONO = IMAGENES / "icono.png"  # la cruz de Farmacia La Esquina
MARCA_DE_AGUA = IMAGENES / "marca_de_agua.png"  # logo "la esquina", casi transparente


def en_base64(archivo: Path) -> str:
    return base64.b64encode(archivo.read_bytes()).decode()


st.set_page_config(
    page_title="Lector de trazabilidad",
    page_icon=str(ICONO) if ICONO.exists() else "💊",
    layout="wide",
    initial_sidebar_state="collapsed",
)
# Botones de nombres y pestañas más grandes y separados (pedido de Edu, 22/11/2026).
# El violeta del seleccionado viene de primaryColor en .streamlit/config.toml.
st.markdown(
    """<style>
    /* Nombres en grilla pareja: 2 por fila en el celular (Claudia-Fernanda / Silvia-Yessi / Maxi-Omar)
       y 3 por fila en pantallas más anchas, así Maxi y Omar quedan siempre juntos al final. */
    [data-testid="stButtonGroup"] [role="radiogroup"] {
        display: grid !important; grid-template-columns: repeat(2, 1fr); gap: .75rem !important;
    }
    @media (min-width: 480px) {
        [data-testid="stButtonGroup"] [role="radiogroup"] { grid-template-columns: repeat(3, 1fr); }
    }
    [data-testid="stButtonGroup"] button { padding: .55rem .8rem !important; min-height: 3rem; width: 100%; }
    [data-testid="stButtonGroup"] button p { font-size: 1.15rem !important; }
    [role="tablist"] { gap: .6rem !important; }
    [data-testid="stTab"] { padding: .6rem 0 !important; }
    [data-testid="stTab"] p { font-size: 1rem !important; }
    </style>""",
    unsafe_allow_html=True,
)
if MARCA_DE_AGUA.exists():
    st.markdown(
        f"""<style>
        [data-testid="stAppViewContainer"] {{
            background-image: url("data:image/png;base64,{en_base64(MARCA_DE_AGUA)}");
            background-repeat: no-repeat;
            background-position: center 60%;
            background-size: min(80vw, 700px) auto;
            background-attachment: fixed;
        }}
        </style>""",
        unsafe_allow_html=True,
    )
if ICONO.exists():
    st.markdown(
        f"""<h1 style="display:flex;align-items:center;gap:.5rem;padding-bottom:0">
        <img src="data:image/png;base64,{en_base64(ICONO)}" alt="" style="height:1.4em;width:1.4em">
        Lector de trazabilidad</h1>""",
        unsafe_allow_html=True,
    )
else:
    st.title("💊 Lector de trazabilidad")
st.caption(f"Farmacia La Esquina · Sucursal {SUCURSAL}")



def secretos() -> dict:
    """Lee la configuración secreta de la nube (.streamlit/secrets.toml o el panel de
    Streamlit Cloud). En la PC normalmente no existe, y entonces devuelve {}."""
    try:
        return st.secrets.to_dict()
    except Exception:
        return {}


@st.cache_resource(show_spinner="Conectando con la planilla de registros…")
def abrir_planilla(cuenta: tuple, url: str):
    import gspread

    return gspread.service_account_from_dict(dict(cuenta)).open_by_url(url).sheet1


SECRETOS = secretos()

# App con Android (en la nube): si hay una clave configurada, se pide una vez.
CLAVE = str(SECRETOS.get("clave_acceso", "") or "")
if CLAVE and not st.session_state.get("clave_ok"):
    escrita = st.text_input("Clave de acceso", type="password")
    if escrita and escrita == CLAVE:
        st.session_state["clave_ok"] = True
        st.rerun()
    if escrita:
        st.error("Clave incorrecta.")
    st.stop()

# App con Android: los registros van a Google Sheets. Sin planilla configurada
# (app con Windows), se guardan en registros/registros.csv como siempre.
# La cuenta de servicio de Google se pega tal cual (el archivo .json entero) en
# `cuenta_google`, o como tabla [gcp_service_account].
CUENTA = SECRETOS.get("gcp_service_account") or SECRETOS.get("cuenta_google")
URL_PLANILLA = SECRETOS.get("planilla_url") or SECRETOS.get("planilla", {}).get("url", "")
if CUENTA and URL_PLANILLA:
    try:
        if isinstance(CUENTA, str):
            CUENTA = json.loads(CUENTA)
        registro.usar_planilla(abrir_planilla(tuple(sorted(CUENTA.items())), URL_PLANILLA))
    except Exception as e:
        st.error(f"No se pudo abrir la planilla de registros de Google: {e}")
        st.stop()

st.session_state.setdefault("items", [])
st.session_state.setdefault("ronda", 0)  # cambia después de guardar, para vaciar la carga de fotos
st.session_state.setdefault("avisos", [])  # mensajes para mostrar después de guardar
st.session_state.setdefault("leidas", set())  # huellas de las fotos ya leídas en esta ronda

# ------------------------------------------------------------ ¿quién usa la app?
# Los nombres salen en el orden de usuarios.json.
# El avatar (emoji) solo se ve en el botón; en los registros se guarda el nombre solo.
nombre = st.pills(
    "¿Quién sos? Tocá tu nombre",
    list(USUARIOS),
    selection_mode="single",
    key="usuario",
    format_func=lambda n: f"{USUARIOS[n].get('avatar', '')} {n}".strip(),
)
usuario = USUARIOS.get(nombre)
es_farmaceutica = bool(usuario and usuario["rol"].lower().startswith("farmac"))

# Registros y Revisados solo aparecen si se elige una farmacéutica (Claudia o Fernanda).
puede_ver_registros = es_farmaceutica
if not ocr_disponible():
    st.warning("El lector de texto (Tesseract) no está instalado: solo se van a leer los DataMatrix. Mirá el README.")


def procesar(contenido: bytes, nombre_archivo: str) -> list[dict]:
    """Lee una foto y devuelve un ítem por cada envase encontrado."""
    img = abrir(io.BytesIO(contenido))
    fecha, origen = fecha_de_la_foto(img, nombre_archivo)
    if fecha is None:
        fecha, origen = registro.ahora(), "fecha de carga (la foto no traía fecha)"
    calidad = medir(img)
    items = []
    for lectura in analizar(img):
        est, motivos = estado(lectura, calidad)
        items.append(
            dict(
                id=uuid.uuid4().hex,
                foto=contenido,
                archivo_foto=nombre_archivo,
                fecha_foto=fecha.strftime(registro.FORMATO_FECHA),
                origen_fecha_foto=origen,
                lectura=lectura.como_dict(),
                nitidez=calidad.nitidez,
                estado=est,
                motivos=motivos,
            )
        )
    return items


def reemplazar(item_id: str, contenido: bytes, nombre_archivo: str) -> None:
    """Cambia la foto de un ítem por una nueva (cuando la app pidió otra)."""
    items = st.session_state["items"]
    i = next(k for k, it in enumerate(items) if it["id"] == item_id)
    items[i : i + 1] = procesar(contenido, nombre_archivo)


def fue_corregido(it: dict, datos: dict) -> bool:
    original = {c: (it["lectura"].get(c) or "") for c, _ in CAMPOS}
    for c in EN_MAYUSCULAS:
        original[c] = original[c].upper()
    return any(datos[c] != original[c] for c, _ in CAMPOS)


def datos_de(it: dict) -> dict:
    """Los datos tal como están ahora en la tarjeta (con las correcciones a mano)."""
    datos = {c: st.session_state.get(f"{c}_{it['id']}", it["lectura"].get(c, "") or "").strip() for c, _ in CAMPOS}
    for c in EN_MAYUSCULAS:
        datos[c] = datos[c].upper()
    return datos


def faltantes(datos: dict) -> list[str]:
    """Lo que falta para poder guardar (vacío = se puede guardar)."""
    faltan = []
    if not gtin_es_valido(datos["gtin"]):
        faltan.append("el GTIN no cierra con el dígito verificador" if datos["gtin"] else "falta el GTIN")
    if not datos["serie"]:
        faltan.append("falta la serie")
    return faltan


def se_puede_guardar_junto(it: dict) -> bool:
    """Entra en "Guardar X fotos": se leyó bien (✅ o ⚠️), tiene GTIN y serie y no es un duplicado pendiente."""
    return it["estado"] != ESTADO_OTRA_FOTO and not faltantes(datos_de(it)) and not it.get("duplicado")


def guardar_varios(lista: list[dict]) -> None:
    """Guarda de una vez todas las lecturas buenas. Las que ya estaban cargadas quedan
    en pantalla con el aviso de duplicado, para elegir qué hacer con cada una."""
    guardadas = 0
    for it in lista:
        fila = fila_de(it)
        previo = registro.buscar(fila["gtin"], fila["serie"])
        if previo:
            it["duplicado"] = previo
            continue
        registro.guardar([fila])
        cerrar_tarjeta(it, None)
        guardadas += 1
    if guardadas:
        st.session_state["avisos"].append(("success", f"✅ Se guardaron correctamente {guardadas} foto(s)."))
    duplicadas = len(lista) - guardadas
    if duplicadas:
        st.session_state["avisos"].append(
            ("warning", f"⚠️ {duplicadas} ya estaba(n) cargada(s): quedaron abajo para que elijas si reemplazar o descartar.")
        )


def fila_de(it: dict) -> dict:
    """Arma la fila del registro con los datos de la tarjeta."""
    datos = datos_de(it)
    if fue_corregido(it, datos):
        estado_final = "Corregido a mano"
    elif it["estado"] == ESTADO_OK:
        estado_final = "Leído del DataMatrix"
    else:
        estado_final = "Revisado por el usuario"
    return dict(
        **datos,
        fecha_foto=it["fecha_foto"],
        origen_fecha_foto=it["origen_fecha_foto"],
        usuario=usuario["nombre"],
        rol=usuario["rol"],
        sucursal=SUCURSAL,
        archivo_foto=it["archivo_foto"],
        fuente=it["lectura"]["fuente"],
        estado=estado_final,
        gtin_valido=gtin_es_valido(datos["gtin"]),
        avisos=" · ".join(it["motivos"]),
    )


def cerrar_tarjeta(it: dict, aviso: tuple[str, str]) -> None:
    """Saca la tarjeta de la pantalla y deja todo listo para el próximo envase."""
    if aviso:
        st.session_state["avisos"].append(aviso)
    st.session_state["items"] = [x for x in st.session_state["items"] if x["id"] != it["id"]]
    for clave in [f"{c}_{it['id']}" for c, _ in CAMPOS] + [f"otra_{it['id']}"]:
        st.session_state.pop(clave, None)
    # Si no queda nada pendiente, vaciar también la carga de fotos.
    if not st.session_state["items"]:
        st.session_state["ronda"] += 1
        st.session_state["leidas"] = set()


def guardar_item(it: dict) -> None:
    """Guarda un envase. Si ya estaba cargado, no guarda y pregunta qué hacer."""
    fila = fila_de(it)
    previo = registro.buscar(fila["gtin"], fila["serie"])
    if previo:
        it["duplicado"] = previo  # la tarjeta muestra el aviso con las opciones
        return
    registro.guardar([fila])
    cerrar_tarjeta(it, ("success", f"✅ Guardado: GTIN {fila['gtin']} · serie {fila['serie']}. Ya podés cargar la próxima foto."))


TIPOS_FOTO = ["jpg", "jpeg", "png", "webp"]

# Estilo de los dos botones grandes (📷 cámara y 🖼️ galería), en lugar del "Subir" de Streamlit.
ESTILO_BOTONES = """
<style>
.st-key-camara [data-testid="stFileUploaderDropzoneInstructions"],
.st-key-camara [data-testid="stFileChip"],
.st-key-camara [data-testid="stFileChips"] > div:not(:has(button[aria-label="Add files"])) { display: none !important; }
.st-key-camara section { padding: 0; background: transparent; border: none; display: block; }
.st-key-camara section > span, .st-key-camara [data-testid="stFileChips"], .st-key-camara [data-testid="stFileChips"] > *, .st-key-camara section button {
  display: block; width: 100%; max-width: none;
}
.st-key-camara section button {
  min-height: 4.5rem; font-size: 0 !important; border-radius: 0.75rem; border: 1px solid rgba(49, 51, 63, 0.2);
}
.st-key-camara section button * { display: none !important; }
.st-key-galeria [data-testid="stFileUploaderDropzoneInstructions"],
.st-key-galeria [data-testid="stFileChip"],
.st-key-galeria [data-testid="stFileChips"] > div:not(:has(button[aria-label="Add files"])) { display: none !important; }
.st-key-galeria section { padding: 0; background: transparent; border: none; display: block; }
.st-key-galeria section > span, .st-key-galeria [data-testid="stFileChips"], .st-key-galeria [data-testid="stFileChips"] > *, .st-key-galeria section button {
  display: block; width: 100%; max-width: none;
}
.st-key-galeria section button {
  min-height: 4.5rem; font-size: 0 !important; border-radius: 0.75rem; border: 1px solid rgba(49, 51, 63, 0.2);
}
.st-key-galeria section button * { display: none !important; }
.st-key-camara section button::before { content: "📷  Sacar foto"; font-size: 1.15rem; }
.st-key-galeria section button::before { content: "🖼️  Galería"; font-size: 1.15rem; }
/* Los dos botones en una sola línea, también en el celular. */
.st-key-fotos [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.5rem; }
.st-key-fotos [data-testid="stColumn"] { flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; }
.st-key-camara section button { background: #c62f3f; color: white; border-color: #c62f3f; }
.st-key-galeria section button { background: white; color: #31333f !important; opacity: 1 !important; }
</style>
"""

# En el celular, "capture" hace que el botón abra directo la cámara trasera.
# Streamlit no tiene esa opción, así que se la agregamos al botón con un poco de JavaScript.
# (Se usa la cámara del propio celular: funciona aunque la app se abra por http en el WiFi.)
SCRIPT_CAMARA = """
<script>
const doc = window.parent.document;
function ajustar() {
  doc.querySelectorAll('.st-key-camara input[type=file]').forEach(i => {
    if (i.getAttribute('capture') !== 'environment') i.setAttribute('capture', 'environment');
    if (i.getAttribute('accept') !== 'image/*') i.setAttribute('accept', 'image/*');
  });
  doc.querySelectorAll('.st-key-galeria input[type=file]').forEach(i => {
    if (i.getAttribute('accept') !== 'image/*') i.setAttribute('accept', 'image/*');
  });
}
ajustar();
new MutationObserver(ajustar).observe(doc.body, {childList: true, subtree: true});
</script>
"""


def botones_de_foto(ronda: int) -> list:
    """Dos botones grandes: sacar foto con la cámara o elegir de la galería."""
    st.markdown(ESTILO_BOTONES, unsafe_allow_html=True)
    with st.container(key="fotos"):
        col_cam, col_gal = st.columns(2)
    with col_cam:
        with st.container(key="camara"):
            de_camara = st.file_uploader(
                "Cámara", type=TIPOS_FOTO, accept_multiple_files=True, key=f"camara_{ronda}", label_visibility="collapsed"
            )
    with col_gal:
        with st.container(key="galeria"):
            de_galeria = st.file_uploader(
                "Galería", type=TIPOS_FOTO, accept_multiple_files=True, key=f"galeria_{ronda}", label_visibility="collapsed"
            )
    components.html(SCRIPT_CAMARA, height=0)
    return list(de_camara or []) + list(de_galeria or [])


if puede_ver_registros:
    # Las farmacéuticas tienen tres secciones, así que van en pestañas.
    tab_leer, tab_pendientes, tab_revisados = st.tabs(["📷 Leer fotos", "📄 Registros", "✅ Revisados"])
else:
    # Mostrador (o sin nombre elegido): una sola sección, sin barra de pestañas.
    tab_leer = contextlib.nullcontext()
    tab_pendientes = tab_revisados = None

# ------------------------------------------------------------ función 1: leer
with tab_leer:
    # Mensajes del último guardado (se muestran una vez y se borran).
    for tipo, texto in st.session_state["avisos"]:
        getattr(st, tipo)(texto)
    st.session_state["avisos"] = []

    # Los botones de foto se ven de entrada, aun sin nombre elegido (pedido de Edu, 23/11/2026).
    st.write(
        "Sacá una foto o elegila de la galería. Que se vea el **cuadradito (DataMatrix)** y los datos "
        "impresos al lado, de cerca, con buena luz y sin reflejos. **Se lee sola al cargarla.**"
    )
    fotos = botones_de_foto(st.session_state["ronda"])
    # Si cargan una foto sin haber elegido quién es, se pide el nombre (la foto queda y se lee al elegirlo).
    if fotos and not usuario:
        st.warning("☝️ Antes de leer la foto, **tocá tu nombre** arriba. Tu nombre queda elegido hasta que cierres la app.")
    if usuario:
        # Leer automáticamente las fotos nuevas (sin tener que tocar otro botón).
        nuevas = [f for f in fotos or [] if hashlib.sha1(f.getvalue()).hexdigest() not in st.session_state["leidas"]]
        if nuevas:
            with st.spinner("Leyendo…"):
                for foto in nuevas:
                    contenido = foto.getvalue()
                    st.session_state["leidas"].add(hashlib.sha1(contenido).hexdigest())
                    try:
                        st.session_state["items"] += procesar(contenido, foto.name)
                    except Exception as e:
                        st.error(f"No se pudo abrir {foto.name}: {e}")
            # Guardado automático (pedido de Edu, 23/11/2026): las que se leyeron del DataMatrix
            # (✅, exactas) se guardan solas. Las ⚠️ esperan que alguien las compare con el envase,
            # y las ❌ piden otra foto.
            nuevos = [it for it in st.session_state["items"] if it.get("auto") is None]
            for it in nuevos:
                it["auto"] = True
            listas = [it for it in nuevos if it["estado"] == ESTADO_OK and se_puede_guardar_junto(it)]
            malas = [it for it in nuevos if it["estado"] == ESTADO_OTRA_FOTO or faltantes(datos_de(it))]
            if listas:
                guardar_varios(listas)
            if malas:
                nombres = ", ".join(f"**{it['archivo_foto']}**" for it in malas)
                st.session_state["avisos"].append(
                    ("error", f"❌ No se pudo leer bien: {nombres}. **Sacá otra foto de ese envase** (está abajo, marcado con ❌).")
                )
            if listas or malas:
                st.rerun()

    items = st.session_state["items"] if usuario else []

    # Varias fotos a la vez: un solo botón para guardar todas las que se leyeron bien.
    if len(items) > 1:
        buenas = [it for it in items if se_puede_guardar_junto(it)]
        malas = [it for it in items if it["estado"] == ESTADO_OTRA_FOTO or faltantes(datos_de(it))]
        with st.container(border=True):
            if buenas:
                if st.button(f"💾 Guardar {len(buenas)} foto(s)", type="primary", key="guardar_todas", use_container_width=True):
                    guardar_varios(buenas)
                    st.rerun()
                if any(it["estado"] != ESTADO_OK for it in buenas):
                    st.caption("Las marcadas ⚠️ se leyeron del texto impreso: miralas abajo antes de guardar.")
            if malas:
                nombres = ", ".join(f"**{it['archivo_foto']}**" for it in malas)
                if buenas:
                    texto = f"Se guardan todas **excepto {len(malas)}** que no se leyeron bien: {nombres}."
                else:
                    texto = f"Ninguna foto se leyó bien: {nombres}."
                st.warning(texto + " **Volvé a sacar esa(s) foto(s)**: están abajo, marcadas con ❌.")

    for it in items:
        lec = it["lectura"]
        with st.container(border=True):
            # Arriba de todo: el estado y el botón Guardar, para no tener que bajar con el scroll.
            st.markdown(f"### {it['estado']}")
            datos = datos_de(it)
            faltan = faltantes(datos)
            previo = it.get("duplicado")
            if previo and (previo.get("gtin"), previo.get("serie")) != (datos["gtin"], datos["serie"]):
                it.pop("duplicado")  # se corrigió el GTIN o la serie: ya no es el mismo envase
                previo = None
            if previo:
                st.warning(
                    f"⚠️ **Este envase ya fue cargado.** Lo registró **{previo.get('usuario') or 'alguien'}** "
                    f"el {previo.get('fecha_registro') or '(fecha desconocida)'} "
                    f"(lote {previo.get('lote') or '-'}, vence {previo.get('vencimiento') or '-'}). ¿Qué querés hacer?"
                )
                b1, b2 = st.columns(2)
                if b1.button("🔁 Reemplazar con estos datos", key=f"reemplazar_{it['id']}", use_container_width=True):
                    registro.reemplazar(fila_de(it))
                    cerrar_tarjeta(it, ("success", "🔁 Se reemplazó el registro anterior con los datos nuevos. Ya podés cargar la próxima foto."))
                    st.rerun()
                if b2.button("🗑️ Descartar y dejar el anterior", key=f"descartar_{it['id']}", use_container_width=True):
                    cerrar_tarjeta(it, ("info", "Se descartó esta lectura. El registro anterior quedó como estaba."))
                    st.rerun()
            else:
                etiqueta = "💾 Guardar" if it["estado"] == ESTADO_OK else "💾 Coincide con el envase: guardar"
                if st.button(etiqueta, type="primary", key=f"guardar_{it['id']}", disabled=bool(faltan), use_container_width=True):
                    guardar_item(it)
                    st.rerun()
                if faltan:
                    st.caption("Para guardar: " + " y ".join(faltan) + ". Corregilo abajo o sacá otra foto.")

            if it["estado"] == ESTADO_OTRA_FOTO:
                st.error(
                    "**No estoy seguro de haber leído bien.** " + " · ".join(it["motivos"])
                    + ". Sacá otra foto más de cerca y con buena luz, o corregí los datos a mano mirando el envase."
                )
                otra_foto = st.file_uploader(
                    "Otra foto", type=["jpg", "jpeg", "png", "webp"], key=f"otra_{it['id']}", label_visibility="collapsed"
                )
                if otra_foto is not None:
                    reemplazar(it["id"], otra_foto.getvalue(), otra_foto.name)
                    st.rerun()
            elif it["motivos"]:
                st.warning(" · ".join(it["motivos"]))

            # Debajo: los datos leídos (se pueden corregir) y la foto, más chica.
            for (campo, titulo), col in zip(CAMPOS, st.columns(len(CAMPOS))):
                col.text_input(titulo, value=lec.get(campo, ""), key=f"{campo}_{it['id']}")
            st.image(it["foto"], caption=it["archivo_foto"], width=320)
            st.caption(f"Leído desde: {lec['fuente']} · Foto del {it['fecha_foto']} ({it['origen_fecha_foto']})")

    if len(items) > 1 and st.button("🧹 Descartar todo y empezar de nuevo"):
        st.session_state["items"] = []
        st.session_state["ronda"] += 1
        st.session_state["leidas"] = set()
        st.rerun()

def borrar_con_doble_confirmacion(clave: str, etiqueta: str, accion) -> None:
    """Botón de borrar que pregunta dos veces antes de hacerlo (por si se tocó sin querer).
    Paso 0: botón "Eliminar…" · Paso 1: "¿Seguro?" · Paso 2: "Última confirmación" → borra."""
    paso = st.session_state.get(f"paso_{clave}", 0)

    def ir_a(n):
        st.session_state[f"paso_{clave}"] = n
        st.rerun()

    if paso == 0:
        if st.button(etiqueta, key=f"{clave}_0"):
            ir_a(1)
    elif paso == 1:
        st.warning("**¿Seguro que querés eliminar?** (pregunta 1 de 2)")
        c1, c2 = st.columns(2)
        if c1.button("Sí, seguir", key=f"{clave}_1_si", use_container_width=True):
            ir_a(2)
        if c2.button("Cancelar", key=f"{clave}_1_no", use_container_width=True):
            ir_a(0)
    else:
        st.error("**Última confirmación:** se borra para siempre y **no se puede deshacer**. ¿Eliminar? (pregunta 2 de 2)")
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Sí, eliminar", key=f"{clave}_2_si", type="primary", use_container_width=True):
            st.session_state[f"paso_{clave}"] = 0
            accion()
            st.rerun()
        if c2.button("Cancelar", key=f"{clave}_2_no", use_container_width=True):
            ir_a(0)


# ------------------------------------------------------------ función 2: registros

def filtrar(datos, clave: str):
    """Filtros comunes: por quién lo subió (vacío = todos) y buscador. Lo más nuevo arriba."""
    c1, c2 = st.columns(2)
    quienes = c1.multiselect(
        "Quién lo subió", sorted(u for u in datos["usuario"].unique() if u), key=f"filtro_{clave}",
        placeholder="Todos",
    )
    buscar = c2.text_input("Buscar (GTIN, serie o lote)", key=f"buscar_{clave}")
    vista = datos.iloc[::-1]
    if quienes:
        vista = vista[vista["usuario"].isin(quienes)]
    if buscar:
        b = buscar.strip().upper()
        vista = vista[vista[["gtin", "serie", "lote"]].apply(lambda col: col.str.upper().str.contains(b, regex=False)).any(axis=1)]
    return vista


def descargas(tabla, nombre: str, clave: str) -> None:
    """Botón para bajar la tabla en Excel. El título y el nombre del archivo llevan
    el rango de fechas de lo que se está mostrando (según "Guardado el")."""
    rango = registro.rango_de_fechas(tabla["Guardado el"]) if "Guardado el" in tabla else ""
    titulo = f"{nombre} {rango}".strip()
    archivo = titulo.replace("/", "-")  # en un nombre de archivo no puede ir "/"
    st.download_button(
        "⬇️ Descargar Excel", registro.a_excel(tabla, titulo), f"{archivo}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"xlsx_{clave}",
    )


datos = registro.leer() if puede_ver_registros else registro.leer().iloc[0:0]
pendientes = datos[datos["revisado_por"] == ""]
revisados = datos[datos["revisado_por"] != ""]

if puede_ver_registros:
    with tab_pendientes:
        st.caption("Lo que cargó todo el equipo y todavía no revisó una farmacéutica. Lo más nuevo arriba.")
        if pendientes.empty:
            st.info("No hay registros pendientes de revisión. 🎉")
        else:
            vista = filtrar(pendientes, "pend")
            st.write(f"{len(vista)} registro(s) pendiente(s).")
            tabla = vista[list(COLUMNAS_REGISTRO)].rename(columns=COLUMNAS_REGISTRO)
            st.write(f"**{usuario['nombre']}**, tildá los que ya viste y confirmaste, y tocá el botón para pasarlos a **Revisados**.")
            # "Seleccionar todo" tilda todos los que se ven ahora (respeta el filtro y la búsqueda).
            todos = st.checkbox(f"Seleccionar todo ({len(tabla)})", key="todos_pend")
            tabla.insert(0, "Revisado", todos)
            editada = st.data_editor(
                tabla,
                hide_index=True,
                use_container_width=True,
                disabled=[c for c in tabla.columns if c != "Revisado"],
                column_config={"Revisado": st.column_config.CheckboxColumn("✔ Revisado", help="Visto y guardado por la farmacéutica")},
                key=f"editor_pendientes_{int(todos)}",  # al cambiar "Seleccionar todo" se arma de nuevo
            )
            tildados = editada[editada["Revisado"]]
            if st.button(
                f"✅ Pasar {len(tildados)} a Revisados", type="primary", disabled=tildados.empty, key="pasar_revisados"
            ):
                n = registro.marcar_revisados(list(zip(tildados["GTIN"], tildados["Serie"])), usuario["nombre"])
                for clave in ("editor_pendientes_0", "editor_pendientes_1", "todos_pend"):
                    st.session_state.pop(clave, None)
                st.toast(f"{n} registro(s) pasaron a Revisados ✅")
                st.rerun()
            descargas(tabla.drop(columns="Revisado"), "Listado de registros sin revisar", "pend")

    with tab_revisados:
        st.caption("Registros que una farmacéutica ya vio y dio por buenos.")
        if revisados.empty:
            st.info("No hay registros revisados sin archivar.")
        else:
            vista = filtrar(revisados, "rev")
            st.write(f"{len(vista)} registro(s) revisado(s).")
            columnas = {**COLUMNAS_REGISTRO, "revisado_por": "Revisado por", "revisado_el": "Revisado el"}
            tabla = vista[list(columnas)].rename(columns=columnas)
            st.dataframe(tabla, hide_index=True, use_container_width=True)
            descargas(tabla, "Listado de revisados", "rev")
            with st.expander("¿Tildaste uno por error? Volverlo a pendientes"):
                opciones = {f"{r.gtin} · serie {r.serie} · revisado por {r.revisado_por}": (r.gtin, r.serie) for r in vista.itertuples()}
                elegido = st.selectbox("Registro", list(opciones), key="volver_pend")
                if st.button("↩️ Volver a pendientes", key="btn_volver"):
                    registro.desmarcar_revisado(*opciones[elegido])
                    st.rerun()

            # Archivar por mes: Revisados queda limpio y cada mes se puede ver y bajar abajo.
            with st.expander(f"📦 Archivar por mes los {len(revisados)} revisados"):
                st.write(
                    "Pasa **todos** los revisados a un archivo de su mes (según la fecha en que se guardaron) "
                    "y los saca de esta lista. No se pierde nada: cada mes se puede ver y bajar en Excel acá abajo."
                )
                if st.button(f"📦 Archivar {len(revisados)} revisados", key="btn_archivar"):
                    cuantos = registro.archivar_revisados()
                    detalle = ", ".join(f"{n} en {registro.nombre_del_mes(m)}" for m, n in cuantos.items())
                    st.session_state["aviso_rev"] = ("success", f"📦 Archivados: {detalle}.")
                    st.rerun()

            # Eliminar todos: no se puede deshacer, por eso pregunta dos veces.
            with st.expander(f"🗑️ Eliminar los {len(revisados)} revisados"):
                st.warning(
                    "Esto **borra para siempre** todos los revisados (no solo los filtrados) y **no se puede deshacer**. "
                    "Si los querés guardar, mejor usá **Archivar por mes**. Los pendientes y los meses archivados no se tocan."
                )

                def eliminar_todos():
                    n = registro.eliminar_revisados()
                    st.session_state["aviso_rev"] = ("info", f"🗑️ Se eliminaron {n} revisados.")

                borrar_con_doble_confirmacion("eliminar_rev", f"🗑️ Eliminar {len(revisados)} revisados", eliminar_todos)

        aviso = st.session_state.pop("aviso_rev", None)
        if aviso:
            getattr(st, aviso[0])(aviso[1])

        meses = registro.meses_archivados()
        if meses:
            st.subheader("📦 Meses archivados")
            cerrados = [registro.nombre_del_mes(m) for m in meses if registro.mes_cerrado(m)]
            if cerrados:
                st.info(
                    f"Ya terminó: **{', '.join(cerrados)}**. Si ya bajaste el Excel, podés eliminar ese archivo: "
                    "elegí el mes acá abajo."
                )
            mes = st.selectbox("Mes", meses, format_func=lambda m: registro.nombre_del_mes(m).capitalize(), key="mes_archivo")
            del_mes = registro.leer_mes(mes)
            st.write(f"{len(del_mes)} registro(s) en {registro.nombre_del_mes(mes)}.")
            columnas = {**COLUMNAS_REGISTRO, "revisado_por": "Revisado por", "revisado_el": "Revisado el"}
            tabla_mes = del_mes.iloc[::-1][list(columnas)].rename(columns=columnas)
            st.dataframe(tabla_mes, hide_index=True, use_container_width=True)
            descargas(tabla_mes, f"Listado de revisados de {registro.nombre_del_mes(mes)}", f"mes_{mes}")

            # Cuando un mes ya terminó, se puede eliminar su archivo (después de bajar el Excel).
            if registro.mes_cerrado(mes):
                with st.expander(f"🗑️ Eliminar el archivo de {registro.nombre_del_mes(mes)}"):
                    st.warning(
                        f"Esto **borra para siempre** los {len(del_mes)} registro(s) de {registro.nombre_del_mes(mes)} "
                        "y **no se puede deshacer**. Antes bajá el Excel con el botón de arriba."
                    )

                    def eliminar_este_mes(mes=mes):
                        n = registro.eliminar_mes(mes)
                        st.session_state.pop("mes_archivo", None)
                        st.session_state["aviso_rev"] = ("info", f"🗑️ Se eliminó {registro.nombre_del_mes(mes)} ({n} registros).")

                    borrar_con_doble_confirmacion(
                        f"eliminar_mes_{mes}", f"🗑️ Eliminar {registro.nombre_del_mes(mes)}", eliminar_este_mes
                    )
            else:
                st.caption("Este mes todavía no terminó. Cuando empiece el mes siguiente, vas a poder eliminar su archivo.")

# ------------------------------------------------------------ consultas rápidas del mostrador (sin IA)
# Busca en consultas/Base_Consultas_Mostrador_Mitre.md. Solo muestra lo que está escrito ahí;
# el horario se actualiza cada viernes reemplazando ese archivo (ver README).
@st.cache_data(show_spinner=False)
def base_de_consultas(_modificado: float):
    return consultas.leer()


def mostrar_horario_de_hoy(base, hoy) -> None:
    hoy_trabajan = consultas.quien_trabaja(base, hoy)
    if hoy_trabajan is None:
        st.info(f"🕒 {consultas.SIN_HORARIO}")
        return
    columna, gente = hoy_trabajan
    st.markdown(f"**🕒 ¿Quién trabaja hoy? ({columna})**")
    st.markdown("\n".join(f"- **{p}** ({puesto}): {h}" for p, puesto, h in gente))


@st.cache_data(show_spinner=False)
def ofertas_otc(_modificado: float):
    return ofertas.leer() if ofertas.ARCHIVO.exists() else []


@st.cache_data(show_spinner=False)
def mapa_de_cajones(_modificado: float):
    return cajones.leer() if cajones.ARCHIVO.exists() else []


OFERTAS_ETIQUETA = "💊 Ofertas OTC"
CAJONES_ETIQUETA = "🗄️ Cajones"


def mostrar_cajones(encontrados) -> None:
    st.markdown("<small>¿En qué cajón está?</small>", unsafe_allow_html=True)
    st.markdown("  \n".join(cajones.texto(it) for it in encontrados))
    st.divider()


def mostrar_ofertas(lista, hoy) -> None:
    for o in lista:
        st.markdown(ofertas.ficha(o, hoy))
        st.divider()


def responder_codigo(codigo: str, base, lista, hoy) -> None:
    """Qué hay cargado para un código de barras: oferta OTC o dato de la base (ej. PICC)."""
    encontradas = ofertas.por_codigo(lista, codigo)
    if encontradas:
        mostrar_ofertas(encontradas, hoy)
        primera = encontradas[0].producto.split()[0]
        en_cajon = cajones.buscar(items_cajones, primera)
        if en_cajon:
            st.caption(f"Puede estar en estos cajones ({cajones.VERIFICAR}):")
            mostrar_cajones(en_cajon)
        return
    datos = consultas.buscar(base, codigo, hoy)["datos"]
    if datos:
        for titulo, texto in datos:
            st.markdown(f"<small>{titulo}</small>", unsafe_allow_html=True)
            st.markdown(texto)
        return
    st.info(f"🔎 Código {codigo}: {ofertas.NO_CARGADO}")


if consultas.ARCHIVO.exists():
    with st.expander("💬 Consultas rápidas del mostrador"):
        base = base_de_consultas(consultas.ARCHIVO.stat().st_mtime)
        lista_ofertas = ofertas_otc(ofertas.ARCHIVO.stat().st_mtime if ofertas.ARCHIVO.exists() else 0)
        items_cajones = mapa_de_cajones(cajones.ARCHIVO.stat().st_mtime if cajones.ARCHIVO.exists() else 0)
        hoy = consultas.hoy_argentina()

        # Lector de código de barras: foto del producto -> oferta, precio o dato cargado.
        st.markdown("**📷 Leer código de barras**")
        st.session_state.setdefault("ronda_codigo", 0)
        foto_codigo = st.file_uploader(
            "Foto del código de barras", type=TIPOS_FOTO, key=f"foto_codigo_{st.session_state['ronda_codigo']}",
            label_visibility="collapsed",
        )
        if foto_codigo is not None:
            try:
                codigos = leer_codigos_de_producto(abrir(foto_codigo))
            except Exception:
                codigos = []
            if not codigos:
                st.warning("No se pudo leer el código de barras. Sacá la foto de cerca, derecha y con buena luz, "
                           "o escribí el número en el buscador.")
            for codigo in codigos:
                responder_codigo(codigo, base, lista_ofertas, hoy)
            if st.button("🧹 Limpiar foto", key="limpiar_codigo"):
                st.session_state["ronda_codigo"] += 1
                st.rerun()

        st.markdown("**🔎 Buscar**")
        st.caption("Escribí una palabra o el número del código (ej.: OSDE, Galeno, Tafirol, ibuprofeno, Ctrl+V, "
                   "quién trabaja hoy) o tocá una categoría. Para los cajones sirve aunque esté mal escrito.")
        pregunta = st.text_input("Buscar", key="consulta_txt", label_visibility="collapsed",
                                 placeholder="🔎 Buscar: obra social, producto, promo, atajo...")
        st.markdown(
            "<style>.st-key-categorias [data-testid='stButtonGroup'] button p { font-size: .95rem !important; }"
            ".st-key-categorias [data-testid='stButtonGroup'] button { min-height: 2.4rem; padding: .3rem .5rem !important; }</style>",
            unsafe_allow_html=True,
        )
        etiquetas = [s.etiqueta for s in base.secciones]
        if lista_ofertas:
            etiquetas.insert(next((i + 1 for i, s in enumerate(base.secciones) if s.numero == "7"), len(etiquetas)),
                             OFERTAS_ETIQUETA)
        if items_cajones:
            etiquetas.insert(next((i + 1 for i, e in enumerate(etiquetas) if e.endswith("Mostrador")), len(etiquetas)),
                             CAJONES_ETIQUETA)
        with st.container(key="categorias"):
            categoria = st.pills("Categorías", etiquetas, key="consulta_cat", label_visibility="collapsed")
        if pregunta.strip():
            r = consultas.buscar(base, pregunta, hoy)
            if r["salud"]:
                st.warning(f"👩‍⚕️ {consultas.SALUD}")
            else:
                encontradas = ofertas.buscar(lista_ofertas, pregunta)
                en_cajon = cajones.buscar(items_cajones, pregunta)
                if en_cajon:
                    mostrar_cajones(en_cajon)
                    # Ofertas del mismo producto que está en el cajón (sin repetir las ya encontradas).
                    ids = {o.codigo for o in encontradas}
                    for it in en_cajon:
                        for o in cajones.ofertas_del_item(it, lista_ofertas, hoy, pregunta):
                            if o.codigo not in ids:
                                encontradas.append(o)
                                ids.add(o.codigo)
                if r["hoy"]:
                    mostrar_horario_de_hoy(base, hoy)
                if r["sin_horario"]:
                    st.info(f"🕒 {consultas.SIN_HORARIO}")
                if encontradas:
                    st.markdown("<small>Ofertas OTC</small>", unsafe_allow_html=True)
                    if en_cajon:
                        st.caption(f"🏷️ Hay ofertas de este producto: {cajones.VERIFICAR}.")
                    mostrar_ofertas(encontradas, hoy)
                for titulo, texto in r["datos"]:
                    st.markdown(f"<small>{titulo}</small>", unsafe_allow_html=True)
                    st.markdown(texto)
                    st.divider()
                if not (r["datos"] or r["hoy"] or r["sin_horario"] or encontradas or en_cajon):
                    if re.fullmatch(r"\s*\d{8,14}\s*", pregunta):
                        st.info(f"🔎 {ofertas.NO_CARGADO}")
                    else:
                        st.info(consultas.SIN_DATO)
        elif categoria == CAJONES_ETIQUETA:
            for cajon, contenido in cajones.mapa(items_cajones).items():
                st.markdown(f"**🗄️ {cajon}**  \n" + " · ".join(
                    it.nombre + (" ⚠️" if it.a_confirmar else "") for it in contenido))
            st.caption("⚠️ = nombre a confirmar (revisar la caja).")
        elif categoria == OFERTAS_ETIQUETA:
            vigentes = [o for o in lista_ofertas if o.vigencia(hoy) != "vencida"]
            st.markdown(f"**{len(lista_ofertas)} productos en oferta** · sin precio cargado: "
                        f"{sum(1 for o in lista_ofertas if o.precio is None)}")
            if len(vigentes) < len(lista_ofertas):
                st.warning(f"❌ {len(lista_ofertas) - len(vigentes)} ofertas ya están vencidas.")
            st.dataframe(
                [{
                    "Producto": f"{o.producto} {o.presentacion}".strip(),
                    "Oferta": o.texto_oferta(),
                    "Hasta": (o.hasta.strftime("%d/%m/%Y") if o.hasta else "—") + ("" if o.vigencia(hoy) == "vigente" else f" ({o.vigencia(hoy)})"),
                    "Paga el cliente": ofertas.pesos(o.paga_el_cliente()) if o.precio is not None else ofertas.SIN_PRECIO,
                    "Código": o.codigo,
                } for o in lista_ofertas],
                hide_index=True, use_container_width=True,
            )
        elif categoria:
            seccion = next(s for s in base.secciones if s.etiqueta == categoria)
            if seccion.numero == "2":
                mostrar_horario_de_hoy(base, hoy)
            contenido = consultas.marcar_promos(seccion.contenido, hoy)
            if seccion.numero == "2" and not consultas.horario_vigente(base, hoy):
                # Fuera del período cargado solo se muestran las reglas fijas (2.2).
                contenido = contenido[contenido.find("### 2.2"):] if "### 2.2" in contenido else ""
            st.markdown(contenido)
        st.caption(f"Lo marcado con ⚠️ está {consultas.A_CONFIRMAR}. "
                   "Las consultas de salud (dosis, para qué sirve) las responde la farmacéutica.")

# ------------------------------------------------------------ notas u observaciones (para mejorar la app)
# Cualquiera deja una nota. Quien tiene "ve_notas" en usuarios.json (Omar) ve todas y las borra
# a medida que aplica los cambios. Los demás ven las suyas hasta que cierran la app.
st.session_state.setdefault("mis_notas", [])
if usuario:
    with st.expander("📝 Nota u observación"):
        st.caption("¿Algo para cambiar, arreglar o agregar a la app? Escribilo acá y le llega a Omar.")
        texto_nota = st.text_area("Tu nota", key="texto_nota", label_visibility="collapsed",
                                  placeholder="Ej.: que el botón de guardar sea más grande")

        def enviar_nota():
            texto = st.session_state.get("texto_nota", "").strip()
            if texto:
                st.session_state["mis_notas"].append(registro.guardar_nota(usuario["nombre"], texto))
                st.session_state["texto_nota"] = ""
                st.session_state["nota_enviada"] = True

        st.button("📨 Enviar nota", key="btn_nota", on_click=enviar_nota, disabled=not texto_nota.strip())
        if st.session_state.pop("nota_enviada", False):
            st.success("¡Gracias! La nota quedó guardada.")
        if st.session_state["mis_notas"] and not usuario.get("ve_notas"):
            st.write("**Tus notas de hoy:**")
            for n in st.session_state["mis_notas"]:
                st.markdown(f"- {n['nota']} _({n['fecha']})_")

        # Clave opcional para ver las notas (clave_notas en Secrets). Sin clave configurada, Omar las ve directo.
        clave_notas = str(SECRETOS.get("clave_notas", "") or "")
        puede_ver_notas = usuario.get("ve_notas") and (
            not clave_notas or st.session_state.get("clave_notas_ok")
        )
        if usuario.get("ve_notas") and not puede_ver_notas:
            escrita = st.text_input("Clave para ver las notas", type="password", key="clave_notas_txt")
            if escrita and escrita == clave_notas:
                st.session_state["clave_notas_ok"] = True
                st.rerun()
            elif escrita:
                st.error("Clave incorrecta.")

        if puede_ver_notas:
            notas = registro.leer_notas()
            st.divider()
            st.write(f"**Notas del equipo ({len(notas)})**" if len(notas) else "**No hay notas del equipo.**")
            for n in notas.itertuples():
                c1, c2 = st.columns([5, 2])
                c1.markdown(f"**{n.usuario}** · {n.fecha}  \n{n.nota}")
                if c2.button("✅ Listo, borrar", key=f"borrar_nota_{n.id}", use_container_width=True):
                    registro.borrar_nota(n.id)
                    st.rerun()

# ------------------------------------------------------------ ayuda (preguntas frecuentes, sin IA)
AYUDA = """
**📷 ¿Cómo cargo un envase?**
Tocá tu nombre arriba. Después tocá **Sacar foto** (abre la cámara) o **Galería** (elegís una foto que ya tenés). La app la lee sola, no hace falta tocar nada más.

**✅ ⚠️ ❌ ¿Qué significan?**
- **✅ Lista**: se leyó del cuadradito (DataMatrix) y es exacta. Se guarda sola.
- **⚠️ Revisar**: se leyó del texto impreso. Puede tener algún error, así que compará con el envase y tocá **Guardar**.
- **❌ Sacar otra foto**: no se pudo leer bien. Sacá otra foto más de cerca y con buena luz.

**📸 La foto no se lee, ¿qué hago?**
Sacá otra: un solo envase, de cerca, con buena luz, sin reflejos y **sin marcar ni tapar** el cuadradito.

**🔁 Me avisa que ya estaba cargado.**
Ese envase (mismo código y serie) ya se había registrado. Elegí **Reemplazar** (si querés dejar los datos nuevos) o **Descartar** (si dejás el anterior).

**👀 ¿Dónde veo lo cargado? (solo farmacéuticas)**
En **Registros** está lo que cargó el equipo y falta revisar. **Seleccionar todo** tilda todos, y **Pasar a Revisados** mueve los tildados a la pestaña **Revisados**.

**📦 Archivar por mes (Revisados)**
Guarda todos los revisados en un archivo de su mes y limpia la lista. No se pierde nada: cada mes se puede ver y bajar en **Excel** abajo, en **Meses archivados**.

**🗑️ Eliminar**
Borra para siempre y no se puede deshacer, por eso pregunta dos veces. Si querés conservar los datos, usá **Archivar por mes** en vez de eliminar. Bajá el Excel antes de borrar.

**⬇️ Descargar Excel**
En Registros y Revisados, el botón **Descargar Excel** baja la lista con el GTIN y la serie completos.
"""

with st.expander("❓ Ayuda — preguntas frecuentes"):
    st.markdown(AYUDA)

# Soporte: abre el sistema de tickets del Área TI en otra pestaña.
st.link_button("🛠️ Soporte Área TI", "https://area-t-i-tickets.vercel.app/", use_container_width=True)

# ------------------------------------------------------------ pie de página (marca de agua)
# Leyenda al final de la app, en gris y letra chica, visible en todas las pantallas.
st.markdown(
    """<div style="text-align:center; color:#9a9a9a; font-size:0.8rem; margin-top:2.5rem; padding-top:1rem; border-top:1px solid rgba(49,51,63,0.1);">
    Diseño y desarrollo: Omar Eduardo Giménez · Con la ayuda de Claude Code
    </div>""",
    unsafe_allow_html=True,
)
