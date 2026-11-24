"""Lista de precios de la quincena: lee consultas/Precios_Quincena.docx (el Word de comercial).

El Word trae una tabla por rubro (ALIMENTOS, CAPILARES, PAÑALES BEBE...) y en cada celda un
producto así:
    NOMBRE / código de barras (o "TODAS LAS REFERENCIAS") / PRECIO REGULAR: $... / OFERTA: $... o -20% OFF / (DESDE EL 16-11 AL 30-11)
Se reemplaza subiendo el Word nuevo con el mismo nombre (ver README). No necesita librerías extra.
"""

from __future__ import annotations

import re
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

from .ofertas import Oferta, _a_numero, solo_digitos

ARCHIVO = Path(__file__).resolve().parent.parent / "consultas" / "Precios_Quincena.docx"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _tablas(archivo: Path) -> list[list[list[list[str]]]]:
    """Tablas -> filas -> celdas -> líneas de texto (un párrafo por línea)."""
    with zipfile.ZipFile(archivo) as z:
        raiz = ElementTree.fromstring(z.read("word/document.xml"))
    tablas = []
    for tbl in raiz.iter(f"{W}tbl"):
        filas = []
        for tr in tbl.iter(f"{W}tr"):
            celdas = []
            for tc in tr.iter(f"{W}tc"):
                lineas = ["".join(t.text or "" for t in p.iter(f"{W}t")).strip() for p in tc.iter(f"{W}p")]
                celdas.append([l for l in lineas if l])
            filas.append(celdas)
        tablas.append(filas)
    return tablas


def _fechas(texto: str, anio: int) -> tuple[date | None, date | None]:
    m = re.search(r"(\d{1,2})-(\d{1,2})\s*AL\s*(\d{1,2})-(\d{1,2})", texto, re.I)
    if not m:
        return None, None
    d1, m1, d2, m2 = map(int, m.groups())
    return date(anio, m1, d1), date(anio if m2 >= m1 else anio + 1, m2, d2)


def _celda(lineas: list[str], rubro: str, anio: int) -> Oferta | None:
    if not lineas:
        return None
    nombre, codigo, presentacion, precio, precio_oferta, descuento = lineas[0], "", "", None, None, None
    desde = hasta = None
    for l in lineas[1:]:
        arriba = l.upper()
        if arriba.startswith("PRECIO REGULAR"):
            precio = _a_numero(l.split(":", 1)[1])
        elif arriba.startswith("OFERTA"):
            valor = l.split(":", 1)[1]
            pct = re.search(r"(\d+(?:[.,]\d+)?)\s*%", valor)
            if pct:
                descuento = float(pct.group(1).replace(",", ".")) / 100
            else:
                precio_oferta = _a_numero(valor)
        elif "DESDE" in arriba:
            desde, hasta = _fechas(l, anio)
        elif re.fullmatch(r"\d{7,14}", solo_digitos(l)) and solo_digitos(l) == l.strip():
            codigo = l.strip()
        else:
            presentacion = l.capitalize()
    if precio is not None and precio_oferta is not None and precio:
        descuento = 1 - precio_oferta / precio
    if precio is None and precio_oferta is None and descuento is None:
        return None
    return Oferta(
        id="", producto=nombre, presentacion=presentacion, codigo=codigo, laboratorio="",
        oferta="Descuento" if descuento is not None else "Precio de oferta", descuento=descuento, precio=precio, desde=desde, hasta=hasta,
        nota=f"Lista de precios de la quincena · {rubro.capitalize()}", precio_oferta=precio_oferta,
    )


def leer(archivo: Path = ARCHIVO, anio: int | None = None) -> list[Oferta]:
    anio = anio or date.today().year
    salida = []
    for filas in _tablas(archivo):
        if not filas or not filas[0]:
            continue
        rubro = (filas[0][0] or [""])[0]
        for fila in filas[1:]:
            for lineas in fila:
                o = _celda(lineas, rubro, anio)
                if o:
                    salida.append(o)
    return salida
