from datetime import date

from lector import ofertas, precios

HOY = date(2026, 11, 24)


def test_lee_la_lista_de_precios_de_la_quincena():
    lista = precios.leer(anio=2026)
    assert len(lista) > 200
    fortisip = ofertas.buscar(lista, "4008976681861")[0]
    assert fortisip.precio == 65456 and round(fortisip.paga_el_cliente(), 2) == 42546.40
    assert fortisip.desde == date(2026, 11, 16) and fortisip.hasta == date(2026, 11, 30)
    assert fortisip.vigencia(HOY) == "vigente"


def test_panales_con_precio_de_oferta_solo():
    o = ofertas.buscar(precios.leer(anio=2026), "7794626013362")[0]
    texto = ofertas.ficha(o, HOY)
    assert "Precio de oferta" in texto and "$ 18.499,90" in texto


def test_porcentaje_sin_precio_y_busqueda_por_rubro():
    lista = precios.leer(anio=2026)
    always = [o for o in lista if o.producto == "ALWAYS"][0]
    assert always.descuento == 0.4 and always.precio is None
    assert ofertas.buscar(lista, "desodorantes rexona")
