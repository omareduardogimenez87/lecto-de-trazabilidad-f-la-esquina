from lector import foto_consulta as fc


def test_encuentra_el_producto_en_el_texto_del_envase():
    conocidas = fc.vocabulario(["TAFIROL FORTE", "IBUPROFENO 400 comp", "GENIOL"])
    texto = "TAFIROL\nForte 650 mg\nComprimidos x 30\nVenta libre\nIndustria Argentina\nTafirol"
    assert fc.producto_en_la_foto([texto], conocidas)[0] == "tafirol"


def test_no_inventa_si_no_hay_palabras_conocidas():
    conocidas = fc.vocabulario(["TAFIROL", "GENIOL"])
    assert fc.producto_en_la_foto(["Comprimidos venta libre industria argentina"], conocidas) == []


def test_ignora_tildes_y_palabras_comunes():
    conocidas = fc.vocabulario(["Buscapina Duo comprimidos"])
    assert "comprimidos" not in conocidas
    assert fc.producto_en_la_foto(["BUSCAPÍNA comprimidos"], conocidas) == ["buscapina"]


def test_miniatura_local_por_codigo_o_sku(tmp_path):
    from lector import miniaturas
    (tmp_path / "35384.png").write_bytes(b"x")
    assert miniaturas.foto_local("", "0000035384", carpeta=tmp_path).name == "35384.png"
    assert miniaturas.foto_local("7796285289362", carpeta=tmp_path) is None


def test_miniatura_lee_la_respuesta_de_la_tienda():
    from lector import miniaturas
    datos = [{"items": [{"images": [{"imageUrl": "https://x.vteximg.com.br/a.jpg"}]}]}]
    assert miniaturas.url_de_la_respuesta(datos) == "https://x.vteximg.com.br/a.jpg"
    assert miniaturas.url_de_la_respuesta({"error": 1}) is None
