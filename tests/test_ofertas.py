"""Ofertas OTC del Excel y lector de código de barras de Consultas."""

import io
from datetime import date
from pathlib import Path

import numpy as np
import zxingcpp
from PIL import Image
from streamlit.testing.v1 import AppTest

from lector import ofertas
from lector.imagen import leer_codigos_de_producto

APP = str(Path(__file__).resolve().parent.parent / "app.py")
LISTA = ofertas.leer()
HOY = date(2026, 11, 24)


def foto_ean(codigo: str) -> Image.Image:
    img = zxingcpp.write_barcode_to_image(zxingcpp.create_barcode(codigo, zxingcpp.BarcodeFormat.EAN13), scale=3)
    gris = np.asarray(img)
    lienzo = np.full((gris.shape[0] + 80, gris.shape[1] + 80), 255, dtype=np.uint8)
    lienzo[40:-40, 40:-40] = gris
    return Image.fromarray(lienzo)


def test_lee_el_excel():
    assert len(LISTA) > 80
    tafirol = ofertas.por_codigo(LISTA, "7798140257998")[0]
    assert tafirol.producto == "TAFIROL DUO" and tafirol.descuento == 0.5 and tafirol.precio == 6635
    assert tafirol.hasta == date(2026, 12, 7)


def test_calcula_lo_que_paga_el_cliente():
    tafirol = ofertas.por_codigo(LISTA, "7798140257998")[0]
    assert tafirol.paga_el_cliente() == 3317.5
    assert "paga **$ 3.317,50**" in ofertas.ficha(tafirol, HOY)
    dos_por_uno = ofertas.por_codigo(LISTA, "7798140258445")[0]
    assert dos_por_uno.oferta == "2x1" and dos_por_uno.paga_el_cliente() == 5835
    assert "llevando 2" in ofertas.ficha(dos_por_uno, HOY)


def test_sin_precio_no_inventa():
    aspirina = ofertas.por_codigo(LISTA, "7793640002673")[0]
    assert aspirina.precio is None and ofertas.SIN_PRECIO in ofertas.ficha(aspirina, HOY)


def test_vencida():
    o = LISTA[0]
    assert o.vigencia(HOY) == "vigente" and o.vigencia(date(2026, 12, 8)) == "vencida"
    assert "vencida" in ofertas.ficha(o, date(2026, 12, 8))


def test_busca_por_nombre_y_codigo():
    assert any("TAFIROL" in o.producto for o in ofertas.buscar(LISTA, "tafirol"))
    assert ofertas.buscar(LISTA, "07798140257998")  # GTIN-14 del DataMatrix
    assert not ofertas.buscar(LISTA, "1234567890128")


def test_lee_el_codigo_de_barras_de_la_foto():
    assert leer_codigos_de_producto(foto_ean("7798140257998")) == ["7798140257998"]


def test_la_app_responde_con_la_foto():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    caja = next(t for t in at.text_input if t.key == "consulta_txt")
    caja.input("tafirol duo").run()
    assert any("TAFIROL DUO" in m.value for m in at.markdown)
    caja.input("1234567890128").run()
    assert any(ofertas.NO_CARGADO in i.value for i in at.info)
