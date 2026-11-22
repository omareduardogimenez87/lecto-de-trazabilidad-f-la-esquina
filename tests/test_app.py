"""Prueba de humo: la app arranca sin errores y muestra los nombres en orden."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_la_app_arranca():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.title[0].value.endswith("Lector de trazabilidad")


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
