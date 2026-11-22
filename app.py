"""Lector de trazabilidad - Farmacia La Esquina.

Para abrirla:  streamlit run app.py

Función 1 (📷 Leer fotos): se sube o se saca la foto, la app lee los datos,
avisa si la foto no sirve y pide otra, y el usuario confirma.
Función 2 (📄 Registros): queda guardado cada registro con quién envió la
foto y la fecha. Se puede descargar en Excel. Las fotos NO se guardan.
"""

from __future__ import annotations

import io
import json
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

from lector import registro
from lector.calidad import ESTADO_OK, ESTADO_OTRA_FOTO, estado, medir
from lector.gs1 import gtin_es_valido
from lector.imagen import abrir, analizar, fecha_de_la_foto, ocr_disponible

CONFIG = json.loads((Path(__file__).parent / "usuarios.json").read_text(encoding="utf-8"))
USUARIOS = {u["nombre"]: u for u in CONFIG["usuarios"]}
SUCURSAL = CONFIG.get("sucursal", "")
CAMPOS = [("gtin", "GTIN (01)"), ("serie", "Serie (21)"), ("lote", "Lote (10)"), ("vencimiento", "Vencimiento"), ("elaboracion", "Elaboración")]
EN_MAYUSCULAS = ("gtin", "serie", "lote")

st.set_page_config(page_title="Lector de trazabilidad", page_icon="💊", layout="wide")
st.title("💊 Lector de trazabilidad")
st.caption(f"Farmacia La Esquina · Sucursal {SUCURSAL}")

# ------------------------------------------------------------ ¿quién usa la app?
with st.sidebar:
    st.header("¿Quién sos?")
    nombre = st.selectbox("Usuario", ["— elegí tu nombre —", *USUARIOS], key="usuario")
    usuario = USUARIOS.get(nombre)
    if usuario:
        st.success(f"{usuario['nombre']} · {usuario['rol']}")
    if not ocr_disponible():
        st.warning("El lector de texto (Tesseract) no está instalado: solo se van a leer los DataMatrix. Mirá el README.")

st.session_state.setdefault("items", [])


def procesar(contenido: bytes, nombre_archivo: str) -> list[dict]:
    """Lee una foto y devuelve un ítem por cada envase encontrado."""
    img = abrir(io.BytesIO(contenido))
    fecha, origen = fecha_de_la_foto(img, nombre_archivo)
    if fecha is None:
        fecha, origen = datetime.now(), "fecha de carga (la foto no traía fecha)"
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


tab_leer, tab_registros = st.tabs(["📷 1. Leer fotos", "📄 2. Registros"])

# ------------------------------------------------------------ función 1: leer
with tab_leer:
    if not usuario:
        st.info("👈 Primero elegí tu nombre en el menú de la izquierda.")
    st.write(
        "Sacá una foto o elegila de la galería. Que se vea el **cuadradito (DataMatrix)** y los datos "
        "impresos al lado, de cerca, con buena luz y sin reflejos."
    )
    fotos = st.file_uploader(
        "Fotos", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True, label_visibility="collapsed", key="subida"
    )
    if st.button("🔎 Leer códigos", type="primary", disabled=not fotos or not usuario):
        nuevos = []
        barra = st.progress(0.0, text="Leyendo…")
        for n, foto in enumerate(fotos, start=1):
            barra.progress(n / len(fotos), text=f"Leyendo {foto.name} ({n}/{len(fotos)})")
            try:
                nuevos += procesar(foto.getvalue(), foto.name)
            except Exception as e:
                st.error(f"No se pudo abrir {foto.name}: {e}")
        barra.empty()
        st.session_state["items"] = nuevos

    items = st.session_state["items"]
    if items:
        listos = sum(it["estado"] == ESTADO_OK for it in items)
        otra = sum(it["estado"] == ESTADO_OTRA_FOTO for it in items)
        st.subheader("Revisá cada envase")
        st.write(f"{len(items)} envase(s): **{listos} listos**, {len(items) - listos - otra} para revisar, **{otra} piden otra foto**.")

    for it in items:
        lec = it["lectura"]
        with st.container(border=True):
            col_foto, col_datos = st.columns([1, 2])
            col_foto.image(it["foto"], caption=it["archivo_foto"], use_container_width=True)
            with col_datos:
                st.markdown(f"### {it['estado']}")
                st.caption(f"Leído desde: {lec['fuente']} · Foto del {it['fecha_foto']} ({it['origen_fecha_foto']})")
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
                for (campo, titulo), col in zip(CAMPOS, st.columns(len(CAMPOS))):
                    col.text_input(titulo, value=lec.get(campo, ""), key=f"{campo}_{it['id']}")
                gtin_actual = st.session_state.get(f"gtin_{it['id']}", "").strip()
                if gtin_actual and not gtin_es_valido(gtin_actual):
                    st.warning("Ese GTIN no cierra con el dígito verificador: revisá los números.")
                st.checkbox(
                    "Los datos coinciden con el envase",
                    value=it["estado"] == ESTADO_OK,
                    key=f"ok_{it['id']}",
                    help="Marcalo cuando hayas comparado los datos con la foto o el envase.",
                )

    if items and st.button("💾 Guardar los confirmados", type="primary", disabled=not usuario):
        duplicados, pendientes, filas = [], [], []
        for it in items:
            if not st.session_state.get(f"ok_{it['id']}"):
                pendientes.append(it)
                continue
            datos = {campo: st.session_state.get(f"{campo}_{it['id']}", "").strip() for campo, _ in CAMPOS}
            for campo in EN_MAYUSCULAS:
                datos[campo] = datos[campo].upper()
            repetido_aca = any(f["gtin"] == datos["gtin"] and f["serie"] == datos["serie"] for f in filas)
            if repetido_aca or registro.ya_registrado(datos["gtin"], datos["serie"]):
                duplicados.append(f"{datos['gtin']} / {datos['serie']}")
                continue
            if fue_corregido(it, datos):
                estado_final = "Corregido a mano"
            elif it["estado"] == ESTADO_OK:
                estado_final = "Leído del DataMatrix"
            else:
                estado_final = "Revisado por el usuario"
            filas.append(
                dict(
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
            )
        guardados = registro.guardar(filas)
        st.session_state["items"] = pendientes
        if guardados:
            st.success(f"Se guardaron {guardados} registro(s). Los podés ver en la pestaña **Registros**.")
        if duplicados:
            st.warning("Ya estaban registrados y no se volvieron a guardar: " + ", ".join(duplicados))
        if pendientes:
            st.info(f"Quedaron {len(pendientes)} envase(s) sin confirmar en la lista.")
        st.button("Seguir")

# ------------------------------------------------------------ función 2: registros
with tab_registros:
    datos = registro.leer()
    if datos.empty:
        st.info("Todavía no hay registros guardados.")
    else:
        c1, c2 = st.columns(2)
        filtro_usuario = c1.multiselect("Filtrar por usuario", sorted(datos["usuario"].unique()))
        buscar = c2.text_input("Buscar (GTIN, serie o lote)")
        vista = datos.iloc[::-1]  # lo más nuevo arriba
        if filtro_usuario:
            vista = vista[vista["usuario"].isin(filtro_usuario)]
        if buscar:
            b = buscar.strip().upper()
            vista = vista[vista[["gtin", "serie", "lote"]].apply(lambda col: col.str.upper().str.contains(b, regex=False)).any(axis=1)]
        st.write(f"{len(vista)} registro(s), lo más nuevo arriba.")

        st.dataframe(
            vista[["gtin", "serie", "lote", "vencimiento", "usuario", "fecha_foto", "estado",
                   "fecha_registro", "elaboracion", "fuente", "origen_fecha_foto", "archivo_foto"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "gtin": "GTIN",
                "serie": "Serie",
                "lote": "Lote",
                "vencimiento": "Vencimiento",
                "usuario": "Envió",
                "fecha_foto": "Fecha de la foto",
                "estado": "Estado",
                "fecha_registro": "Guardado el",
                "elaboracion": "Elaboración",
                "fuente": "Leído desde",
                "origen_fecha_foto": "Origen de la fecha",
                "archivo_foto": "Nombre de la foto",
            },
        )

        hoy = datetime.now().strftime("%Y-%m-%d")
        d1, d2 = st.columns(2)
        d1.download_button(
            "⬇️ Descargar Excel", registro.a_excel(vista), f"trazabilidad_{hoy}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        d2.download_button(
            "⬇️ Descargar CSV", vista.to_csv(sep=";", index=False).encode("utf-8-sig"), f"trazabilidad_{hoy}.csv", "text/csv"
        )
