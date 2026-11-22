"""Prueba de humo: la app arranca sin errores y muestra los nombres en orden."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_la_app_arranca():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.title[0].value.endswith("Lector de trazabilidad")
