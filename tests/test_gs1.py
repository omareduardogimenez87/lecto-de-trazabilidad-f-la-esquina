"""Pruebas automáticas del intérprete de códigos.

Correr con:  python -m pytest
Usan textos de ejemplo (no fotos), para no subir imágenes al repositorio.
"""

from lector.gs1 import fecha_gs1, fecha_texto, gtin_es_valido, parsear_gs1, parsear_texto


def test_gtin_valido():
    assert gtin_es_valido("07796285298739")
    assert gtin_es_valido("07795312020770")
    assert not gtin_es_valido("07796295300531")  # un 8 leído como 9
    assert not gtin_es_valido("123")


def test_fechas():
    assert fecha_gs1("280229") == "29/02/2028"
    assert fecha_gs1("280600") == "30/06/2028"  # día 00 = fin de mes
    assert fecha_texto("VEN: 30/06/2028") == "30/06/2028"
    assert fecha_texto("V 06/28") == "30/06/2028"
    assert fecha_texto("VTO.: 10/2028") == "31/10/2028"
    assert fecha_texto("Cad./Vto./Exp.:(17) 29/02/28") == "29/02/2028"


def test_datamatrix_con_parentesis():
    l = parsear_gs1("(01)07795312020770(21)11185T9C59E11T(17)280229(10)6F950A")
    assert (l.gtin, l.serie, l.lote, l.vencimiento) == ("07795312020770", "11185T9C59E11T", "6F950A", "29/02/2028")
    assert l.gtin_valido


def test_datamatrix_crudo_con_separador():
    l = parsear_gs1("0107796285298739" "216717047054\x1d" "17280630" "104975D")
    assert (l.gtin, l.serie, l.lote, l.vencimiento) == ("07796285298739", "6717047054", "4975D", "30/06/2028")


def test_texto_lot_ven():
    l = parsear_texto("(01)07796285298739\n(21)6717047054\nLOT:4975D\nVEN:30/06/2028")
    assert (l.gtin, l.serie, l.lote, l.vencimiento) == ("07796285298739", "6717047054", "4975D", "30/06/2028")


def test_texto_l_v_e():
    l = parsear_texto("L 508960A1\nV 31/12/2027\nE 05/12/2025\n(21) H02P5FZE17S\n(01) 07790375001209")
    assert (l.gtin, l.serie, l.lote) == ("07790375001209", "H02P5FZE17S", "508960A1")
    assert (l.vencimiento, l.elaboracion) == ("31/12/2027", "05/12/2025")


def test_texto_sin_rotulos_novo_nordisk():
    l = parsear_texto("GTIN/No. de Serie/Elab./Vence/Lote:\n(01)07798058930969\n(21) 0524578959\n01/2026\n06/2028\nVT6NM06")
    assert (l.gtin, l.serie, l.lote) == ("07798058930969", "0524578959", "VT6NM06")
    assert (l.vencimiento, l.elaboracion) == ("30/06/2028", "31/01/2026")


def test_texto_rotulos_a_la_izquierda_jj():
    l = parsear_texto("GTIN: 07795314027029\nN° Serie: 130924633687\nVTO.: 10/2028\nLOTE: 2240299")
    assert (l.gtin, l.serie, l.lote, l.vencimiento) == ("07795314027029", "130924633687", "2240299", "31/10/2028")


def test_ocr_con_parentesis_mal_leido():
    # El OCR leyó ")" como "9": igual debe encontrar el GTIN correcto.
    l = parsear_texto("(01907798058930969")
    assert l.gtin == "07798058930969"


def test_gtin_partido_en_dos_lineas():
    l = parsear_texto("(01)07796285\n300531\n(21) 2848974076\nVto: 31/10/2027\nL: 1702")
    assert (l.gtin, l.serie, l.lote, l.vencimiento) == ("07796285300531", "2848974076", "1702", "31/10/2027")
