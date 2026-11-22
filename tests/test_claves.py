from lector import claves


def test_pin(tmp_path):
    archivo = tmp_path / "claves.json"
    assert not claves.tiene_pin("Claudia", archivo)
    claves.crear_pin("Claudia", "4821", archivo)
    assert claves.tiene_pin("Claudia", archivo)
    assert claves.verificar("Claudia", "4821", archivo)
    assert not claves.verificar("Claudia", "0000", archivo)
    assert not claves.verificar("Fernanda", "4821", archivo)
    assert "4821" not in archivo.read_text()  # el PIN no queda escrito


def test_pin_valido():
    assert claves.pin_valido("1234") and claves.pin_valido("123456")
    assert not claves.pin_valido("12") and not claves.pin_valido("12ab")
