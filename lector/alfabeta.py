"""Precios de AlfaBeta (alfabeta.net) y lo que paga el afiliado de PAMI.

La página de cada marca es  https://www.alfabeta.net/precio/<marca>.html  (no pide usuario).
Trae cada presentación con su precio, la fecha del precio y, si tiene PAMI, la línea
"AF $..." = lo que termina pagando el afiliado de PAMI con el descuento.

AlfaBeta no busca por droga, así que "montelukast" se pasa a marcas (Singulair...)
con el vademécum cargado y con  consultas/alfabeta_marcas.csv  (droga;marca1,marca2).
La app la pide desde el servidor (no desde el celular), una vez por día y por marca.
"""

from __future__ import annotations

import csv
import html as html_mod
import re
import unicodedata
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

BASE = "https://www.alfabeta.net/precio/"
ARCHIVO_MARCAS = Path(__file__).resolve().parent.parent / "consultas" / "alfabeta_marcas.csv"
ESPERA = 6  # segundos
RE_PRECIO = re.compile(r"\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})\s*\|?\s*\((\d{2}/\d{2}/\d{2,4})\)")
RE_AF = re.compile(r"\bAF\b\s*\|?\s*\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})")


@dataclass
class Presentacion:
    nombre: str
    precio: str  # "$ 99.251,08" tal como lo publica AlfaBeta
    fecha: str  # "01/10/26"
    pami_af: str | None = None


@dataclass
class Marca:
    marca: str
    laboratorio: str = ""
    droga: str = ""
    url: str = ""
    presentaciones: list[Presentacion] = field(default_factory=list)


def _sin_tildes(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def slug(marca: str) -> str:
    """"T4 Montpellier" -> "t4-montpellier" (como arma AlfaBeta sus direcciones)."""
    return "-".join(re.findall(r"[a-z0-9]+", _sin_tildes(marca)))


def url(marca: str) -> str:
    return f"{BASE}{slug(marca)}.html"


def texto_de_html(h: str) -> list[str]:
    """El HTML pasado a renglones: una fila/párrafo por renglón y las celdas separadas por " | "."""
    h = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", h)
    h = re.sub(r"(?i)</t[dh]\s*>", " | ", h)
    h = re.sub(r"(?i)<\s*(br|/tr|/li|/p|/div|/h\d|/table|tr|li|p|div|h\d|table)\b[^>]*>", "\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html_mod.unescape(h).replace("\xa0", " ")
    renglones = []
    for r in h.split("\n"):
        r = re.sub(r"\s+", " ", r).strip(" |")
        r = re.sub(r"(\s*\|\s*)+", " | ", r)
        if r:
            renglones.append(r)
    return renglones


def _limpiar_presentacion(t: str) -> str:
    t = re.sub(r"^[\s\-•·|*]+|[\s\-•·|*]+$", "", t)
    return re.sub(r"\s+", " ", t)


def leer_pagina(h: str, marca: str = "") -> Marca:
    """Saca de la página de AlfaBeta las presentaciones, precios, fecha y PAMI AF."""
    renglones = texto_de_html(h)
    m = Marca(marca=marca.upper(), url=url(marca) if marca else "")
    # Nombre y laboratorio: el renglón que empieza con la marca ("SINGULAIR Organon Arg.").
    if marca:
        clave = _sin_tildes(marca)
        for r in renglones:
            if _sin_tildes(r).startswith(clave + " ") and "precio" not in _sin_tildes(r) and not RE_PRECIO.search(r):
                resto = r[len(marca):].strip(" |-")
                if resto and len(resto) < 60:
                    m.laboratorio = resto
                    break
    actual: Presentacion | None = None
    en_pami = False
    for i, r in enumerate(renglones):
        p = RE_PRECIO.search(r)
        if p:
            nombre = _limpiar_presentacion(r[:p.start()])
            if not nombre and i > 0:
                nombre = _limpiar_presentacion(renglones[i - 1])
            actual = Presentacion(nombre=nombre, precio="$ " + p.group(1), fecha=p.group(2))
            m.presentaciones.append(actual)
            en_pami = False
            continue
        if actual is None:
            continue
        sin = _sin_tildes(r)
        if "pami" in sin:
            en_pami = True
        elif "ioma" in sin:
            en_pami = False
        af = RE_AF.search(r)
        if af and en_pami and actual.pami_af is None:
            actual.pami_af = "$ " + af.group(1)
            en_pami = False
    return m


def pedir(marca: str) -> Marca | None:
    """Trae la página de la marca. None si AlfaBeta no la tiene o no contesta."""
    req = urllib.request.Request(url(marca), headers={"User-Agent": "Mozilla/5.0 (asistente-mostrador)"})
    try:
        with urllib.request.urlopen(req, timeout=ESPERA) as r:
            h = r.read().decode("utf-8", "replace")
    except Exception:
        return None
    m = leer_pagina(h, marca)
    return m if m.presentaciones else None


# ---------------------------------------------------------------- droga -> marcas

def marcas_guardadas(archivo: Path = ARCHIVO_MARCAS) -> dict[str, list[str]]:
    """consultas/alfabeta_marcas.csv:  droga;marca1,marca2"""
    salida: dict[str, list[str]] = {}
    if not archivo.exists():
        return salida
    with archivo.open(encoding="utf-8-sig") as f:
        for fila in csv.reader(f, delimiter=";"):
            if len(fila) >= 2 and fila[0].strip() and not fila[0].startswith("#") and fila[0].strip().lower() != "droga":
                salida[_sin_tildes(fila[0].strip())] = [x.strip() for x in fila[1].split(",") if x.strip()]
    return salida


def marcas_para(consulta: str, vademecum: list | None = None, guardadas: dict | None = None,
                maximo: int = 4) -> list[str]:
    """"montelukast" -> ["Singulair", ...]; "singulair" -> ["singulair"] (ya es una marca)."""
    q = _sin_tildes(consulta).strip()
    if not q:
        return []
    guardadas = marcas_guardadas() if guardadas is None else guardadas
    marcas: list[str] = []
    for droga, lista in guardadas.items():
        if q == droga or (len(q) >= 5 and droga.startswith(q)):
            marcas += [x for x in lista if x not in marcas]
    for c in vademecum or []:
        droga = _sin_tildes(getattr(c, "droga", "") or "")
        if len(q) >= 5 and re.search(r"(^|[\s+,])" + re.escape(q), droga):
            nombre = (getattr(c, "producto", "") or "").split(" ")[0].strip()
            if nombre and nombre.title() not in marcas:
                marcas.append(nombre.title())
    return marcas[:maximo] if marcas else [consulta.strip()]


def resumen(m: Marca, droga: str = "") -> str:
    """Igual al ejemplo de Edu:
    Montelukast en AlfaBeta, marca Singulair (Organon), precios del 01/10/26:
    • 10 mg x 30 comp.: $99.251,08 · PAMI AF $35.537,67
    """
    fechas = sorted({p.fecha for p in m.presentaciones})
    cabeza = (f"**{droga.capitalize()}** en AlfaBeta, marca " if droga else "En AlfaBeta, marca ")
    cabeza += f"**{m.marca.title()}**" + (f" ({m.laboratorio})" if m.laboratorio else "")
    cabeza += f", precios del {' y '.join(fechas)}:" if fechas else ":"
    lineas = [f"- {p.nombre}: **{p.precio}**" + (f" · PAMI AF **{p.pami_af}**" if p.pami_af else " · sin PAMI")
              for p in m.presentaciones]
    return cabeza + "\n" + "\n".join(lineas)
