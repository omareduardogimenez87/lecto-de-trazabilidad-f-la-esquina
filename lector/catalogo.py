"""Catálogo de productos: lee consultas/Ventas_Producto_Categoria_Marcas.xlsx.

Columnas: SKU ID, Producto, Categoría, Marca. Sirve para saber de qué marca o
categoría es un producto y qué productos hay de una marca. El Excel se
reemplaza subiéndolo con el mismo nombre (ver README).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .cajones import _parecido
from .consultas import normalizar, palabras

ARCHIVO = Path(__file__).resolve().parent.parent / "consultas" / "Ventas_Producto_Categoria_Marcas.xlsx"

# Palabras de la pregunta que no ayudan a encontrar el producto.
IGNORAR = {"marca", "marcas", "categoria", "categorias", "producto", "productos", "tenemos", "venden", "vendemos"}


@dataclass
class Producto:
    sku: str
    nombre: str
    categoria: str
    marca: str

    def buscable(self) -> list[str]:
        return re.findall(r"[a-z0-9]+", normalizar(f"{self.nombre} {self.categoria} {self.marca}"))


def leer(archivo: Path = ARCHIVO) -> list[Producto]:
    from openpyxl import load_workbook

    filas = list(load_workbook(archivo, read_only=True).worksheets[0].iter_rows(values_only=True))
    if not filas:
        return []
    enc = [normalizar(str(c or "")).strip() for c in filas[0]]

    def col(clave):
        return next((i for i, e in enumerate(enc) if clave in e), None)

    i_sku, i_prod, i_cat, i_marca = col("sku"), col("producto"), col("categor"), col("marca")
    if i_prod is None:
        return []

    def dato(f, i):
        return str(f[i] or "").strip() if i is not None and i < len(f) else ""

    vistos, productos = set(), []
    for f in filas[1:]:
        if not f or not dato(f, i_prod):
            continue
        p = Producto(dato(f, i_sku), dato(f, i_prod), dato(f, i_cat), dato(f, i_marca))
        if (p.sku, p.nombre) not in vistos:  # sin filas repetidas
            vistos.add((p.sku, p.nombre))
            productos.append(p)
    return productos


def buscar(productos: list[Producto], pregunta: str) -> list[Producto]:
    """Todos los productos que tienen todas las palabras buscadas (tolera tildes y errores chicos)."""
    numeros = re.findall(r"\d{6,10}", pregunta)
    if numeros:  # código interno (SKU), con o sin ceros adelante
        return [p for p in productos for n in numeros if p.sku.lstrip("0") == n.lstrip("0")]
    claves = [w for w in palabras(pregunta) if w not in IGNORAR and len(w) >= 3]
    if not claves:
        return []
    exactos = [p for p in productos if all(any(w in b for b in p.buscable()) for w in claves)]
    if exactos:
        return exactos
    # Sin coincidencia exacta: probar con errores de tipeo ("garnir", "shampo").
    return [
        p for p in productos
        if all(max((_parecido(w, b) for b in p.buscable()), default=0) >= 0.85 for w in claves if len(w) >= 4)
        and any(len(w) >= 4 for w in claves)
    ]


def resumen(encontrados: list[Producto]) -> tuple[Counter, Counter]:
    return Counter(p.categoria for p in encontrados), Counter(p.marca for p in encontrados)


def categorias(productos: list[Producto]) -> Counter:
    return Counter(p.categoria for p in productos)
