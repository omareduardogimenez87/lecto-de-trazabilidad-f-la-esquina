"""Vademécums de cobertura cargados como archivo (uno por obra social; por ahora Vale Salud).

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


def fuentes(carpeta: Path = CARPETA) -> dict[str, tuple[str, Path]]:
    """Cada archivo consultas/Vademecum_<Obra_social>.csv/.xlsx es una fuente de cobertura.

    Clave = primera palabra del nombre en minúscula ("Vademecum_Vale_Salud.csv" -> "vale").
    """
    salida = {}
    for ruta in sorted(carpeta.glob("Vademecum_*")):
        if ruta.suffix.lower() in (".csv", ".xlsx"):
            nombre = ruta.stem.removeprefix("Vademecum_").replace("_", " ").strip()
            salida.setdefault(normalizar(nombre.split()[0]), (nombre, ruta))
    return salida


@dataclass
class Cobertura:
    producto: str
    laboratorio: str
    droga: str
    porcentaje: str
    codigo: str = ""
    marca: str = ""  # nombre comercial solo ("BRONAX CB"), sin la presentación


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
            c_pres, c_cod = col("presentacion"), col("barra", "ean")
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
            nombre = " ".join(x for x in (dato(f, c_prod), dato(f, c_pres)) if x)
            fila = Cobertura(nombre, dato(f, c_lab), dato(f, c_dro), pct, dato(f, c_cod), dato(f, c_prod))
            if fila not in salida:  # el archivo trae renglones repetidos
                salida.append(fila)
    return salida


def buscar(lista: list[Cobertura], medicamento: str, limite: int = 15) -> list[Cobertura]:
    numeros = re.findall(r"\d{8,14}", medicamento)
    if numeros:
        return [c for c in lista if any(c.codigo.lstrip("0") == n.lstrip("0") for n in numeros)][:limite]
    claves = [w for w in re.findall(r"[a-z0-9]+", normalizar(medicamento)) if len(w) >= 2]
    if not claves:
        return []

    def coincide(c: Cobertura) -> bool:
        palabras = re.findall(r"[a-z0-9]+", normalizar(f"{c.producto} {c.droga}"))
        return all(any(p.startswith(x) or (len(x) >= 5 and _parecido(x, p) >= 0.9)
                       for p in palabras for x in {w, SINONIMOS.get(w, w)}) for w in claves)

    return [c for c in lista if coincide(c)][:limite]


# Cómo se lo pide en el mostrador -> cómo figura en el vademécum.
SINONIMOS = {"t4": "levotiroxina", "t3": "liotironina", "levo": "levotiroxina", "amoxi": "amoxicilina"}

# Abreviaturas de la presentación -> forma farmacéutica, para los filtros.
FORMAS = {
    "comp": "Comprimidos", "cap": "Cápsulas", "caps": "Cápsulas", "gts": "Gotas", "jbe": "Jarabe",
    "susp": "Suspensión", "sus": "Suspensión", "cr": "Crema", "crema": "Crema", "gel": "Gel", "pda": "Pomada",
    "iny": "Inyectable", "amp": "Ampollas", "sol": "Solución", "sob": "Sobres", "sobres": "Sobres",
    "parches": "Parches", "sup": "Supositorios", "colirio": "Colirio", "spray": "Spray", "emuls": "Emulsión",
    "pvo": "Polvo", "polvo": "Polvo", "lata": "Lata", "brick": "Brick", "brik": "Brick", "botella": "Botella",
}


def marca_corta(c: Cobertura) -> str:
    """"IBUPIRAC 600 MG" -> "IBUPIRAC" (la marca sin la dosis)."""
    palabras = (c.marca or c.producto).split()
    corte = next((i for i, w in enumerate(palabras) if i and w[0].isdigit()), len(palabras))
    return " ".join(palabras[:corte])


def dosis(c: Cobertura) -> str:
    """"LEVOTIROXINA 100 mcg comp.x 50" -> "100 mcg" (no cuenta los ml del frasco)."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(mcg|µg|ug|mg|g|ui|%)(?![a-z])", c.producto.lower())
    return f"{m.group(1)} {m.group(2).replace('µg', 'mcg').replace('ug', 'mcg')}" if m else ""


def forma(c: Cobertura) -> str:
    """"... comp.rec.x 30" -> "Comprimidos"."""
    for w in re.findall(r"[a-z]+", normalizar(c.producto[len(c.marca):])):
        if w in FORMAS:
            return FORMAS[w]
    return ""


def variantes(lista: list[Cobertura]) -> dict[str, list[str]]:
    """Valores distintos de cada filtro (solo los filtros con 2 o más opciones)."""
    campos = {"Marca": marca_corta, "Dosis": dosis, "Presentación": forma, "Laboratorio": lambda c: c.laboratorio}
    salida = {}
    for nombre, f in campos.items():
        valores = []
        for c in lista:
            v = f(c)
            if v and v not in valores:
                valores.append(v)
        if len(valores) >= 2:
            if nombre == "Dosis":
                valores.sort(key=lambda v: (v.split()[1], float(v.split()[0].replace(",", "."))))
            salida[nombre] = valores
    return salida


def filtrar(lista: list[Cobertura], elegidos: dict[str, list[str]]) -> list[Cobertura]:
    campos = {"Marca": marca_corta, "Dosis": dosis, "Presentación": forma, "Laboratorio": lambda c: c.laboratorio}
    return [c for c in lista if all(not v or campos[k](c) in v for k, v in elegidos.items())]


def vocabulario(lista: list[Cobertura]) -> list[str]:
    """Nombres comerciales y drogas, para sugerir cuando algo está mal escrito."""
    palabras = set()
    for c in lista:
        nombre = c.producto.split()[0] if c.producto else ""
        if len(nombre) >= 4:
            palabras.add(nombre.upper())
        for droga in re.split(r"[+,]", c.droga):
            droga = droga.strip()
            if len(droga) >= 4 and not droga.endswith("."):
                palabras.add(droga.lower())
    return sorted(palabras)


def sugerencias(vocab: list[str], texto: str, n: int = 5) -> list[str]:
    """"klinal" -> ["CLINAL"]. Compara sin tildes ni mayúsculas."""
    from difflib import get_close_matches

    normal = {normalizar(v): v for v in vocab}
    buscado = normalizar(texto).strip()
    if len(buscado) < 3 or buscado in normal:
        return []
    return [normal[m] for m in get_close_matches(buscado, list(normal), n=n, cutoff=0.7)]
