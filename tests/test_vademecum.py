from lector import vademecum


def test_lee_csv_y_busca_por_nombre(tmp_path):
    ruta = tmp_path / "Vademecum_Vale_Salud.csv"
    ruta.write_text("Producto;Laboratorio;Droga;% Desc\nCLINAL, pda.x 25 g;Andrómaco;vit.a+bencetonio;20\n"
                    "TAFIROL 1 G comp.x 8;Genomma;paracetamol;0,4\n", encoding="utf-8")
    lista = vademecum.leer(ruta)
    assert len(lista) == 2
    (c,) = vademecum.buscar(lista, "Clinal")
    assert c.laboratorio == "Andrómaco" and c.porcentaje == "20 %"
    assert vademecum.buscar(lista, "tafirol")[0].porcentaje == "40 %"
    assert vademecum.buscar(lista, "rexona") == []


def test_accion_terapeutica_solo_del_archivo(tmp_path):
    from lector import accion

    archivo = tmp_path / "Accion_Terapeutica.csv"
    archivo.write_text("droga;accion;fuente\npropinox;Antiespasmódico;Alfabeta\n", encoding="utf-8")
    tabla = accion.leer(archivo)
    assert accion.de_la_droga(tabla, "Propinox")["accion"] == "Antiespasmódico"
    assert accion.de_la_droga(tabla, "ibuprofeno") is None  # sin dato: no se inventa
    assert accion.leer(tmp_path / "no_existe.csv") == {}


def test_accion_por_sku_del_catalogo(tmp_path):
    from lector import accion

    archivo = tmp_path / "Accion_Terapeutica.csv"
    archivo.write_text('sku;droga;accion;indicacion;fuente\n0000044525;;Analgésico;"dolores; musculares";web\n', encoding="utf-8")
    tabla = accion.leer(archivo)
    assert accion.del_sku(tabla, "44525")["indicacion"] == "dolores; musculares"
    assert accion.del_sku(tabla, "999") is None
