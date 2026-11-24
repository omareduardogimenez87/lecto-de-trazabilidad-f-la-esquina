"""Vademécum de cobertura cargado como archivo (por ahora Vale Salud).

Si existe consultas/Vademecum_Vale_Salud.xlsx (o .csv), el asistente muestra el % directamente
("CLINAL, pda.x 25 g · Andrómaco · 20 %"). Lee la primera hoja y reconoce solas las columnas de
producto, laboratorio y porcentaje por el nombre del encabezado. Se reemplaza subiendo el archivo
nuevo con el mismo nombre.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from .cajones import _parecido
from .consultas import normalizar

CARPETA = Path(__file__).resolve().parent.parent / "consultas"
ARCHIVOS = {"vale": ["Vademecum_Vale_Salud.xlsx", "Vademecum_Vale_Salud.csv"]}


@dataclass
class Cobertura:
    producto: str
    laboratorio: str
    droga: str
    porcentaje: str


def archivo(fuente: str) -> Path | None:
    return next((CARPETA / n for n in ARCHIVOS.get(fuente, []) if (CARPETA / n).exists()), None)


def _filas(ruta: Path) -> list[list[str]]:
    if ruta.suffix == ".csv":
        with ruta.open(encoding="utf-8-sig", newline="") as f:
            muestra = f.read(4096)
            f.seek(0)
            dialecto = csv.Sniffer().sniff(muestra, delimiters=";,\t")
            return [[c.strip() for c in fila] for fila in csv.reader(f, dialecto)]
    from openpyxl import load_workbook

    hoja = load_workbook(ruta, read_only=True, data_only=True).worksheets[0]
    return [["" if c is None else str(c).strip() for c in fila] for fila in hoja.iter_rows(values_only=True)]


def leer(ruta: Path) -> list[Cobertura]:
    filas = _filas(ruta)
    for i, fila in enumerate(filas[:30]):
        enc = [normalizar(c) for c in fila]

        def col(*claves):
            return next((j for j, n in enumerate(enc) if any(k in n for k in claves)), None)

        c_prod = col("producto", "nombre", "medicamento", "comercial", "descripcion")
        c_pct = col("%", "porcentaje", "descuento", "cobertura", "bonif")
        if c_prod is not None and c_pct is not None:
            c_lab, c_dro = col("laboratorio", "lab"), col("droga", "monodroga", "principio")
            break
    else:
        return []

    def dato(f, j):
        return f[j] if j is not None and j < len(f) else ""

    salida = []
    for f in filas[i + 1:]:
        if dato(f, c_prod):
            pct = dato(f, c_pct)
            try:  # 0.2 o 20 -> "20 %"
                v = float(pct.replace("%", "").replace(",", "."))
                pct = f"{round(v * 100 if v <= 1 else v):g} %"
            except ValueError:
                pass
            salida.append(Cobertura(dato(f, c_prod), dato(f, c_lab), dato(f, c_dro), pct))
    return salida


def buscar(lista: list[Cobertura], medicamento: str, limite: int = 10) -> list[Cobertura]:
    claves = [w for w in re.findall(r"[a-z0-9]+", normalizar(medicamento)) if len(w) >= 2]
    if not claves:
        return []

    def coincide(c: Cobertura) -> bool:
        palabras = re.findall(r"[a-z0-9]+", normalizar(f"{c.producto} {c.droga}"))
        return all(any(p.startswith(w) or (len(w) >= 5 and _parecido(w, p) >= 0.9) for p in palabras) for w in claves)

    return [c for c in lista if coincide(c)][:limite]
