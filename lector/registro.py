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
    return buscar(gtin, serie, archivo) is not None


def buscar(gtin: str, serie: str, archivo=None) -> dict | None:
    """Devuelve el registro anterior de esa unidad (GTIN + serie), si existe."""
    archivo = _destino(archivo)
    if not gtin or not serie:
        return None
    df = leer(archivo)
    previo = df[(df["gtin"] == gtin) & (df["serie"] == serie)]
    if not previo.empty:
        return previo.iloc[-1].to_dict()
    try:
        return _buscar_en_archivo(gtin, serie, archivo)
    except Exception:  # si no se puede leer el archivo, no frenar el guardado
        return None


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


# ------------------------------------------------------------ archivo por mes y borrado de revisados
# Los revisados se pueden "archivar por mes": salen de Revisados y pasan a un archivo de
# ese mes (según la fecha en que se guardaron). En la PC es registros/archivo/AAAA-MM.csv;
# en la nube, una pestaña "Revisados AAAA-MM" en la misma planilla de Google.

PREFIJO_PESTANA = "Revisados "
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
_cache_archivo: dict[str, tuple[float, pd.DataFrame]] = {}


def nombre_del_mes(mes: str) -> str:
    """'2026-11' -> 'noviembre 2026'."""
    anio, m = mes.split("-")
    return f"{MESES[int(m) - 1]} {anio}"


def _mes_de(fecha: str) -> str:
    try:
        return datetime.strptime(fecha, FORMATO_FECHA).strftime("%Y-%m")
    except (TypeError, ValueError):
        return ahora().strftime("%Y-%m")


def _carpeta_archivo(archivo):
    """Dónde van los meses archivados de este registro (carpeta o planilla de Google)."""
    if isinstance(archivo, Path):
        return archivo.parent / "archivo"
    return archivo.spreadsheet


def _destino_mes(lugar, mes: str, crear: bool = False):
    if isinstance(lugar, Path):
        return lugar / f"{mes}.csv"
    titulo = PREFIJO_PESTANA + mes
    for hoja in lugar.worksheets():
        if hoja.title == titulo:
            return hoja
    return lugar.add_worksheet(title=titulo, rows=1000, cols=len(COLUMNAS)) if crear else None


def meses_archivados(archivo=None) -> list[str]:
    """Meses que tienen archivo, del más nuevo al más viejo (ej. ['2026-11', '2026-10'])."""
    lugar = _carpeta_archivo(_destino(archivo))
    if isinstance(lugar, Path):
        meses = [p.stem for p in lugar.glob("*.csv")] if lugar.exists() else []
    else:
        meses = [h.title[len(PREFIJO_PESTANA):] for h in lugar.worksheets() if h.title.startswith(PREFIJO_PESTANA)]
    return sorted(meses, reverse=True)


def leer_mes(mes: str, archivo=None) -> pd.DataFrame:
    """Los revisados archivados de un mes."""
    clave = f"{id(_destino(archivo))}:{mes}"
    guardado = _cache_archivo.get(clave)
    if guardado and time.monotonic() - guardado[0] < SEGUNDOS_CACHE:
        return guardado[1].copy()
    destino = _destino_mes(_carpeta_archivo(_destino(archivo)), mes)
    df = pd.DataFrame(columns=COLUMNAS) if destino is None else leer(destino)
    _cache_archivo[clave] = (time.monotonic(), df)
    return df.copy()


def archivar_revisados(archivo=None) -> dict[str, int]:
    """Pasa todos los revisados a su archivo del mes y los saca de Revisados.
    Devuelve cuántos fueron a cada mes, ej. {'2026-11': 12}."""
    archivo = _destino(archivo)
    df = leer(archivo)
    revisados = df[df["revisado_por"] != ""]
    if revisados.empty:
        return {}
    lugar = _carpeta_archivo(archivo)
    cuantos = {}
    for mes, grupo in revisados.groupby(revisados["fecha_registro"].map(_mes_de)):
        destino = _destino_mes(lugar, mes, crear=True)
        guardar(grupo.to_dict("records"), destino)  # primero se copia al archivo...
        cuantos[mes] = len(grupo)
    _escribir(df[df["revisado_por"] == ""], archivo)  # ...y recién después se saca de Revisados
    _cache_archivo.clear()
    return cuantos


def eliminar_revisados(archivo=None) -> int:
    """Borra para siempre todos los revisados (no toca los pendientes ni los meses archivados)."""
    archivo = _destino(archivo)
    df = leer(archivo)
    quedan = df[df["revisado_por"] == ""]
    _escribir(quedan, archivo)
    return len(df) - len(quedan)


def mes_cerrado(mes: str) -> bool:
    """True si el mes ya terminó (es anterior al mes actual de Argentina)."""
    return mes < ahora().strftime("%Y-%m")


def eliminar_mes(mes: str, archivo=None) -> int:
    """Borra para siempre el archivo de un mes que ya terminó. Devuelve cuántos registros tenía."""
    if not mes_cerrado(mes):
        raise ValueError("Solo se pueden eliminar meses que ya terminaron.")
    lugar = _carpeta_archivo(_destino(archivo))
    destino = _destino_mes(lugar, mes)
    if destino is None:
        return 0
    n = len(leer(destino))
    if isinstance(destino, Path):
        destino.unlink()
    else:
        lugar.del_worksheet(destino)
    _cache_archivo.clear()
    return n


def _buscar_en_archivo(gtin: str, serie: str, archivo) -> dict | None:
    """Busca la unidad también en los meses archivados (para avisar duplicados)."""
    for mes in meses_archivados(archivo):
        df = leer_mes(mes, archivo)
        previo = df[(df["gtin"] == gtin) & (df["serie"] == serie)]
        if not previo.empty:
            return previo.iloc[-1].to_dict()
    return None


# ------------------------------------------------------------ notas u observaciones para mejorar la app
# Cada usuario puede dejar una nota (algo para cambiar o agregar). Solo Omar las ve todas y las borra.
# En la PC: registros/notas.csv · En la nube: pestaña "Notas" de la planilla.

COLUMNAS_NOTAS = ["id", "fecha", "usuario", "nota"]
PESTANA_NOTAS = "Notas"


def _lugar_notas(archivo=None, crear: bool = False):
    archivo = _destino(archivo)
    if isinstance(archivo, Path):
        return archivo.parent / "notas.csv"
    libro = archivo.spreadsheet
    for hoja in libro.worksheets():
        if hoja.title == PESTANA_NOTAS:
            return hoja
    return libro.add_worksheet(title=PESTANA_NOTAS, rows=500, cols=len(COLUMNAS_NOTAS)) if crear else None


def leer_notas(archivo=None) -> pd.DataFrame:
    """Todas las notas, de la más nueva a la más vieja."""
    lugar = _lugar_notas(archivo)
    if lugar is None:
        return pd.DataFrame(columns=COLUMNAS_NOTAS)
    if isinstance(lugar, Path):
        if not lugar.exists():
            return pd.DataFrame(columns=COLUMNAS_NOTAS)
        df = pd.read_csv(lugar, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    else:
        valores = lugar.get_all_values()
        if not valores:
            return pd.DataFrame(columns=COLUMNAS_NOTAS)
        filas = [f + [""] * (len(valores[0]) - len(f)) for f in valores[1:]]
        df = pd.DataFrame(filas, columns=valores[0], dtype=str)
    return df.reindex(columns=COLUMNAS_NOTAS, fill_value="").iloc[::-1].reset_index(drop=True)


def guardar_nota(usuario: str, texto: str, archivo=None) -> dict:
    """Guarda una nota nueva y la devuelve (con su id, para poder mostrarla después)."""
    import uuid

    nota = {"id": uuid.uuid4().hex[:10], "fecha": ahora().strftime(FORMATO_FECHA), "usuario": usuario, "nota": texto.strip()}
    lugar = _lugar_notas(archivo, crear=True)
    if isinstance(lugar, Path):
        lugar.parent.mkdir(parents=True, exist_ok=True)
        nuevo = not lugar.exists()
        with open(lugar, "a", newline="", encoding="utf-8-sig" if nuevo else "utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNAS_NOTAS, delimiter=";")
            if nuevo:
                w.writeheader()
            w.writerow(nota)
    else:
        if lugar.row_values(1) != COLUMNAS_NOTAS:
            lugar.update([COLUMNAS_NOTAS], "A1", value_input_option="RAW")
        lugar.append_rows([[nota[c] for c in COLUMNAS_NOTAS]], value_input_option="RAW")
    return nota


def borrar_nota(id_nota: str, archivo=None) -> None:
    """Borra una nota (cuando Omar ya aplicó el cambio)."""
    lugar = _lugar_notas(archivo)
    if lugar is None:
        return
    df = leer_notas(archivo).iloc[::-1]
    df = df[df["id"] != id_nota]
    if isinstance(lugar, Path):
        df.to_csv(lugar, sep=";", index=False, encoding="utf-8-sig")
    else:
        lugar.clear()
        lugar.update([COLUMNAS_NOTAS] + df.values.tolist(), "A1", value_input_option="RAW")


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
