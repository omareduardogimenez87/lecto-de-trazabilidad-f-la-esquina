"""Padrón OSDOP: ¿el DNI figura en OSDOP, OSDOP Monotributo o Cobertura especial?

En el repo NO hay nombres, domicilios, fechas ni enfermedades: solo un código (HMAC-SHA256 con
una clave secreta) de cada DNI, en consultas/padron_osdop.json. La clave va en Secrets como
padron_clave. Sin la clave no se puede saber qué DNI hay en el archivo.
Se arma con herramientas/armar_padron.py a partir de los Excel del mes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from pathlib import Path

ARCHIVO = Path(__file__).resolve().parent.parent / "consultas" / "padron_osdop.json"
LISTAS = ("OSDOP", "OSDOP Monotributo", "Cobertura especial", "ISSPSE")


def codigo(dni: str, clave: str) -> str:
    dni = re.sub(r"\D", "", str(dni)).lstrip("0")
    return hmac.new(clave.encode(), dni.encode(), hashlib.sha256).hexdigest()[:20]


def leer(archivo: Path = ARCHIVO) -> dict:
    """Junta todos los consultas/padron_*.json (OSDOP, ISSPSE...). Con archivo distinto, solo ese."""
    rutas = sorted(archivo.parent.glob("padron_*.json")) if archivo == ARCHIVO else [archivo]
    junto: dict = {"listas": {}, "meses": {}}
    for ruta in rutas:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        for nombre, codigos in datos.get("listas", {}).items():
            junto["listas"][nombre] = codigos
            junto["meses"][nombre] = datos.get("mes", "")
        junto.setdefault("mes", datos.get("mes", ""))
    return junto if junto["listas"] else {}


def dni_de_la_pregunta(pregunta: str) -> str | None:
    """"dni 25333620" u "osdop 25.333.620" -> "25333620". Solo si dice dni u osdop."""
    texto = pregunta.lower()
    if "dni" not in texto and "osdop" not in texto and "isspse" not in texto:
        return None
    m = re.search(r"\b(\d{1,2}\.?\d{3}\.?\d{3})\b", texto)
    return m.group(1).replace(".", "") if m else None


def consultar(padron: dict, dni: str, clave: str) -> list[str]:
    """Las listas en las que figura el DNI (vacía si no figura)."""
    c = codigo(dni, clave)
    return [nombre for nombre in LISTAS if c in set(padron.get("listas", {}).get(nombre, []))]
