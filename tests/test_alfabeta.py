from lector import alfabeta

SINGULAIR = """<html><head><title>SINGULAIR PRECIO - DESCUENTO PAMI</title></head><body>
<p>Ultima Actualización: 24/11/2026</p>
<h1><img src="x.png"> SINGULAIR <span>Organon Arg.</span></h1>
<p><i>montelukast</i> <i>Antiasmático</i></p>
<ul><li>10 mg comp.x 30 <b>$101.236,10</b> (02/11/26)</li><li>Importado</li></ul>
<table><tr><th>PAMI</th></tr><tr><td>AF <b>$36.828,50</b></td></tr></table>
<table><tr><th>IOMA</th><th>Cobertura Monto Fijo</th></tr><tr><td>OS <b>$20.280,40</b></td><td>AF <b>$80.955,70</b></td></tr></table>
<ul><li>niños 4 mg comp.mast.x30 <b>$104.118,74</b> (02/11/26)</li><li>Importado</li></ul>
<table><tr><th>PAMI</th></tr><tr><td>AF <b>$29.589,32</b></td></tr></table>
<table><tr><th>IOMA</th><th>Cobertura Monto Fijo</th></tr><tr><td>OS <b>$19.145,87</b></td><td>AF <b>$84.972,87</b></td></tr></table>
<ul><li>niños 5 mg comp.mast.x30 <b>$105.119,48</b> (02/11/26)</li></ul>
<table><tr><td>IOMA</td></tr><tr><td>OS $19.463,34</td><td>AF $85.656,14</td></tr></table>
</body></html>"""

CLINAL = """<h2>CLINAL Andrómaco</h2><p><i>vit.a+bencetonio,cl.+asoc.</i></p>
<table><tr><th>pda.x 25 g</th><th>$27.533,93</th><th>(02/11/26)</th></tr></table>"""


def test_lee_presentaciones_precios_y_pami_af():
    m = alfabeta.leer_pagina(SINGULAIR, "singulair")
    assert m.laboratorio == "Organon Arg."
    assert [(p.nombre, p.precio, p.fecha, p.pami_af) for p in m.presentaciones] == [
        ("10 mg comp.x 30", "$ 101.236,10", "02/11/26", "$ 36.828,50"),
        ("niños 4 mg comp.mast.x30", "$ 104.118,74", "02/11/26", "$ 29.589,32"),
        ("niños 5 mg comp.mast.x30", "$ 105.119,48", "02/11/26", None),  # solo IOMA: no se toma como PAMI
    ]


def test_precio_en_celdas_y_sin_pami():
    m = alfabeta.leer_pagina(CLINAL, "clinal")
    assert [(p.nombre, p.precio, p.pami_af) for p in m.presentaciones] == [("pda.x 25 g", "$ 27.533,93", None)]
    assert m.laboratorio == "Andrómaco"


def test_resumen_como_el_ejemplo():
    m = alfabeta.leer_pagina(SINGULAIR, "singulair")
    r = alfabeta.resumen(m, "montelukast")
    assert r.startswith("**Montelukast** en AlfaBeta, marca **Singulair** (Organon Arg.), precios del 02/11/26:")
    assert "- 10 mg comp.x 30: **$ 101.236,10** · PAMI AF **$ 36.828,50**" in r


def test_droga_a_marcas_y_slug():
    guardadas = {"montelukast": ["Singulair"]}
    assert alfabeta.marcas_para("Montelukast", [], guardadas) == ["Singulair"]
    assert alfabeta.marcas_para("singulair", [], guardadas) == ["singulair"]
    assert alfabeta.slug("T4 Montpellier") == "t4-montpellier"
    assert "montelukast" in alfabeta.marcas_guardadas()
