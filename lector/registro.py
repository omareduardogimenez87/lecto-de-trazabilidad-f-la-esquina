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
    "revisado_por",  # farmacéutica que lo vio y lo dio por bueno (vacío = pendiente)
    "revisado_el",
]

FORMATO_FECHA = "%d/%m/%Y %H:%M:%S"


def leer(archivo: Path = ARCHIVO) -> pd.DataFrame:
    """Devuelve todos los registros guardados (o una tabla vacía)."""
    if not archivo.exists():
        return pd.DataFrame(columns=COLUMNAS)
    df = pd.read_csv(archivo, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    # Los archivos de versiones anteriores no tienen las columnas nuevas: se agregan vacías.
    return df.reindex(columns=COLUMNAS, fill_value="")


def _escribir(df: pd.DataFrame, archivo: Path) -> None:
    archivo.parent.mkdir(parents=True, exist_ok=True)
    df.reindex(columns=COLUMNAS, fill_value="").to_csv(archivo, sep=";", index=False, encoding="utf-8-sig")


def _migrar(archivo: Path) -> None:
    """Si el archivo es de una versión anterior (otras columnas), lo pasa al formato actual."""
    if not archivo.exists():
        return
    with open(archivo, encoding="utf-8-sig") as f:
        encabezado = f.readline().strip().split(";")
    if encabezado != COLUMNAS:
        _escribir(leer(archivo), archivo)


def marcar_revisados(claves: list[tuple[str, str]], farmaceutica: str, archivo: Path = ARCHIVO) -> int:
    """Marca registros (GTIN + serie) como vistos y aprobados por una farmacéutica."""
    df = leer(archivo)
    elegidos = pd.Series(False, index=df.index)
    for gtin, serie in claves:
        elegidos |= (df["gtin"] == gtin) & (df["serie"] == serie)
    elegidos &= df["revisado_por"] == ""
    df.loc[elegidos, "revisado_por"] = farmaceutica
    df.loc[elegidos, "revisado_el"] = datetime.now().strftime(FORMATO_FECHA)
    _escribir(df, archivo)
    return int(elegidos.sum())


def desmarcar_revisado(gtin: str, serie: str, archivo: Path = ARCHIVO) -> None:
    """Vuelve un registro a pendientes (por si se tildó por error)."""
    df = leer(archivo)
    fila = (df["gtin"] == gtin) & (df["serie"] == serie)
    df.loc[fila, ["revisado_por", "revisado_el"]] = ""
    _escribir(df, archivo)


def ya_registrado(gtin: str, serie: str, archivo: Path = ARCHIVO) -> bool:
    """GTIN + serie identifican una unidad única. Si ya está, es un duplicado."""
    if not gtin or not serie:
        return False
    df = leer(archivo)
    return bool(((df["gtin"] == gtin) & (df["serie"] == serie)).any())


def buscar(gtin: str, serie: str, archivo: Path = ARCHIVO) -> dict | None:
    """Devuelve el registro anterior de esa unidad (GTIN + serie), si existe."""
    if not gtin or not serie:
        return None
    df = leer(archivo)
    previo = df[(df["gtin"] == gtin) & (df["serie"] == serie)]
    return None if previo.empty else previo.iloc[-1].to_dict()


def reemplazar(fila: dict, archivo: Path = ARCHIVO) -> None:
    """Borra el registro anterior de esa unidad (GTIN + serie) y guarda el nuevo."""
    df = leer(archivo)
    df = df[~((df["gtin"] == fila["gtin"]) & (df["serie"] == fila["serie"]))]
    _escribir(df, archivo)
    guardar([fila], archivo)


def guardar(filas: list[dict], archivo: Path = ARCHIVO) -> int:
    """Agrega filas al final del CSV. Devuelve cuántas guardó."""
    archivo.parent.mkdir(parents=True, exist_ok=True)
    _migrar(archivo)
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
