"""Pruebas de la detección de fotos dudosas, con imágenes generadas (sin fotos reales)."""

import numpy as np
from PIL import Image, ImageFilter

from lector.calidad import ESTADO_OK, ESTADO_OTRA_FOTO, ESTADO_REVISAR, estado, medir
from lector.gs1 import Lectura


def _tablero():
    """Un dibujo con bordes bien marcados, parecido a un DataMatrix."""
    rng = np.random.default_rng(0)
    celdas = rng.integers(0, 2, (40, 30)) * 255
    return Image.fromarray(np.kron(celdas, np.ones((40, 40))).astype("uint8"))


def test_foto_nitida_y_desenfocada():
    nitida = medir(_tablero())
    borrosa = medir(_tablero().filter(ImageFilter.GaussianBlur(12)))
    assert not nitida.desenfocada
    assert borrosa.desenfocada


def test_estados():
    calidad = medir(_tablero())
    dm = Lectura(gtin="07795312020770", serie="11185T9C59E11T", fuente="DataMatrix")
    assert estado(dm, calidad)[0] == ESTADO_OK
    ocr = Lectura(gtin="07796285298739", serie="6717047054", fuente="Texto (OCR)")
    assert estado(ocr, calidad)[0] == ESTADO_REVISAR
    sin_gtin = Lectura(serie="2848974076", fuente="Texto (OCR)")
    assert estado(sin_gtin, calidad)[0] == ESTADO_OTRA_FOTO
    gtin_mal = Lectura(gtin="07796295300531", serie="2848974076", fuente="Texto (OCR)")
    assert estado(gtin_mal, calidad)[0] == ESTADO_OTRA_FOTO
