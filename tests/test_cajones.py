"""¿En qué cajón está? Búsqueda tolerante a errores sobre el Excel de cajones."""

from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from lector import cajones, ofertas

APP = str(Path(__file__).resolve().parent.parent / "app.py")
ITEMS = cajones.leer()
HOY = date(2026, 11, 24)


def cajones_de(pregunta):
    return [(it.cajon, it.nombre) for it in cajones.buscar(ITEMS, pregunta)]


def test_lee_el_excel():
    assert ("CAJON 2-A", "GLIBENCLAMIDA") in [(i.cajon, i.nombre) for i in ITEMS]
    assert any(i.a_confirmar and i.nombre == "TAFIROL Y GENIOL 1 G" for i in ITEMS)


def test_encuentra_aunque_este_mal_escrito():
    assert ("CAJON 2-A", "GLIBENCLAMIDA") in cajones_de("glibencamida")
    assert ("CAJON 5-A", "DEXAMETASONA AMP / DICLOFENAC AMP") in cajones_de("dexametazona")
    assert ("CAJON 2-B", "OMEPRAZOL / GRIPABEN/NEXT") in cajones_de("omeprasol")
    assert ("CAJON 1-A", "AMOXI+CLAVULANICO") in cajones_de("amoxicilina clavulánico")
    assert ("CAJON 1-C", "DICLO 75 Y 100") in cajones_de("diclofenac")


def test_no_confunde_productos_distintos():
    assert all("BETAMETASONA" not in n for _, n in cajones_de("dexametasona"))
    assert not cajones_de("osde")


def test_ofertas_del_producto_del_cajon():
    tafirol = cajones.buscar(ITEMS, "tafirol")[0]
    assert any(o.producto.startswith("TAFIROL") for o in cajones.ofertas_del_item(tafirol, ofertas.leer(), HOY, "tafirol"))
    buscapina = next(i for i in ITEMS if i.nombre.startswith("BUSCAPINA"))
    assert not cajones.ofertas_del_item(buscapina, ofertas.leer(), HOY, "dexametasona")


def test_la_app_dice_el_cajon():
    at = AppTest.from_file(APP, default_timeout=60).run()
    caja = next(t for t in at.text_input if t.key == "consulta_txt")
    at.text_input(key="consulta_txt").input("glibencamida"); at.button(key="btn_buscar").click().run()
    assert not at.exception
    assert any("CAJON 2-A" in m.value for m in at.markdown)
    at.text_input(key="consulta_txt").input("tafirol"); at.button(key="btn_buscar").click().run()
    assert any(cajones.VERIFICAR in c.value for c in at.caption)
