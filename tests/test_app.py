"""Prueba de humo: la app arranca sin errores y muestra los nombres en orden."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_la_app_arranca():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("Lector de trazabilidad" in m.value for m in at.markdown)


def test_pide_la_clave_si_esta_configurada():
    at = AppTest.from_file(APP, default_timeout=60)
    at.secrets["clave_acceso"] = "farmacia"
    at.run()
    assert not at.exception and not at.pills  # todavía no se ven los nombres
    at.text_input[0].input("farmacia").run()
    assert not at.exception and at.pills


def test_avisa_si_la_cuenta_de_google_esta_mal():
    at = AppTest.from_file(APP, default_timeout=60)
    at.secrets["planilla_url"] = "https://docs.google.com/spreadsheets/d/x"
    at.secrets["cuenta_google"] = "esto no es json"
    at.run()
    assert not at.exception and at.error and "planilla" in at.error[0].value


def test_registros_sin_columna_estado(tmp_path, monkeypatch):
    from lector import registro

    monkeypatch.setattr(registro, "ARCHIVO", tmp_path / "registros.csv")
    registro.guardar([dict(gtin="07795312020770", serie="A1", lote="L", usuario="Omar", estado="Leído del DataMatrix")])
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.pills[0].set_value("Claudia").run()
    assert not at.exception
    columnas = list(at.tabs[1].dataframe[0].value.columns)
    assert "GTIN" in columnas and "Estado" not in columnas
