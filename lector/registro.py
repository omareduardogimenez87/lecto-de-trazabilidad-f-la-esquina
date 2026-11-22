"""Guardar las lecturas en el registro y exportarlas a Excel.

Hay dos lugares posibles donde se guarda:
- En la PC (app con Windows): un archivo CSV en la carpeta `registros/`. El CSV usa
  ";" como separador y UTF-8 con BOM, que es lo que espera el Excel en español.
- En la nube (app con Android): una planilla de Google Sheets, porque en la nube
  los archivos locales se borran cada vez que la app se reinicia. Se activa
  llamando a `usar_planilla()` (lo hace app.py si encuentra la planilla configurada).
"""

from __future__ import annotations

import csv
import io
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    from zoneinfo import ZoneInfo

    ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
except Exception:  # pragma: no cover - sin datos de zona horaria: hora de la compu
    ZONA = None

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

# Planilla de Google (hoja) donde guardar en la nube. None = guardar en el CSV.
_planilla = None
_cache: tuple[float, pd.DataFrame] | None = None
SEGUNDOS_CACHE = 15  # para no pedirle a Google la planilla entera en cada toque


def ahora() -> datetime:
    """Fecha y hora de Argentina (los servidores de la nube usan la hora de otro país)."""
    if ZONA is None:
        return datetime.now()
    return datetime.now(ZONA).replace(tzinfo=None)


def usar_planilla(hoja) -> None:
    """Desde ahora se guarda en esta hoja de Google Sheets (un objeto Worksheet de gspread)."""
    global _planilla, _cache
    _planilla, _cache = hoja, None


def en_la_nube() -> bool:
    return _planilla is not None


def _destino(archivo):
    if archivo is not None:
        return archivo
    return _planilla if _planilla is not None else ARCHIVO


# ------------------------------------------------------------ Google Sheets

def _leer_planilla(hoja) -> pd.DataFrame:
    global _cache
    if hoja is _planilla and _cache and time.monotonic() - _cache[0] < SEGUNDOS_CACHE:
        return _cache[1].copy()
    valores = hoja.get_all_values()
    if not valores:
        df = pd.DataFrame(columns=COLUMNAS)
    else:
        encabezado, filas = valores[0], valores[1:]
        filas = [f + [""] * (len(encabezado) - len(f)) for f in filas]
        df = pd.DataFrame(filas, columns=encabezado, dtype=str).reindex(columns=COLUMNAS, fill_value="")
    if hoja is _planilla:
        _cache = (time.monotonic(), df)
    return df.copy()


def _olvidar_cache() -> None:
    global _cache
    _cache = None


def _escribir_planilla(df: pd.DataFrame, hoja) -> None:
    df = df.reindex(columns=COLUMNAS, fill_value="").fillna("").astype(str)
    hoja.clear()
    # RAW: se guarda tal cual, como texto (así el GTIN no pierde el 0 de adelante).
    hoja.update([COLUMNAS] + df.values.tolist(), "A1", value_input_option="RAW")
    _olvidar_cache()


def _agregar_planilla(filas: list[list[str]], hoja) -> None:
    primera = hoja.row_values(1)
    if primera != COLUMNAS:
        if primera:  # planilla de otra versión: se pasa al formato actual
            _escribir_planilla(_leer_planilla(hoja), hoja)
        else:
            hoja.update([COLUMNAS], "A1", value_input_option="RAW")
    hoja.append_rows(filas, value_input_option="RAW")
    _olvidar_cache()


# ------------------------------------------------------------ CSV y funciones comunes

def leer(archivo=None) -> pd.DataFrame:
    """Devuelve todos los registros guardados (o una tabla vacía)."""
    archivo = _destino(archivo)
    if not isinstance(archivo, Path):
        return _leer_planilla(archivo)
    if not archivo.exists():
        return pd.DataFrame(columns=COLUMNAS)
    df = pd.read_csv(archivo, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    # Los archivos de versiones anteriores no tienen las columnas nuevas: se agregan vacías.
    return df.reindex(columns=COLUMNAS, fill_value="")


def _escribir(df: pd.DataFrame, archivo) -> None:
    if not isinstance(archivo, Path):
        return _escribir_planilla(df, archivo)
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


def marcar_revisados(claves: list[tuple[str, str]], farmaceutica: str, archivo=None) -> int:
    """Marca registros (GTIN + serie) como vistos y aprobados por una farmacéutica."""
    archivo = _destino(archivo)
    df = leer(archivo)
    elegidos = pd.Series(False, index=df.index)
    for gtin, serie in claves:
        elegidos |= (df["gtin"] == gtin) & (df["serie"] == serie)
    elegidos &= df["revisado_por"] == ""
    df.loc[elegidos, "revisado_por"] = farmaceutica
    df.loc[elegidos, "revisado_el"] = ahora().strftime(FORMATO_FECHA)
    _escribir(df, archivo)
    return int(elegidos.sum())


def desmarcar_revisado(gtin: str, serie: str, archivo=None) -> None:
    """Vuelve un registro a pendientes (por si se tildó por error)."""
    archivo = _destino(archivo)
    df = leer(archivo)
    fila = (df["gtin"] == gtin) & (df["serie"] == serie)
    df.loc[fila, ["revisado_por", "revisado_el"]] = ""
    _escribir(df, archivo)


def ya_registrado(gtin: str, serie: str, archivo=None) -> bool:
    """GTIN + serie identifican una unidad única. Si ya está, es un duplicado."""
    archivo = _destino(archivo)
    if not gtin or not serie:
        return False
    df = leer(archivo)
    return bool(((df["gtin"] == gtin) & (df["serie"] == serie)).any())


def buscar(gtin: str, serie: str, archivo=None) -> dict | None:
    """Devuelve el registro anterior de esa unidad (GTIN + serie), si existe."""
    archivo = _destino(archivo)
    if not gtin or not serie:
        return None
    df = leer(archivo)
    previo = df[(df["gtin"] == gtin) & (df["serie"] == serie)]
    return None if previo.empty else previo.iloc[-1].to_dict()


def reemplazar(fila: dict, archivo=None) -> None:
    """Borra el registro anterior de esa unidad (GTIN + serie) y guarda el nuevo."""
    archivo = _destino(archivo)
    df = leer(archivo)
    df = df[~((df["gtin"] == fila["gtin"]) & (df["serie"] == fila["serie"]))]
    _escribir(df, archivo)
    guardar([fila], archivo)


def guardar(filas: list[dict], archivo=None) -> int:
    """Agrega filas al final del registro. Devuelve cuántas guardó."""
    archivo = _destino(archivo)
    momento = ahora().strftime(FORMATO_FECHA)
    filas = [{c: str(fila.get(c, "") or "") for c in COLUMNAS} for fila in filas]
    for fila in filas:
        fila["fecha_registro"] = fila["fecha_registro"] or momento
    if not isinstance(archivo, Path):
        _agregar_planilla([[f[c] for c in COLUMNAS] for f in filas], archivo)
        return len(filas)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    _migrar(archivo)
    nuevo = not archivo.exists()
    with open(archivo, "a", newline="", encoding="utf-8-sig" if nuevo else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, delimiter=";", extrasaction="ignore")
        if nuevo:
            w.writeheader()
        w.writerows(filas)
    return len(filas)


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def rango_de_fechas(fechas) -> str:
    """Ej.: 'desde el domingo 22/11 al viernes 27/11' (o 'del domingo 22/11' si es un solo día).
    `fechas` son textos con el formato de FORMATO_FECHA; los que no se entienden se ignoran."""
    dias = pd.to_datetime(pd.Series(list(fechas), dtype=str), format=FORMATO_FECHA, errors="coerce").dropna()
    if dias.empty:
        return ""
    desde, hasta = dias.min(), dias.max()
    texto = lambda d: f"{DIAS[d.weekday()]} {d:%d/%m}"
    if desde.date() == hasta.date():
        return f"del {texto(desde)}"
    return f"desde el {texto(desde)} al {texto(hasta)}"


VIOLETA = "8B5A9E"  # el mismo violeta de la app (.streamlit/config.toml)


def a_excel(df: pd.DataFrame, titulo: str = "") -> bytes:
    """Convierte la tabla a un archivo Excel (.xlsx) en memoria, para descargar.
    Si hay título, va en la primera fila, destacado en violeta, y la tabla empieza en la fila 3."""
    from openpyxl.styles import Alignment, Font, PatternFill

    buffer = io.BytesIO()
    inicio = 2 if titulo else 0  # filas que quedan arriba de la tabla
    with pd.ExcelWriter(buffer, engine="openpyxl") as xl:
        df.to_excel(xl, index=False, sheet_name="Registros", startrow=inicio)
        hoja = xl.sheets["Registros"]
        for i, col in enumerate(df.columns, start=1):
            ancho = max([len(str(col))] + [len(str(v)) for v in df[col].head(200)]) + 2
            hoja.column_dimensions[hoja.cell(row=1, column=i).column_letter].width = min(ancho, 45)
        # Todo como texto: así Excel no muestra el GTIN o la serie como 7,79531E+12 ni borra el 0 de adelante.
        for fila in hoja.iter_rows(min_row=inicio + 2):
            for celda in fila:
                celda.number_format = "@"
        if titulo:
            ultima = max(len(df.columns), 1)
            hoja.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ultima)
            celda = hoja.cell(row=1, column=1, value=titulo)
            celda.font = Font(size=16, bold=True, color="FFFFFF")
            celda.fill = PatternFill("solid", fgColor=VIOLETA)
            celda.alignment = Alignment(horizontal="left", vertical="center", indent=1)
            hoja.row_dimensions[1].height = 30
            for c in range(1, len(df.columns) + 1):  # títulos de columna en violeta clarito
                hoja.cell(row=inicio + 1, column=c).fill = PatternFill("solid", fgColor="E9DDEE")
        hoja.freeze_panes = hoja.cell(row=inicio + 2, column=1)
    return buffer.getvalue()
