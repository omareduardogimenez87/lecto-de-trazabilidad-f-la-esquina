"""Foto en miniatura de un producto (para el Asistente).

De dónde sale, en este orden:
1. Una foto propia en  consultas/fotos/  con el código de barras o el SKU como nombre
   (ej. 7796285289362.jpg o 0000035384.png). Es lo más seguro.
2. La tienda web de la farmacia (farmacialaesquina.com.ar), si responde con la foto
   del producto. Se pide una sola vez por producto y, si no contesta rápido, no se muestra nada.
Si no hay foto, no se muestra nada (la búsqueda sigue igual).
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

CARPETA = Path(__file__).resolve().parent.parent / "consultas" / "fotos"
TIENDA = "https://farmacialaesquina.com.ar"
EXTENSIONES = (".jpg", ".jpeg", ".png", ".webp")
ESPERA = 3  # segundos


def foto_local(*codigos: str, carpeta: Path = CARPETA) -> Path | None:
    """La foto cargada a mano en consultas/fotos/, buscando por código de barras o SKU."""
    for c in codigos:
        c = (c or "").strip()
        if not c:
            continue
        for variante in dict.fromkeys((c, c.lstrip("0"))):
            for ext in EXTENSIONES:
                ruta = carpeta / f"{variante}{ext}"
                if ruta.exists():
                    return ruta
    return None


def _pedir(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (asistente-mostrador)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=ESPERA) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def url_de_la_respuesta(datos) -> str | None:
    """Toma la primera imagen de la respuesta de búsqueda de la tienda (formato VTEX)."""
    if not isinstance(datos, list):
        return None
    for prod in datos:
        for item in (prod or {}).get("items") or []:
            for img in item.get("images") or []:
                url = img.get("imageUrl")
                if isinstance(url, str) and url.startswith("http"):
                    return url
    return None


def foto_de_la_tienda(ean: str = "", nombre: str = "") -> str | None:
    """Pide la foto a la tienda web por código de barras y, si no, por nombre. None si no hay."""
    consultas = []
    if ean:
        consultas.append("fq=" + urllib.parse.quote(f"alternateIds_Ean:{ean}"))
    if nombre:
        consultas.append("ft=" + urllib.parse.quote(nombre))
    for q in consultas:
        try:
            url = url_de_la_respuesta(_pedir(f"{TIENDA}/api/catalog_system/pub/products/search?{q}&_from=0&_to=0"))
        except Exception:
            return None  # la tienda no contesta: no insistir con el nombre
        if url:
            return url
    return None
