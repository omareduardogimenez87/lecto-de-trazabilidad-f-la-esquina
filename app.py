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
import hashlib
import io
import json
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from lector import registro
from lector.calidad import ESTADO_OK, ESTADO_OTRA_FOTO, estado, medir
from lector.gs1 import gtin_es_valido
from lector.imagen import abrir, analizar, fecha_de_la_foto, ocr_disponible

CONFIG = json.loads((Path(__file__).parent / "usuarios.json").read_text(encoding="utf-8"))
USUARIOS = {u["nombre"]: u for u in CONFIG["usuarios"]}
SUCURSAL = CONFIG.get("sucursal", "")
CAMPOS = [("gtin", "GTIN (01)"), ("serie", "Serie (21)"), ("lote", "Lote (10)"), ("vencimiento", "Vencimiento"), ("elaboracion", "Elaboración")]
EN_MAYUSCULAS = ("gtin", "serie", "lote")
# Columnas que se ven en Registros y salen en el Excel, con su título.
COLUMNAS_REGISTRO = {
    "gtin": "GTIN",
    "serie": "Serie",
    "lote": "Lote",
    "vencimiento": "Vencimiento",
    "usuario": "Envió",
    "fecha_foto": "Fecha de la foto",
    "estado": "Estado",
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
    [data-testid="stButtonGroup"] [role="radiogroup"] { gap: .75rem !important; }
    [data-testid="stButtonGroup"] button { padding: .55rem 1.3rem !important; min-height: 3rem; }
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
nombre = st.pills("¿Quién sos? Tocá tu nombre", list(USUARIOS), selection_mode="single", key="usuario")
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
        st.session_state["avisos"].append(("success", f"✅ Se guardaron {guardadas} foto(s)."))
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
    tab_leer, tab_pendientes, tab_revisados = st.tabs(["📷 1. Leer fotos", "📄 2. Registros", "✅ 3. Revisados"])
else:
    (tab_leer,) = st.tabs(["📷 1. Leer fotos"])
    tab_pendientes = tab_revisados = None

# ------------------------------------------------------------ función 1: leer
with tab_leer:
    # Mensajes del último guardado (se muestran una vez y se borran).
    for tipo, texto in st.session_state["avisos"]:
        getattr(st, tipo)(texto)
    st.session_state["avisos"] = []

    if not usuario:
        st.info("☝️ Primero tocá tu nombre.")
    else:
        st.write(
            "Sacá una foto o elegila de la galería. Que se vea el **cuadradito (DataMatrix)** y los datos "
            "impresos al lado, de cerca, con buena luz y sin reflejos. **Se lee sola al cargarla.**"
        )
        fotos = botones_de_foto(st.session_state["ronda"])
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
            # En Registros no se muestra "Estado" (pedido de Edu, 22/11/2026). Sigue guardado en el registro.
            columnas = {k: v for k, v in COLUMNAS_REGISTRO.items() if k != "estado"}
            tabla = vista[list(columnas)].rename(columns=columnas)
            tabla.insert(0, "Revisado", False)
            st.write(f"**{usuario['nombre']}**, tildá los que ya viste y confirmaste, y tocá el botón para pasarlos a **Revisados**.")
            editada = st.data_editor(
                tabla,
                hide_index=True,
                use_container_width=True,
                disabled=[c for c in tabla.columns if c != "Revisado"],
                column_config={"Revisado": st.column_config.CheckboxColumn("✔ Revisado", help="Visto y guardado por la farmacéutica")},
                key="editor_pendientes",
            )
            tildados = editada[editada["Revisado"]]
            if st.button(
                f"✅ Pasar {len(tildados)} a Revisados", type="primary", disabled=tildados.empty, key="pasar_revisados"
            ):
                n = registro.marcar_revisados(list(zip(tildados["GTIN"], tildados["Serie"])), usuario["nombre"])
                st.session_state.pop("editor_pendientes", None)
                st.toast(f"{n} registro(s) pasaron a Revisados ✅")
                st.rerun()
            descargas(tabla.drop(columns="Revisado"), "Listado de registros sin revisar", "pend")

    with tab_revisados:
        st.caption("Registros que una farmacéutica ya vio y dio por buenos.")
        if revisados.empty:
            st.info("Todavía no hay registros revisados.")
        else:
            vista = filtrar(revisados, "rev")
            st.write(f"{len(vista)} registro(s) revisado(s).")
            columnas = {**COLUMNAS_REGISTRO, "revisado_por": "Revisado por", "revisado_el": "Revisado el"}
            tabla = vista[list(columnas)].rename(columns=columnas)
            st.dataframe(tabla, hide_index=True, use_container_width=True)
            descargas(tabla, "Listado de revisados", "rev")
            if True:
                with st.expander("¿Tildaste uno por error? Volverlo a pendientes"):
                    opciones = {f"{r.gtin} · serie {r.serie} · revisado por {r.revisado_por}": (r.gtin, r.serie) for r in vista.itertuples()}
                    elegido = st.selectbox("Registro", list(opciones), key="volver_pend")
                    if st.button("↩️ Volver a pendientes", key="btn_volver"):
                        registro.desmarcar_revisado(*opciones[elegido])
                        st.rerun()
