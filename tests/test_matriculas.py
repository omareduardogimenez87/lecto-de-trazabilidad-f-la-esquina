from lector import matriculas


def test_busca_por_matricula_y_por_nombre():
    medicos = matriculas.leer()
    assert len(medicos) > 3000
    assert matriculas.es_consulta("matricula 2911") and matriculas.es_consulta("dr abalos")
    assert not matriculas.es_consulta("ibuprofeno")
    (m,) = matriculas.buscar(medicos, "matricula 2911")
    assert m.nombre == "ABALOS ALEJANDRO G"
    assert any(x.matricula == "2911" for x in matriculas.buscar(medicos, "dr abalos alejandro"))
