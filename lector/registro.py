"""Guardar las lecturas en el archivo de registros (CSV) y exportarlas a Excel.

El CSV usa ";" como separador y codificación UTF-8 con BOM, que es lo que
espera el Excel en español: así se abre con doble clic y se ven bien las tildes.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path

import pandas as pd

CARPETA = Path(__file__).resolve().parent.parent / "registros"
ARCHIVO = CARPETA / "registros.csv"

COLUMNAS = [
    "fecha_registro",  # cuándo se guardó en el sistema
    "fecha_foto",  # cuándo se sacó la foto
    "origen_fecha_foto",  # EXIF de la foto / nombre del archivo / fecha de carga
    "usuario",
    "rol",
    "sucursal",
    "archivo_foto",  # nombre original de la foto
    "gtin",
    "serie",
    "lote",
    "vencimiento",
    "elaboracion",
    "fuente",  # DataMatrix o Texto (OCR)
    "estado",  # Leído del DataMatrix / Revisado por el usuario / Corregido a mano
    "gtin_valido",
    "avisos",
]

FORMATO_FECHA = "%d/%m/%Y %H:%M:%S"


def leer(archivo: Path = ARCHIVO) -> pd.DataFrame:
    """Devuelve todos los registros guardados (o una tabla vacía)."""
    if not archivo.exists():
        return pd.DataFrame(columns=COLUMNAS)
    return pd.read_csv(archivo, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)


def ya_registrado(gtin: str, serie: str, archivo: Path = ARCHIVO) -> bool:
    """GTIN + serie identifican una unidad única. Si ya está, es un duplicado."""
    if not gtin or not serie:
        return False
    df = leer(archivo)
    return bool(((df["gtin"] == gtin) & (df["serie"] == serie)).any())


def guardar(filas: list[dict], archivo: Path = ARCHIVO) -> int:
    """Agrega filas al final del CSV. Devuelve cuántas guardó."""
    archivo.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not archivo.exists()
    ahora = datetime.now().strftime(FORMATO_FECHA)
    with open(archivo, "a", newline="", encoding="utf-8-sig" if nuevo else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, delimiter=";", extrasaction="ignore")
        if nuevo:
            w.writeheader()
        for fila in filas:
            fila = {c: fila.get(c, "") for c in COLUMNAS}
            fila["fecha_registro"] = fila["fecha_registro"] or ahora
            w.writerow(fila)
    return len(filas)


def a_excel(df: pd.DataFrame) -> bytes:
    """Convierte la tabla a un archivo Excel (.xlsx) en memoria, para descargar."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as xl:
        df.to_excel(xl, index=False, sheet_name="Registros")
        hoja = xl.sheets["Registros"]
        for i, col in enumerate(df.columns, start=1):
            ancho = max([len(str(col))] + [len(str(v)) for v in df[col].head(200)]) + 2
            hoja.column_dimensions[hoja.cell(row=1, column=i).column_letter].width = min(ancho, 45)
        hoja.freeze_panes = "A2"
    return buffer.getvalue()
