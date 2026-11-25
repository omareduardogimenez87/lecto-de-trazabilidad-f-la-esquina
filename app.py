"""App Trazabilidad - Farmacia La Esquina.

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

from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

from lector import ayuda, cajones, catalogo, consultas, matriculas, ofertas, padron, precios, registro, vademecum

# Streamlit Cloud a veces deja cargada la versión vieja de estos módulos después de un merge
# (y aparece un AttributeError hasta hacer "Reboot app"). Si el archivo cambió, se vuelve a cargar.
import importlib

for _modulo in (consultas, ofertas, precios, cajones, catalogo, ayuda, vademecum, padron, matriculas):
    _cambio = Path(_modulo.__file__).stat().st_mtime
    if getattr(_modulo, "_version_cargada", None) != _cambio:
        importlib.reload(_modulo)
        _modulo._version_cargada = _cambio
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
ICONO = IMAGENES / "icono.png"  # la cruz de Farmacia La Esquina (logo del título)
ICONO_APP = IMAGENES / "icono_app.png"  # cruz pixelada con ojitos: ícono de la pestaña
ICONO_CELULAR = IMAGENES / "icono_celular.png"  # mismo ícono con fondo blanco, para el acceso directo del celular
MARCA_DE_AGUA = IMAGENES / "marca_de_agua.png"  # logo "la esquina", casi transparente


def en_base64(archivo: Path) -> str:
    return base64.b64encode(archivo.read_bytes()).decode()


st.set_page_config(
    page_title="App Trazabilidad",
    page_icon=str(ICONO_APP) if ICONO_APP.exists() else (str(ICONO) if ICONO.exists() else "💊"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Fondo de la app: degradado lima-crema-lila (colores de la marca, más cálido que el blanco).
st.markdown(
    """<style>
    [data-testid="stApp"] { background: linear-gradient(180deg, #F8FBEA 0%, #FBF8EE 45%, #F4EEFA 100%) !important;
                            background-attachment: fixed !important; }
    [data-testid="stHeader"] { background: transparent !important; }
    </style>""",
    unsafe_allow_html=True,
)

# Ícono para "Agregar a la pantalla de inicio" del celular (Streamlit no trae opción para esto).
# En Streamlit Cloud la app corre dentro de otra página (la de afuera trae el ícono rojo de
# Streamlit), así que se cambia el ícono y el manifest en las dos: la de la app y la de afuera.
if ICONO_CELULAR.exists():
    components.html(
        f"""<script>
        const DATA = "data:image/png;base64,{en_base64(ICONO_CELULAR)}";
        const app = window.parent;
        const icono = n => new URL("app/static/icono_" + n + ".png", app.location.href).href;
        function aplicar(w) {{
            const doc = w.document;
            for (const rel of ["apple-touch-icon", "icon", "shortcut icon"]) {{
                doc.querySelectorAll(`link[rel="${{rel}}"]:not([data-celular])`).forEach(l => l.remove());
                let link = doc.querySelector(`link[rel="${{rel}}"][data-celular]`);
                if (!link) {{ link = doc.createElement("link"); link.rel = rel; link.dataset.celular = "1"; doc.head.appendChild(link); }}
                link.href = rel === "apple-touch-icon" ? icono(512) : DATA;
            }}
            for (const name of ["apple-mobile-web-app-title", "application-name"]) {{
                let meta = doc.querySelector(`meta[name="${{name}}"]`);
                if (!meta) {{ meta = doc.createElement("meta"); meta.name = name; doc.head.appendChild(meta); }}
                meta.content = "App Trazabilidad";
            }}
            // Manifest propio (Android usa este para el ícono del acceso directo).
            if (!doc.querySelector('link[rel="manifest"][data-celular]')) {{
                const inicio = w.location.origin + w.location.pathname;
                const manifest = {{
                    name: "App Trazabilidad", short_name: "App Trazabilidad",
                    start_url: inicio, scope: w.location.origin + "/", display: "standalone",
                    background_color: "#F8FBEA", theme_color: "#8B5A9E",
                    icons: [192, 512].map(n => ({{ src: icono(n), sizes: n + "x" + n, type: "image/png", purpose: "any" }})),
                }};
                const url = w.URL.createObjectURL(new w.Blob([JSON.stringify(manifest)], {{ type: "application/manifest+json" }}));
                doc.querySelectorAll('link[rel="manifest"]').forEach(l => l.remove());
                const link = doc.createElement("link"); link.rel = "manifest"; link.href = url; link.dataset.celular = "1";
                doc.head.appendChild(link);
            }}
        }}
        aplicar(app);
        try {{ if (window.top !== app) aplicar(window.top); }} catch (e) {{ /* la página de afuera no deja tocarla */ }}
        </script>""",
        height=0,
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
        App Trazabilidad</h1>""",
        unsafe_allow_html=True,
    )
else:
    st.title("💊 App Trazabilidad")
st.caption(f"Farmacia La Esquina · Sucursal {SUCURSAL}")



def secretos() -> dict:
    """Lee la configuración secreta de la nube (.streamlit/secrets.toml o el panel de
    Streamlit Cloud). En la PC normalmente no existe, y entonces devuelve {}."""
    try:
        return st.secrets.to_dict()
    except Exception:
        return {}


# Botón "Escanear código o producto" del Asistente. Apagado hasta tener los códigos cargados;
# se prende en Secrets con  escaneo_activo = true  (el código del lector queda intacto).
ESCANEO_ACTIVO = str(secretos().get("escaneo_activo", False)).strip().lower() in ("true", "1", "si", "sí")

AVISO_ISSPSE = ("🧾 **ISSPSE (indicación de Germán, ROC):** en **mostrador** imprimí la **validación**; en **caja/perfumería**, "
                "una **copia de la factura**. Adjuntala con las **recetas diarias** para auditoría.")

# Contraseña para entrar a la app (pedido de Edu, 24/11/2026). Se activa poniendo en Secrets
#   clave_app = "la-clave"
# Sin esa línea la app abre como siempre. Se pide una vez por sesión del navegador.
CLAVE_APP = str(secretos().get("clave_app", "")).strip()
if CLAVE_APP and not st.session_state.get("entro"):
    with st.form("form_clave", border=True):
        st.markdown("🔒 **Ingresá la contraseña de la app**")
        escrita = st.text_input("Contraseña", type="password", key="clave_ingresada")
        if st.form_submit_button("Entrar", type="primary", use_container_width=True):
            import hmac as _hmac

            if _hmac.compare_digest(escrita.strip(), CLAVE_APP):
                st.session_state["entro"] = True
                st.rerun()
            st.error("Contraseña incorrecta.")
    st.stop()


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
/* "Sacar de nuevo" en las tarjetas ❌: mismo estilo que "Sacar foto", del alto de un botón común. */
[class*="st-key-recamara_"] [data-testid="stFileUploaderDropzoneInstructions"],
[class*="st-key-recamara_"] [data-testid="stFileChip"] { display: none !important; }
[class*="st-key-recamara_"] section { padding: 0; background: transparent; border: none; display: block; }
[class*="st-key-recamara_"] section > span, [class*="st-key-recamara_"] section button { display: block; width: 100%; max-width: none; }
[class*="st-key-recamara_"] section button {
  min-height: 2.5rem; font-size: 0 !important; border-radius: 0.5rem; background: #c62f3f; color: white; border: 1px solid #c62f3f;
}
[class*="st-key-recamara_"] section button * { display: none !important; }
[class*="st-key-recamara_"] section button::before { content: "📷  Sacar de nuevo"; font-size: 1rem; }
/* Consultas: botón "Escanear código o producto" en lugar del "Upload". */
.st-key-escanear [data-testid="stFileUploaderDropzoneInstructions"],
.st-key-escanear [data-testid="stFileChip"] { display: none !important; }
.st-key-escanear section { padding: 0; background: transparent; border: none; display: block; }
.st-key-escanear section > span, .st-key-escanear section button { display: block; width: 100%; max-width: none; }
.st-key-escanear section { text-align: center; }
.st-key-escanear section > span, .st-key-escanear section button { display: inline-block !important; width: auto !important; }
.st-key-escanear section button {
  min-height: 2rem; padding: .3rem .9rem; font-size: 0 !important; border-radius: 999px; background: #8B5A9E; color: white; border: 1px solid #8B5A9E;
}
.st-key-escanear section button * { display: none !important; }
/* Ícono de código de barras (dibujado en SVG) + texto, la mitad de grande que antes. */
.st-key-escanear section button::before { content: "Escanear código o producto"; font-size: .9rem; padding-left: 1.7rem;
  background: url("data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2024%2016%27%20fill%3D%27white%27%3E%3Crect%20x%3D%270%27%20y%3D%270%27%20width%3D%272%27%20height%3D%2716%27/%3E%3Crect%20x%3D%273%27%20y%3D%270%27%20width%3D%271%27%20height%3D%2716%27/%3E%3Crect%20x%3D%275%27%20y%3D%270%27%20width%3D%273%27%20height%3D%2716%27/%3E%3Crect%20x%3D%279%27%20y%3D%270%27%20width%3D%271%27%20height%3D%2716%27/%3E%3Crect%20x%3D%2711%27%20y%3D%270%27%20width%3D%272%27%20height%3D%2716%27/%3E%3Crect%20x%3D%2714%27%20y%3D%270%27%20width%3D%271%27%20height%3D%2716%27/%3E%3Crect%20x%3D%2716%27%20y%3D%270%27%20width%3D%273%27%20height%3D%2716%27/%3E%3Crect%20x%3D%2720%27%20y%3D%270%27%20width%3D%271%27%20height%3D%2716%27/%3E%3Crect%20x%3D%2722%27%20y%3D%270%27%20width%3D%272%27%20height%3D%2716%27/%3E%3C/svg%3E") no-repeat left center / 1.3rem .9rem; }
</style>
"""

# En el celular, "capture" hace que el botón abra directo la cámara trasera.
# Streamlit no tiene esa opción, así que se la agregamos al botón con un poco de JavaScript.
# (Se usa la cámara del propio celular: funciona aunque la app se abra por http en el WiFi.)
SCRIPT_CAMARA = """
<script>
const doc = window.parent.document;
function ajustar() {
  doc.querySelectorAll('.st-key-camara input[type=file], [class*="st-key-recamara_"] input[type=file], .st-key-escanear input[type=file]').forEach(i => {
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

# ------------------------------------------------------------ notas u observaciones (para mejorar la app)
# Cualquiera deja una nota. Quien tiene "ve_notas" en usuarios.json (Omar) ve todas y las borra
# a medida que aplica los cambios. Los demás ven las suyas hasta que cierran la app.
# Va chiquito, justo debajo de los botones de foto (pedido de Edu: no es tan importante).
def nota_u_observacion() -> None:
    st.session_state.setdefault("mis_notas", [])
    if not usuario:
        return
    st.markdown("<style>.st-key-nota button p { font-size: .85rem !important; color: #6b6b6b; }</style>",
                unsafe_allow_html=True)
    with st.container(key="nota"):
        with st.popover("📝 Nota u observación"):
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
    nota_u_observacion()
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
                # Dos opciones claras: volver a sacar la foto (abre la cámara) o quitar esta tarjeta.
                col_otra, col_cancelar = st.columns(2)
                with col_otra:
                    with st.container(key=f"recamara_{it['id']}"):
                        otra_foto = st.file_uploader(
                            "Sacar de nuevo", type=TIPOS_FOTO, key=f"otra_{it['id']}", label_visibility="collapsed"
                        )
                if col_cancelar.button("🗑️ Cancelar y eliminar", key=f"cancelar_{it['id']}", use_container_width=True):
                    cerrar_tarjeta(it, ("info", "Se eliminó esa foto sin guardar nada."))
                    st.rerun()
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
def ofertas_otc(_modificado: float, _modificado_precios: float = 0):
    """Ofertas OTC del Excel + lista de precios de la quincena (Word de comercial)."""
    lista = ofertas.leer() if ofertas.ARCHIVO.exists() else []
    if precios.ARCHIVO.exists():
        try:
            lista += precios.leer()
        except Exception:
            pass  # si el Word viene con otro formato, que no se caiga la app
    return lista


@st.cache_data(show_spinner=False)
def vademecum_cargado(ruta: str, _modificado: float):
    try:
        return vademecum.leer(Path(ruta))
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def lista_de_medicos(_modificado: float):
    return matriculas.leer()


@st.cache_data(show_spinner=False)
def mapa_de_cajones(_modificado: float):
    return cajones.leer() if cajones.ARCHIVO.exists() else []


@st.cache_data(show_spinner=False)
def catalogo_de_productos(_modificado: float):
    return catalogo.leer() if catalogo.ARCHIVO.exists() else []


def mostrar_catalogo(encontrados, lista_ofertas, maximo: int = 10) -> None:
    con_oferta = {o.id.lstrip("0") for o in lista_ofertas if o.id}
    cats, marcas = catalogo.resumen(encontrados)
    st.markdown(f"<small>Catálogo de productos · {len(encontrados)} encontrados</small>", unsafe_allow_html=True)
    if len(encontrados) > maximo:
        st.caption("Por categoría: " + " · ".join(f"{c} ({n})" for c, n in cats.most_common(4))
                   + "  \nPor marca: " + " · ".join(f"{m} ({n})" for m, n in marcas.most_common(5)))
    st.markdown("\n".join(
        f"- **{p.nombre}** · {p.marca} · _{p.categoria}_" + (" · 🏷️ en oferta" if p.sku.lstrip("0") in con_oferta else "")
        for p in encontrados[:maximo]
    ))
    if len(encontrados) > maximo:
        st.caption(f"Y {len(encontrados) - maximo} más: escribí más palabras para achicar la búsqueda.")
    st.divider()


OFERTAS_ETIQUETA = "🏷️ Ofertas"
AYUDA_ETIQUETA = "❓ Ayuda de la app"
SECCIONES_CON_BOTON = ()  # ninguna sección del .md tiene botón (pedido de Edu); se encuentran escribiendo
ESTILO_BUSCADOR = """
<style>
/* Caja de texto y botón 🔎 en la misma línea, también en el celular; sin el cartel "Press Enter". */
.st-key-buscador [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: .4rem; align-items: center; }
.st-key-buscador [data-testid="stColumn"]:first-child { flex: 1 1 auto !important; min-width: 0 !important; width: auto !important; }
.st-key-buscador [data-testid="stColumn"]:last-child { flex: 0 0 3rem !important; min-width: 3rem !important; width: 3rem !important; }
.st-key-buscador [data-testid="InputInstructions"] { display: none !important; }
.st-key-buscador [data-testid="stFormSubmitButton"] button { min-height: 2.6rem; padding: 0; font-size: 1.2rem; }
.st-key-buscador input { padding-right: 2.6rem !important; }
.boton-voz { position: absolute; right: .35rem; top: 50%; transform: translateY(-50%); border: none; background: transparent;
  font-size: 1.25rem; cursor: pointer; z-index: 5; padding: .2rem; line-height: 1; }
.boton-voz.escuchando { animation: latido 1s infinite; }
@keyframes latido { 50% { transform: translateY(-50%) scale(1.25); } }
</style>
"""

# Dictado por voz: usa el reconocimiento de voz del navegador (Chrome en Android lo trae; en otros puede no estar).
# Si no está, no aparece el 🎤 y se puede usar el micrófono del teclado del celular.
SCRIPT_VOZ = """
<script>
const doc = window.parent.document;
const win = window.parent;
const Reconocer = win.SpeechRecognition || win.webkitSpeechRecognition;
function poner() {
  const caja = doc.querySelector('.st-key-buscador input');
  if (!Reconocer || !caja || caja.parentElement.querySelector('.boton-voz')) return;
  caja.parentElement.style.position = 'relative';
  const b = doc.createElement('button');
  b.type = 'button'; b.className = 'boton-voz'; b.textContent = '🎤'; b.title = 'Dictar por voz';
  b.onclick = () => {
    const r = new Reconocer(); r.lang = 'es-AR'; r.interimResults = false; r.maxAlternatives = 1;
    b.classList.add('escuchando');
    r.onresult = (e) => {
      const texto = e.results[0][0].transcript;
      const setter = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
      setter.call(caja, texto);
      caja.dispatchEvent(new Event('input', { bubbles: true }));
      setTimeout(() => { const enviar = doc.querySelector('.st-key-buscador [data-testid="stFormSubmitButton"] button'); if (enviar) enviar.click(); }, 150);
    };
    r.onend = () => b.classList.remove('escuchando');
    r.onerror = () => b.classList.remove('escuchando');
    r.start();
  };
  caja.parentElement.appendChild(b);
}
poner();
new MutationObserver(poner).observe(doc.body, {childList: true, subtree: true});
</script>
"""
TITULO_AYUDANTE = "Asistente La Esquina"  # no usa IA: busca en los archivos de la carpeta consultas
CATALOGO_ETIQUETA = "🛍️ Catálogo"
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


def todos_los_vademecum() -> list:
    lista = []
    for nombre, ruta in vademecum.fuentes().values():
        lista += [(nombre, c) for c in vademecum_cargado(str(ruta), ruta.stat().st_mtime)]
    return lista


def sugerir(texto: str, sufijo: str = "", lugar: str = "general") -> None:
    """"¿Quisiste decir…?" con nombres comerciales y drogas de los vademécums y marcas del catálogo."""
    vocab = vademecum.vocabulario([c for _, c in todos_los_vademecum()])
    opciones = []
    for palabra in texto.split():
        opciones += [o for o in vademecum.sugerencias(vocab, palabra) if o not in opciones]
    if not opciones:
        return
    st.caption("¿Quisiste decir…?")
    columnas = st.columns(min(len(opciones), 3))
    for i, o in enumerate(opciones[:6]):
        if columnas[i % len(columnas)].button(o, key=f"sugerencia_{lugar}_{i}_{o}"):
            st.session_state["consulta_sugerida"] = o + sufijo
            st.rerun()


TOPE_VARIANTES = 300  # cuántos renglones del vademécum se juntan antes de filtrar
MOSTRAR_COBERTURA = 15  # renglones de la tabla de cobertura


def filtros_de_variantes(pares: list, clave: str, desde: int = 5) -> list:
    """Si la búsqueda trae muchas variantes ("t4 levo"), filtros para tildar: marca, dosis, presentación y laboratorio.

    Las opciones salen solo de lo que encontró esa búsqueda. Sin nada tildado, muestra todo.
    """
    lista = [c for _, c in pares]
    opciones = vademecum.variantes(lista)
    if len(pares) < desde or not opciones:
        return pares
    elegidos = {}
    with st.expander(f"🔎 Filtrar las {len(pares)} variantes ({', '.join(opciones).lower()})"):
        for nombre, valores in opciones.items():
            elegidos[nombre] = st.pills(nombre, valores, selection_mode="multi",
                                        key=f"filtro_{clave}_{nombre}") or []
    if not any(elegidos.values()):
        return pares
    quedan = {id(c) for c in vademecum.filtrar(lista, elegidos)}
    pares = [(n, c) for n, c in pares if id(c) in quedan]
    if not pares:
        st.caption("Ninguna variante tiene todo lo tildado: destildá algún filtro.")
    return pares


def fichas_de_vademecum(pregunta: str, maximo: int = 5) -> bool:
    """Datos del producto que figuran en los vademécums (laboratorio, droga, presentación, cobertura).

    No se muestra para qué sirve ni dosis: eso lo responde la farmacéutica (regla de la app).
    """
    pares = [(nombre, c) for nombre, c in todos_los_vademecum() if vademecum.buscar([c], pregunta)]
    pares = filtros_de_variantes(pares, f"ficha_{consultas.normalizar(pregunta)}")
    por_producto: dict[str, list] = {}
    for nombre, c in pares:
        por_producto.setdefault(c.producto, []).append((nombre, c))
    for producto, filas in list(por_producto.items())[:maximo]:
        c = filas[0][1]
        coberturas = " · ".join(f"{n} {x.porcentaje}" for n, x in filas)
        st.markdown(f"💊 **{producto}**  \n🏭 {c.laboratorio or '—'} · 🧪 Droga: {c.droga or '—'}"
                    + (f" · Código {c.codigo}" if c.codigo else "") + f"  \n🩺 Cobertura: {coberturas}"
                    + f" · [📷 Ver foto](https://www.google.com/search?tbm=isch&q={quote(producto + ' ' + c.laboratorio)})")
    if len(por_producto) > maximo:
        st.caption(f"…y {len(por_producto) - maximo} presentaciones más en el vademécum.")
    return bool(por_producto)


if consultas.ARCHIVO.exists():
    # Siempre a la vista (sin desplegable), así no se cierra ni se abre solo al buscar o escanear.
    with st.container(border=True, key="consultas"):
        base = base_de_consultas(consultas.ARCHIVO.stat().st_mtime)
        lista_ofertas = ofertas_otc(ofertas.ARCHIVO.stat().st_mtime if ofertas.ARCHIVO.exists() else 0,
                                    precios.ARCHIVO.stat().st_mtime if precios.ARCHIVO.exists() else 0)
        items_cajones = mapa_de_cajones(cajones.ARCHIVO.stat().st_mtime if cajones.ARCHIVO.exists() else 0)
        productos = catalogo_de_productos(catalogo.ARCHIVO.stat().st_mtime if catalogo.ARCHIVO.exists() else 0)
        hoy = consultas.hoy_argentina()

        # Arriba: el buscador ("ayudante", sin IA). Debajo: escanear el código del producto.
        # Encabezado con el ayudante: la cruz pixelada con ojitos (el ícono de la app), más grande y amigable.
        avatar = (f'<img src="data:image/png;base64,{en_base64(ICONO_APP)}" alt="" style="height:3rem; width:3rem; '
                  f'image-rendering:pixelated; background:#f4f7e1; border-radius:50%; padding:.3rem;">') if ICONO_APP.exists() else "🤖"
        st.markdown(
            f'<div style="display:flex; align-items:center; gap:.7rem; margin-bottom:.2rem;">{avatar}'
            f'<div><div style="font-size:1.2rem; font-weight:700; line-height:1.2;">{TITULO_AYUDANTE}</div>'
            f'<div style="font-size:.85rem; color:#6b6b6b;">Consultas rápidas y ayuda de la app</div></div></div>',
            unsafe_allow_html=True,
        )
        st.caption("Escribí (o dictá con 🎤) una palabra o el número del código y tocá 🔎 o Enter (ej.: OSDE, Galeno, Tafirol, ibuprofeno, Ctrl+V, "
                   "quién trabaja hoy, la foto no se lee). Para los cajones sirve aunque esté mal escrito.")
        # Buscador: se escribe y se busca con Enter o con el botón 🔎. El 🎤 (si el navegador lo permite)
        # dicta la búsqueda por voz. Va en un formulario para que busque solo al confirmar.
        st.markdown(ESTILO_BUSCADOR, unsafe_allow_html=True)
        if "consulta_sugerida" in st.session_state:  # tocó una sugerencia ("¿Quisiste decir…?")
            st.session_state["consulta_txt"] = st.session_state.pop("consulta_sugerida")
        with st.container(key="buscador"):
            with st.form("form_buscar", border=False):
                col_txt, col_btn = st.columns([6, 1])
                pregunta = col_txt.text_input("Buscar", key="consulta_txt", label_visibility="collapsed",
                                              placeholder="Escribí o dictá tu consulta...")
                col_btn.form_submit_button("🔎", key="btn_buscar", use_container_width=True, help="Buscar")
        components.html(SCRIPT_VOZ, height=0)

        # Escaneo apagado hasta tener los códigos cargados. Para activarlo: en Secrets, escaneo_activo = true
        if ESCANEO_ACTIVO:
            # Lector de código de barras: foto del producto -> oferta, precio o dato cargado.
            st.session_state.setdefault("ronda_codigo", 0)
            # Un solo botón grande que abre la cámara (sin el "Upload" ni el texto de Streamlit).
            with st.container(key="escanear"):
                foto_codigo = st.file_uploader(
                    "Escanear código o producto", type=TIPOS_FOTO, key=f"foto_codigo_{st.session_state['ronda_codigo']}",
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

        st.markdown(
            "<style>.st-key-categorias [data-testid='stButtonGroup'] button p { font-size: .95rem !important; }"
            ".st-key-categorias [data-testid='stButtonGroup'] button { min-height: 2.4rem; padding: .3rem .5rem !important; }</style>",
            unsafe_allow_html=True,
        )
        # Botones de categoría (pedido de Edu: solo estos). El resto se encuentra escribiendo en el buscador.
        etiquetas = [s.etiqueta for s in base.secciones if s.numero in SECCIONES_CON_BOTON]
        if lista_ofertas:
            etiquetas.append(OFERTAS_ETIQUETA)
        if items_cajones:
            etiquetas.append(CAJONES_ETIQUETA)
        with st.container(key="categorias"):
            categoria = st.pills("Categorías", etiquetas, key="consulta_cat", label_visibility="collapsed")
        if pregunta.strip() and matriculas.es_consulta(pregunta) and matriculas.ARCHIVO.exists():
            # "matricula 2911" o "dr abalos": médicos de la provincia (para verificar la receta).
            medicos = matriculas.buscar(lista_de_medicos(matriculas.ARCHIVO.stat().st_mtime), pregunta)
            if medicos:
                marca = {"Sí": " · ✅ **Convenio ISSPSE** (descuento extra)",
                         "Probable": " · 🟡 Convenio ISSPSE probable: confirmá con \"dni\" y su número"}
                st.markdown("\n".join(f"- 👨‍⚕️ **{m.nombre}** · Matrícula **{m.matricula}**{marca.get(m.isspse, '')}"
                                       for m in medicos))
                if any(m.isspse for m in medicos):
                    st.warning(AVISO_ISSPSE)
                st.caption("Si no dice convenio, igual puede estar con el nombre escrito distinto: "
                           "confirmalo escribiendo \"isspse\" y su DNI.")
            else:
                st.info("👨‍⚕️ No encontré ese médico o matrícula en el listado de la provincia.")
            pregunta = ""
        dni = padron.dni_de_la_pregunta(pregunta) if pregunta.strip() else None
        if dni:
            # "dni 25333620": solo dice en qué lista de OSDOP figura (sin nombre ni enfermedad).
            datos_padron, clave = padron.leer(), str(secretos().get("padron_clave", ""))
            if not datos_padron or not clave:
                st.info("🪪 Los padrones (OSDOP, ISSPSE) todavía no están cargados.")
            else:
                listas = padron.consultar(datos_padron, dni, clave)
                mes = datos_padron.get("mes", "")
                if listas:
                    nombres = [{"Cobertura especial": "Cobertura especial (crónico)",
                                "ISSPSE": "convenio ISSPSE (descuento extra)"}.get(l, l) for l in listas]
                    st.success(f"🪪 DNI {dni}: figura en **{' · '.join(nombres)}**" + (f" (padrón {mes})" if mes else ""))
                    if "ISSPSE" in listas:
                        st.warning(AVISO_ISSPSE)
                else:
                    st.warning(f"🪪 DNI {dni}: **no figura** en los padrones cargados (OSDOP, ISSPSE)" + (f", {mes}" if mes else "") + ".")
            pregunta = ""  # no buscar el número en el resto de la base
        cargadas = vademecum.fuentes()  # {"vale": ("Vale Salud", ruta)}
        cobertura = (consultas.medicamento_de_cobertura(pregunta, {k: (k,) for k in cargadas})
                     if pregunta.strip() else None)
        if cobertura:
            # "clinal cobertura": tabla obra social -> % con todos los vademécums cargados.
            # "clinal cobertura vale": solo Vale Salud.
            medicamento, elegidas = cobertura
            st.markdown(f"**🩺 Cobertura de {medicamento}**")
            pares = []
            for clave in elegidas:
                if clave in cargadas:
                    nombre, ruta = cargadas[clave]
                    pares += [(nombre, c) for c in vademecum.buscar(vademecum_cargado(str(ruta), ruta.stat().st_mtime),
                                                                    medicamento, limite=TOPE_VARIANTES)]
            pares = filtros_de_variantes(pares, f"cob_{consultas.normalizar(medicamento)}")
            filas = [{"Obra social": nombre, "Cobertura": c.porcentaje, "Producto": c.producto,
                      "Laboratorio": c.laboratorio, "Droga": c.droga, "Marca": c.marca} for nombre, c in pares]
            if filas:
                st.dataframe([{k: v for k, v in f.items() if k != "Marca"} for f in filas[:MOSTRAR_COBERTURA]],
                             hide_index=True, use_container_width=True)
                if len(filas) > MOSTRAR_COBERTURA:
                    st.caption(f"Y {len(filas) - MOSTRAR_COBERTURA} más: tocá 🔎 Filtrar, arriba, para achicar la lista.")
            if not filas:
                sugerir(medicamento, " cobertura" + "".join(f" {k}" for k in elegidas if len(elegidas) == 1), "cobertura")
            sin_dato = [cargadas[k][0] for k in elegidas if k in cargadas and not any(f["Obra social"] == cargadas[k][0] for f in filas)]
            if sin_dato:
                st.caption(f"No figura en el vademécum de: {', '.join(sin_dato)}.")
            if "pami" in elegidas and "pami" not in cargadas:
                # Alfabeta tiene una página por marca comercial (alfabeta.net/precio/bronax-cb.html).
                # Si se buscó por droga ("ibuprofeno"), se arman los links con las marcas del vademécum.
                marcas = []
                for _, c in todos_los_vademecum():
                    if vademecum.buscar([c], medicamento):
                        m = vademecum.marca_corta(c)  # la página de Alfabeta es por marca, sin la dosis
                        if m and m not in marcas:
                            marcas.append(m)
                if not marcas:
                    marcas = [medicamento]
                for m in marcas[:4]:
                    s_m = "-".join(re.findall(r"[a-z0-9]+", consultas.normalizar(m)))
                    st.link_button(f"PAMI (Alfabeta): {m.upper()}", f"https://www.alfabeta.net/precio/{s_m}.html",
                                   use_container_width=True)
                st.caption("PAMI no tiene archivo cargado: se consulta en Alfabeta. Si no encuentra el producto, "
                           "buscalo en [alfabeta.net](https://www.alfabeta.net/).")
            if "osdop" in elegidas and "osdop" not in cargadas:
                st.caption("OSDOP: no hay vademécum cargado, solo el padrón (escribí \"dni\" y el número para ver si figura).")
            if "vale" in elegidas and "vale" not in cargadas:
                st.link_button("Vale Salud (vademécum)", "https://valesalud.ar/vademecum.html", use_container_width=True)
            pregunta = medicamento  # además, lo que haya del producto (ofertas, cajón, catálogo)
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
                    st.markdown("<small>Ofertas</small>", unsafe_allow_html=True)
                    if en_cajon:
                        st.caption(f"🏷️ Hay ofertas de este producto: {cajones.VERIFICAR}.")
                    mostrar_ofertas(encontradas, hoy)
                for titulo, texto in r["datos"]:
                    st.markdown(f"<small>{titulo}</small>", unsafe_allow_html=True)
                    st.markdown(texto)
                    st.divider()
                de_ayuda = ayuda.buscar(pregunta)
                for q, resp in de_ayuda:
                    st.markdown(f"<small>Ayuda de la app</small>", unsafe_allow_html=True)
                    st.markdown(f"**{q}**  \n{resp}")
                    st.divider()
                en_vademecum = fichas_de_vademecum(pregunta) if not cobertura else bool(filas)
                del_catalogo = catalogo.buscar(productos, pregunta)
                if del_catalogo:
                    mostrar_catalogo(del_catalogo, lista_ofertas)
                if not (r["datos"] or r["hoy"] or r["sin_horario"] or encontradas or en_cajon or del_catalogo or de_ayuda or en_vademecum):
                    if re.fullmatch(r"\s*\d{8,14}\s*", pregunta):
                        st.info(f"🔎 {ofertas.NO_CARGADO}")
                    elif len(pregunta.strip()) >= 2:
                        st.info(consultas.SIN_DATO)
                        if not cobertura:  # en cobertura ya se sugirió arriba
                            sugerir(pregunta)
        elif categoria == AYUDA_ETIQUETA:
            st.markdown(ayuda.AYUDA)
        elif categoria == CATALOGO_ETIQUETA:
            st.markdown(f"**{len(productos)} productos** en el catálogo. Buscá por nombre, marca o categoría arriba.")
            st.markdown("\n".join(f"- {c}: {n}" for c, n in catalogo.categorias(productos).most_common()))
        elif categoria == CAJONES_ETIQUETA:
            for cajon, contenido in cajones.mapa(items_cajones).items():
                st.markdown(f"**🗄️ {cajon}**  \n" + " · ".join(
                    it.nombre + (" ⚠️" if it.a_confirmar else "") for it in contenido))
            st.caption("⚠️ = nombre a confirmar (revisar la caja).")
        elif categoria == OFERTAS_ETIQUETA:
            # Todas las ofertas juntas: promos de la semana (tarjetas, bancos, laboratorios) y productos.
            # Una tarjeta por promo (se lee mejor en el celular que la tabla). Las vencidas no se muestran.
            promos = [d for d in base.datos if d.seccion == "7" and d.titulo == "Promociones vigentes"
                      and not d.texto.startswith("Fecha de referencia")]
            if promos:
                st.markdown("**🎉 Promociones de la semana** (tarjetas, bancos y laboratorios)")
                for d in promos:
                    if consultas._promo_vencida(d, hoy):
                        continue
                    with st.container(border=True):
                        st.markdown(consultas.con_aviso(d, hoy))
                st.markdown("**💊 Productos en oferta**")
            vigentes = [o for o in lista_ofertas if o.vigencia(hoy) != "vencida"]
            st.markdown(f"**{len(lista_ofertas)} productos en oferta** · sin precio cargado: "
                        f"{sum(1 for o in lista_ofertas if o.paga_el_cliente() is None)}")
            if len(vigentes) < len(lista_ofertas):
                st.warning(f"❌ {len(lista_ofertas) - len(vigentes)} ofertas ya están vencidas.")
            st.dataframe(
                [{
                    "Producto": f"{o.producto} {o.presentacion}".strip(),
                    "Oferta": o.texto_oferta(),
                    "Hasta": (o.hasta.strftime("%d/%m/%Y") if o.hasta else "—") + ("" if o.vigencia(hoy) == "vigente" else f" ({o.vigencia(hoy)})"),
                    "Paga el cliente": ofertas.pesos(o.paga_el_cliente()) if o.paga_el_cliente() is not None else ofertas.SIN_PRECIO,
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

# Soporte: abre el sistema de tickets del Área TI en otra pestaña, con el logo de I.T. AREA.
LOGO_TI = IMAGENES / "logo_ti.png"
URL_TICKETS = "https://area-t-i-tickets.vercel.app/"
if LOGO_TI.exists():
    st.markdown(
        # Colores de Área TI, pero discreto (pedido de Edu): botón chico y centrado, fondo claro,
        # borde fino degradé violeta → verde y el logo redondo con aro verde.
        f"""<div style="text-align:center;"><a href="{URL_TICKETS}" target="_blank" rel="noopener" style="display:inline-flex;
        align-items:center; gap:.5rem; padding:.35rem .95rem; border:1px solid transparent; border-radius:999px;
        text-decoration:none; color:#31333f; font-size:1.05rem; font-weight:500;
        background: linear-gradient(#ffffff, #ffffff) padding-box, linear-gradient(90deg, #8B5CF6, #22C55E) border-box;">
        <img src="data:image/png;base64,{en_base64(LOGO_TI)}" alt="" style="height:1.6rem; width:1.6rem; border-radius:50%;
        box-shadow: 0 0 0 1px #22C55E;">
        <span>Reportar incidencia a <span style="color:#7C3AED">Equipo</span> <span style="color:#16A34A">TI</span></span></a></div>""",
        unsafe_allow_html=True,
    )
else:
    st.link_button("Reportar incidencia a Equipo TI", URL_TICKETS, use_container_width=True)

# Acceso a la página oficial, con los colores de la web (verde lima, amarillo y violeta) y la cruz de La Esquina.
URL_WEB = "https://farmacialaesquina.com.ar/"
cruz = (f'<img src="data:image/png;base64,{en_base64(ICONO)}" alt="" style="height:1.6rem; width:1.6rem;">'
        if ICONO.exists() else "🌐")
st.markdown(
    f"""<div style="text-align:center; margin-top:.6rem;"><a href="{URL_WEB}" target="_blank" rel="noopener" style="display:inline-flex;
    align-items:center; gap:.5rem; padding:.35rem .95rem; border:1px solid transparent; border-radius:999px;
    text-decoration:none; color:#31333f; font-size:1.05rem; font-weight:500;
    background: linear-gradient(#ffffff, #ffffff) padding-box, linear-gradient(90deg, #BFCD3A, #FFF212, #8B5A9E) border-box;">
    {cruz}<span>Página oficial <span style="color:#8B5A9E; font-weight:700;">Farmacia La Esquina</span></span></a></div>""",
    unsafe_allow_html=True,
)

# Enviar para imprimir: primero la foto (cámara o galería) y después el menú "Compartir" del celular,
# donde se elige WhatsApp o Gmail y el contacto de la Mitre. wa.me y mailto no pueden adjuntar archivos.
ENVIAR_PARA_IMPRIMIR = """
<style>
  body { margin:0; font-family: "Source Sans Pro", sans-serif; text-align:center; color:#31333f; }
  .caja { border:1px solid #d9cbe3; border-radius:14px; padding:.5rem .6rem .55rem; background:#ffffffcc; }
  .tit { font-weight:700; color:#8B5A9E; margin-bottom:.35rem; }
  .fila { display:flex; gap:.4rem; justify-content:center; }
  .fila label { flex:1 1 0; max-width:12rem; white-space:nowrap; }
  button#enviar { display:block; width:100%; max-width:24.4rem; margin:.35rem auto 0; }
  label, button { font:inherit; font-size:.95rem; border-radius:999px; padding:.35rem .9rem; cursor:pointer;
                  border:1px solid #BFCD3A; background:#F8FBEA; color:#31333f; }
  button#enviar { background:#25D366; border-color:#25D366; color:#fff; font-weight:700; }
  button#enviar:disabled { background:#e6e6e6; border-color:#e6e6e6; color:#999; cursor:default; }
  input { display:none; }
  .nota { font-size:.8rem; color:#777; margin-top:.3rem; line-height:1.2; }
  .ok { color:#16A34A; } .mal { color:#c0392b; }
</style>
<div class="caja">
  <div class="tit">📤 Enviar para imprimir</div>
  <div class="fila">
    <label>📷 Sacar foto<input id="cam" type="file" accept="image/*" capture="environment"></label>
    <label>🖼️ Galería o archivo<input id="gal" type="file" accept="image/*,application/pdf" multiple></label>
  </div>
  <button id="enviar" disabled>📤 Enviar (WhatsApp o correo)</button>
  <div class="nota" id="nota">1) Sacá o elegí el archivo · 2) Tocá Enviar y elegí WhatsApp o Gmail y el contacto de la Mitre.</div>
</div>
<script>
  const TEXTO = "Te comparto un archivo para imprimir";
  let archivos = [];
  const nota = document.getElementById("nota"), enviar = document.getElementById("enviar");
  function elegidos(ev) {
    archivos = Array.from(ev.target.files || []);
    if (!archivos.length) return;
    enviar.disabled = false;
    nota.className = "nota ok";
    nota.textContent = "✅ " + (archivos.length === 1 ? archivos[0].name : archivos.length + " archivos") + " listo. Tocá Enviar.";
  }
  document.getElementById("cam").addEventListener("change", elegidos);
  document.getElementById("gal").addEventListener("change", elegidos);
  enviar.addEventListener("click", async () => {
    const datos = { files: archivos, text: TEXTO, title: "Archivo para imprimir" };
    if (!navigator.canShare || !navigator.canShare({ files: archivos })) {
      nota.className = "nota mal";
      nota.textContent = "⚠️ Este navegador no permite compartir archivos. Usá Chrome en el celular, o los botones de WhatsApp y correo de abajo y adjuntá el archivo a mano.";
      return;
    }
    try {
      await navigator.share(datos);
      nota.className = "nota ok"; nota.textContent = "✅ Enviado. Podés sacar otra foto.";
      archivos = []; enviar.disabled = true;
    } catch (e) {
      if (e.name !== "AbortError") { nota.className = "nota mal"; nota.textContent = "⚠️ No se pudo compartir: " + e.message; }
    }
  });
</script>
"""
components.html(ENVIAR_PARA_IMPRIMIR, height=158)

# WhatsApp de la sucursal Mitre, con el mensaje ya escrito.
# Por defecto, los de la Mitre. Para probar con otros datos, en Secrets:
#   whatsapp_destino = "3856210820"   (con o sin +54 9: la app agrega el 549 si falta)
#   correo_destino = "alguien@ejemplo.com"
def numero_whatsapp(texto: str) -> str:
    """Deja el número como lo pide wa.me: 549 + característica + número. Agrega el 549 si falta."""
    n = "".join(c for c in str(texto) if c.isdigit())
    if n.startswith("54"):
        n = n[2:]
    n = n.removeprefix("9").removeprefix("0")
    return "549" + n


WHATSAPP_DESTINO = numero_whatsapp(secretos().get("whatsapp_destino", "") or "3854750195")
CORREO_DESTINO = str(secretos().get("correo_destino", "") or "esquinamitre@fesquina.com.ar").strip()
URL_WHATSAPP = f"https://wa.me/{WHATSAPP_DESTINO}?text=" + quote("Te comparto un archivo para imprimir")
LOGO_WHATSAPP = (
    '<svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true"><path fill="#25D366" d="M16 3C9 3 3.3 8.7 3.3 15.7c0 2.2.6 4.4 1.7 6.3L3.2 28.8l7-1.8c1.8 1 3.8 1.5 5.8 1.5 7 0 12.7-5.7 12.7-12.7S23 3 16 3z"/>'
    '<path fill="#fff" d="M22.6 19.1c-.4-.2-2.1-1-2.4-1.1-.3-.1-.6-.2-.8.2-.2.4-.9 1.1-1.1 1.3-.2.2-.4.3-.8.1-.4-.2-1.6-.6-3-1.9-1.1-1-1.9-2.2-2.1-2.6-.2-.4 0-.6.2-.8l.6-.7c.2-.2.3-.4.4-.6.1-.3.1-.5 0-.7l-1.1-2.6c-.3-.7-.6-.6-.8-.6h-.7c-.2 0-.6.1-1 .5-.3.4-1.3 1.3-1.3 3.1s1.3 3.6 1.5 3.9c.2.2 2.6 4 6.3 5.6 2.2.9 3 1 4.1.8.7-.1 2.1-.9 2.4-1.7.3-.8.3-1.6.2-1.7-.1-.2-.3-.3-.7-.5z"/></svg>'
)
st.markdown(
    f"""<div style="text-align:center; margin-top:.6rem;"><a href="{URL_WHATSAPP}" target="_blank" rel="noopener" style="display:inline-flex;
    align-items:center; gap:.5rem; padding:.35rem .95rem; border:1px solid #25D366; border-radius:999px;
    text-decoration:none; color:#075E54; font-size:1.05rem; font-weight:500; background:#ffffff;">
    {LOGO_WHATSAPP}<span>WhatsApp <span style="color:#128C7E; font-weight:700;">Sucursal Mitre</span></span></a></div>""",
    unsafe_allow_html=True,
)

# Correo de la sucursal, con asunto y mensaje ya escritos.
URL_CORREO = f"mailto:{CORREO_DESTINO}?subject=" + quote("Archivos para imprimir") + "&body=" + quote("Te adjunto archivos para imprimir")
st.markdown(
    f"""<div style="text-align:center; margin-top:.6rem;"><a href="{URL_CORREO}" style="display:inline-flex;
    align-items:center; gap:.5rem; padding:.35rem .95rem; border:1px solid #4285F4; border-radius:999px;
    text-decoration:none; color:#31333f; font-size:1.05rem; font-weight:500; background:#ffffff;">
    <span style="font-size:1.3rem;">✉️</span><span>Correo <span style="color:#1A73E8; font-weight:700;">{CORREO_DESTINO}</span></span></a></div>""",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------ pie de página (marca de agua)
# Leyenda al final de la app, en gris y letra chica, visible en todas las pantallas.
st.markdown(
    """<div style="text-align:center; color:#9a9a9a; font-size:0.8rem; margin-top:2.5rem; padding-top:1rem; border-top:1px solid rgba(49,51,63,0.1);">
    Diseño y desarrollo: Omar Eduardo Giménez · Con la ayuda de Claude Code
    </div>""",
    unsafe_allow_html=True,
)
