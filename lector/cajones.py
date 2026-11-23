"""¿En qué cajón está? Lee consultas/CAJONES_corregido.xlsx y busca aunque esté mal escrito.

Formato del Excel (hoja 1): la primera columna es el cajón ("CAJON 1-A") y las
siguientes, lo que hay adentro. Si hay una hoja "Cambios" con la columna
"Estado" = "A confirmar", esos nombres se muestran con ⚠️.
El Excel se reemplaza subiéndolo con el mismo nombre (ver README).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

from .consultas import normalizar

ARCHIVO = Path(__file__).resolve().parent.parent / "consultas" / "CAJONES_corregido.xlsx"
VERIFICAR = "verificá la presentación exacta"

# Palabras que no sirven para identificar un producto.
GENERICAS = {
    "amp", "comp", "iny", "y", "de", "con", "x", "mg", "g", "1g", "2g", "gotas", "comun", "ninos", "cajon",
    "esta", "donde", "en", "que", "el", "la", "los", "las", "hay", "busco", "buscar", "un", "una",
}


@dataclass
class Item:
    cajon: str
    nombre: str  # tal como está anotado
    a_confirmar: bool = False

    def palabras(self) -> list[str]:
        return [w for w in re.findall(r"[a-z0-9]+", normalizar(self.nombre)) if w not in GENERICAS]


def leer(archivo: Path = ARCHIVO) -> list[Item]:
    from openpyxl import load_workbook

    libro = load_workbook(archivo, read_only=True)
    dudosos = set()
    for hoja in libro.worksheets[1:]:
        filas = list(hoja.iter_rows(values_only=True))
        if not filas:
            continue
        enc = [normalizar(str(c or "")).strip() for c in filas[0]]
        if "estado" in enc and any("quedo" in e for e in enc):
            i_estado, i_quedo = enc.index("estado"), next(i for i, e in enumerate(enc) if "quedo" in e)
            for f in filas[1:]:
                if len(f) > max(i_estado, i_quedo) and normalizar(str(f[i_estado] or "")).startswith("a confirmar"):
                    dudosos.add(normalizar(str(f[i_quedo] or "")).strip())
    items = []
    for fila in libro.worksheets[0].iter_rows(values_only=True):
        if not fila or not fila[0] or not normalizar(str(fila[0])).strip().startswith("cajon"):
            continue
        cajon = re.sub(r"\s+", " ", str(fila[0])).strip()
        for celda in fila[1:]:
            nombre = re.sub(r"\s+", " ", str(celda or "")).strip()
            if nombre:
                items.append(Item(cajon, nombre, normalizar(nombre) in dudosos))
    return items


def _parecido(consulta: str, palabra: str) -> float:
    """Qué tanto se parece una palabra buscada a una palabra anotada (0 a 1)."""
    if consulta == palabra:
        return 1.0
    # "diclo" anotado y buscan "diclofenac", o buscan "tafir" y está "tafirol"
    corta, larga = sorted((consulta, palabra), key=len)
    if len(corta) >= 4 and larga.startswith(corta):
        return 0.95
    if len(consulta) < 4:
        return 0.0
    return SequenceMatcher(None, consulta, palabra).ratio()


def buscar(items: list[Item], pregunta: str, minimo: float = 0.85) -> list[Item]:
    """Busca tolerando errores de tipeo y tildes. Devuelve los más parecidos primero."""
    claves = [w for w in re.findall(r"[a-z0-9]+", normalizar(pregunta)) if w not in GENERICAS and len(w) >= 3]
    if not claves:
        return []
    puntajes = []
    for it in items:
        palabras = it.palabras() or [normalizar(it.nombre)]
        pegado = "".join(palabras)  # "amoxi+clavulanico" -> "amoxiclavulanico"
        notas = []
        for c in claves:
            mejor = max([_parecido(c, p) for p in palabras] + [_parecido(c, pegado)])
            notas.append(mejor)
        if min(notas) >= minimo:
            puntajes.append((sum(notas) / len(notas), it))
    puntajes.sort(key=lambda x: -x[0])
    return [it for _, it in puntajes]


def ofertas_del_item(item: Item, lista_ofertas: list, hoy: date, pregunta: str = "") -> list:
    """Ofertas OTC vigentes que parecen ser de ese producto (hay que verificar la presentación).

    Con pregunta, solo las del producto buscado (un cajón puede tener varios productos anotados juntos).
    """
    palabras = [p for p in item.palabras() if len(p) >= 5]
    if pregunta:
        buscadas = [w for w in re.findall(r"[a-z0-9]+", normalizar(pregunta)) if len(w) >= 4]
        palabras = [p for p in palabras if any(_parecido(b, p) >= 0.85 for b in buscadas)]
    encontradas = []
    for o in lista_ofertas:
        if o.vigencia(hoy) != "vigente":
            continue
        primera = (re.findall(r"[a-z0-9]+", normalizar(o.producto)) or [""])[0]
        if any(p == primera or (len(primera) >= 5 and _parecido(p, primera) >= 0.9) for p in palabras):
            encontradas.append(o)
    return encontradas


def mapa(items: list[Item]) -> dict[str, list[Item]]:
    salida: dict[str, list[Item]] = {}
    for it in items:
        salida.setdefault(it.cajon, []).append(it)
    return salida


def texto(item: Item) -> str:
    aviso = " ⚠️ _(nombre a confirmar)_" if item.a_confirmar else ""
    return f"🗄️ **{item.cajon}** → {item.nombre}{aviso}"
