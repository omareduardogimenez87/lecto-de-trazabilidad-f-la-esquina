from lector import padron


def test_consulta_por_codigo_sin_datos_personales():
    clave = "clave-de-prueba"
    datos = {"listas": {"OSDOP": [padron.codigo("25333620", clave)], "Cobertura especial": [padron.codigo("25333620", clave)]}}
    assert padron.consultar(datos, "25.333.620", clave) == ["OSDOP", "Cobertura especial"]
    assert padron.consultar(datos, "11111111", clave) == []
    assert padron.consultar(datos, "25333620", "otra-clave") == []


def test_dni_de_la_pregunta():
    assert padron.dni_de_la_pregunta("dni 25.333.620") == "25333620"
    assert padron.dni_de_la_pregunta("osdop 25333620") == "25333620"
    assert padron.dni_de_la_pregunta("7793742001673") is None


def test_isspse_por_dni():
    assert padron.dni_de_la_pregunta("isspse 20868328") == "20868328"
    assert padron.dni_de_la_pregunta("issp 20868328") == "20868328"
    assert padron.dni_de_la_pregunta("ISSP 20.868.328") == "20868328"
    assert "ISSPSE" in padron.leer().get("listas", {})
