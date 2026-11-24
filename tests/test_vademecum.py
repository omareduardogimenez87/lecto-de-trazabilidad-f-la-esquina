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
