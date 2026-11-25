"""Consultar con foto (📷 del Asistente): qué producto se ve en la foto.

1. Si se ve el código de barras o el DataMatrix, se usa ese número (exacto).
2. Si no, se lee el texto del envase (OCR) y se buscan palabras que estén
   cargadas en la app (ofertas, cajones, catálogo, vademécum). La palabra
   conocida que más aparece en el envase es la que se busca.
No usa IA ni internet.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from .consultas import normalizar

# Palabras de los envases que no sirven para identificar el producto.
COMUNES = {
    "comprimidos", "comp", "capsulas", "caps", "blandas", "recubiertos", "jarabe", "gotas", "crema", "solucion",
    "venta", "libre", "bajo", "receta", "archivada", "industria", "argentina", "laboratorio", "laboratorios",
    "contiene", "cada", "contenido", "neto", "lote", "vence", "vencimiento", "elab", "elaborado", "directora",
    "director", "tecnico", "tecnica", "farmaceutica", "farmaceutico", "certificado", "ministerio", "salud",
    "especialidad", "medicinal", "autorizada", "consulte", "medico", "lea", "atentamente", "prospecto",
    "mantener", "alcance", "ninos", "conservar", "temperatura", "ambiente", "lugar", "seco", "fresco",
    "para", "con", "sin", "adultos", "forte", "plus", "rapida", "accion", "oral", "uso", "externo", "envase",
    "unidades", "sobres", "pomo", "frasco", "presentacion", "formula", "nueva", "original", "x",
}


def palabras(texto: str) -> list[str]:
    """Palabras de 4 letras o más, en minúsculas y sin tildes."""
    return [p for p in re.findall(r"[a-zñ]{4,}", normalizar(texto)) if p not in COMUNES]


def vocabulario(nombres: Iterable[str]) -> set[str]:
    """Palabras de los productos cargados en la app (ofertas, cajones, catálogo, vademécum)."""
    salida: set[str] = set()
    for n in nombres:
        salida.update(palabras(n or ""))
    return salida


def producto_en_la_foto(textos: Iterable[str], conocidas: set[str], maximo: int = 3) -> list[str]:
    """Palabras conocidas que aparecen en el texto leído, la más repetida (y más larga) primero."""
    cuenta = Counter(p for t in textos for p in palabras(t or "") if p in conocidas)
    orden = sorted(cuenta, key=lambda p: (-cuenta[p], -len(p), p))
    return orden[:maximo]
