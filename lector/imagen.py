"""Leer una foto: el DataMatrix, el texto (OCR) y la fecha en que se sacó."""

from __future__ import annotations

import os
import re
import shutil
from datetime import datetime

import numpy as np
from PIL import Image, ImageOps

from .gs1 import Lectura, combinar, parsear_gs1, parsear_texto

try:
    import zxingcpp
except ImportError:  # pragma: no cover
    zxingcpp = None

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None

# En Windows, el instalador de Tesseract no lo agrega al PATH. Si no se
# encuentra, lo buscamos en las carpetas donde se instala por defecto.
if pytesseract is not None and shutil.which("tesseract") is None:
    for _ruta in (
        os.environ.get("TESSERACT_CMD", ""),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ):
        if _ruta and os.path.isfile(_ruta):
            pytesseract.pytesseract.tesseract_cmd = _ruta
            break


def abrir(archivo) -> Image.Image:
    """Abre la foto y la endereza según la orientación que guardó el celular."""
    img = Image.open(archivo)
    img.load()
    return ImageOps.exif_transpose(img) or img


# ---------------------------------------------------------------- fecha de la foto

RE_FECHA_NOMBRE = re.compile(r"(20\d{2})(\d{2})(\d{2})[_-]?(?:(\d{2})(\d{2})(\d{2}))?")


def fecha_de_la_foto(img: Image.Image, nombre_archivo: str = "") -> tuple[datetime | None, str]:
    """Devuelve (fecha, de dónde salió).

    1. EXIF: el dato que guarda la cámara al sacar la foto (lo más fiel).
    2. El nombre del archivo, si trae la fecha (ej. IMG_20261120_101530.jpg
       o IMG-20261120-WA0001.jpg de WhatsApp).
    3. Si no hay nada, devuelve None y la app usa la fecha de carga.
    """
    try:
        exif = img.getexif()
        sub = exif.get_ifd(0x8769)  # bloque "Exif" con DateTimeOriginal
        for valor in (sub.get(36867), sub.get(36868), exif.get(306)):
            if valor:
                return datetime.strptime(str(valor).strip()[:19], "%Y:%m:%d %H:%M:%S"), "EXIF de la foto"
    except Exception:
        pass

    m = RE_FECHA_NOMBRE.search(nombre_archivo or "")
    if m:
        a, mes, d, h, mi, s = m.groups()
        try:
            return datetime(int(a), int(mes), int(d), int(h or 0), int(mi or 0), int(s or 0)), "nombre del archivo"
        except ValueError:
            pass
    return None, ""


# ---------------------------------------------------------------- preparación de la imagen

def _sin_marcador(img: Image.Image) -> Image.Image:
    """Pasa a gris y "borra" trazos de marcador verde/fluo dibujados encima."""
    rgb = np.asarray(img.convert("RGB")).astype(int)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    verde = (g > 150) & (g - r > 60) & (g - b > 20)
    gris = np.asarray(img.convert("L")).copy()
    if verde.any():
        gris[verde] = int(np.median(gris))
    return Image.fromarray(gris)


def _variantes(img: Image.Image):
    yield img
    gris = _sin_marcador(img)
    yield gris
    for escala in (1.5, 2):
        yield gris.resize((int(gris.width * escala), int(gris.height * escala)), Image.LANCZOS)


# ---------------------------------------------------------------- DataMatrix

def leer_datamatrix(img: Image.Image) -> list[str]:
    """Busca códigos DataMatrix en la foto y devuelve su contenido."""
    if zxingcpp is None:
        return []
    for v in _variantes(img):
        for binarizador in (zxingcpp.Binarizer.LocalAverage, zxingcpp.Binarizer.GlobalHistogram):
            res = zxingcpp.read_barcodes(
                v,
                formats=zxingcpp.BarcodeFormat.DataMatrix,
                try_rotate=True,
                try_invert=True,
                try_downscale=True,
                binarizer=binarizador,
            )
            textos = [r.text for r in res if r.text]
            if textos:
                return list(dict.fromkeys(textos))  # sin repetidos, en orden
    return []


# ---------------------------------------------------------------- OCR

def ocr_disponible() -> bool:
    """True si Tesseract (el programa de OCR) está instalado y se puede usar."""
    if pytesseract is None:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def leer_texto(img: Image.Image) -> list[str]:
    """Lee el texto impreso. Prueba la imagen normal y la invertida
    (para letras blancas sobre fondo oscuro, como Novo Nordisk o J&J)."""
    if pytesseract is None:
        return []
    gris = _sin_marcador(img)
    # Agrandar la imagen ayuda mucho al OCR con fotos chicas (ej. las de WhatsApp).
    escala = max(1.0, 2400 / gris.width)
    gris = gris.resize((int(gris.width * escala), int(gris.height * escala)), Image.LANCZOS)
    textos = []
    for v in (gris, ImageOps.invert(gris)):
        textos.append(pytesseract.image_to_string(v, config="--psm 11"))
    return textos


# ---------------------------------------------------------------- todo junto

def analizar(img: Image.Image) -> list[Lectura]:
    """Lee una foto y devuelve una lectura por cada envase encontrado.

    Primero intenta con el DataMatrix (exacto). Si no lo encuentra,
    usa el texto impreso (aproximado, hay que revisarlo).
    """
    codigos = leer_datamatrix(img)
    if codigos:
        return [parsear_gs1(c) for c in codigos]

    try:
        textos = leer_texto(img)
    except Exception as e:  # tesseract no instalado, etc.
        lec = Lectura(fuente="Sin lectura")
        lec.avisos.append(f"No se pudo leer el texto: {e}")
        return [lec]
    if not textos:
        lec = Lectura(fuente="Sin lectura")
        lec.avisos.append("No se encontró DataMatrix y el OCR no está instalado")
        return [lec]
    return [combinar([parsear_texto(t) for t in textos])]


# ---------------------------------------------------------------- código de barras (consultas)

def leer_codigos_de_producto(img: Image.Image) -> list[str]:
    """Busca el código de barras del producto (EAN-13, EAN-8, UPC) o el DataMatrix.

    Devuelve los números encontrados (GTIN/EAN), sin repetidos. Del DataMatrix
    se toma solo el GTIN (01).
    """
    if zxingcpp is None:
        return []
    import warnings

    with warnings.catch_warnings():  # zxing-cpp 3 prefiere una tupla; el "|" sirve en la 2 y la 3
        warnings.simplefilter("ignore", DeprecationWarning)
        formatos = (
            zxingcpp.BarcodeFormat.EAN13 | zxingcpp.BarcodeFormat.EAN8 | zxingcpp.BarcodeFormat.UPCA
            | zxingcpp.BarcodeFormat.UPCE | zxingcpp.BarcodeFormat.DataMatrix
        )
    for v in _variantes(img):
        for binarizador in (zxingcpp.Binarizer.LocalAverage, zxingcpp.Binarizer.GlobalHistogram):
            res = zxingcpp.read_barcodes(
                v, formats=formatos, try_rotate=True, try_invert=True, try_downscale=True, binarizer=binarizador
            )
            codigos = []
            for r in res:
                if not r.text:
                    continue
                if r.format == zxingcpp.BarcodeFormat.DataMatrix:
                    gtin = parsear_gs1(r.text).gtin
                    if gtin:
                        codigos.append(gtin)
                else:
                    codigos.append(r.text)
            if codigos:
                return list(dict.fromkeys(codigos))
    return []
