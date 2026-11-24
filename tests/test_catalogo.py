"""Catálogo de productos (producto, categoría y marca) en Consultas."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from lector import catalogo

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PRODUCTOS = catalogo.leer()


def test_lee_el_excel_sin_repetidos():
    assert len(PRODUCTOS) > 1000
    claves = [(p.sku, p.nombre) for p in PRODUCTOS]
    assert len(claves) == len(set(claves))


def test_busca_por_marca_categoria_y_codigo():
    assert all(p.marca == "Head & Shoulders" for p in catalogo.buscar(PRODUCTOS, "head shoulders"))
    assert catalogo.buscar(PRODUCTOS, "dermocosmética")
    assert catalogo.buscar(PRODUCTOS, "0000055085")[0].sku == "0000055085"


def test_tolera_errores():
    assert catalogo.buscar(PRODUCTOS, "garnir")
    assert not catalogo.buscar(PRODUCTOS, "zzzqqq")


def test_la_app_muestra_el_catalogo():
    at = AppTest.from_file(APP, default_timeout=60).run()
    next(t for t in at.text_input if t.key == "consulta_txt").input("head shoulders"); at.button(key="btn_buscar").click().run()
    assert not at.exception
    assert any("Head & Shoulders" in m.value for m in at.markdown)


def test_clinal_no_trae_rexona_clinical():
    from lector import catalogo
    assert not [p for p in catalogo.buscar(catalogo.leer(), "clinal") if "REXONA" in p.nombre.upper()]
