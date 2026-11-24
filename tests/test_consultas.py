"""Consultas rápidas: busca en el archivo .md y sigue sus reglas (sin IA)."""

from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from lector import consultas

APP = str(Path(__file__).resolve().parent.parent / "app.py")
BASE = consultas.leer()
EN_PERIODO = date(2026, 11, 24)  # martes, dentro del horario cargado
FUERA = date(2026, 12, 5)


def test_lee_categorias_y_periodo():
    etiquetas = [s.etiqueta for s in BASE.secciones]
    assert "💳 Obras sociales" in etiquetas
    assert not any("Reglas" in e or "Registro" in e for e in etiquetas)
    assert BASE.periodo == (date(2026, 11, 21), date(2026, 11, 27))


def test_busca_sin_importar_tildes_ni_mayusculas():
    r = consultas.buscar(BASE, "galeno", EN_PERIODO)
    assert any("❌ No" in t for _, t in r["datos"])
    assert consultas.buscar(BASE, "PREVENCIÓN token", EN_PERIODO)["datos"]
    assert consultas.buscar(BASE, "prevencion token", EN_PERIODO)["datos"]


def test_lo_dudoso_dice_a_confirmar():
    r = consultas.buscar(BASE, "vale salud", EN_PERIODO)
    assert any(consultas.A_CONFIRMAR in t for _, t in r["datos"])


def test_sin_dato_no_inventa():
    r = consultas.buscar(BASE, "zzzqqq", EN_PERIODO)
    assert not r["datos"] and not r["hoy"] and not r["salud"]


def test_consultas_de_salud_van_a_la_farmaceutica():
    for q in ("dosis de ibuprofeno", "¿para qué sirve el Dutide?", "lo puede tomar una embarazada"):
        r = consultas.buscar(BASE, q, EN_PERIODO)
        assert r["salud"] and not r["datos"]


def test_quien_trabaja_hoy():
    r = consultas.buscar(BASE, "quién trabaja hoy", EN_PERIODO)
    columna, gente = r["hoy"]
    assert columna == "Mar 24"
    assert ("Yessi Guzmán", "Mostrador", "15:30–00") in gente
    assert all(p != "Germán Ibarra" for p, _, _ in gente)  # no figura ese día


def test_horario_fuera_del_periodo():
    r = consultas.buscar(BASE, "horario", FUERA)
    assert r["sin_horario"] and not r["hoy"]
    r = consultas.buscar(BASE, "yessi", FUERA)
    assert r["sin_horario"]
    assert not any("15:30" in t for _, t in r["datos"])


def test_promo_vencida():
    r = consultas.buscar(BASE, "andromaco avanter", date(2026, 12, 1))
    assert any("vencida" in t for _, t in r["datos"])
    r = consultas.buscar(BASE, "andromaco avanter", EN_PERIODO)
    assert not any("vencida" in t for _, t in r["datos"])
    promos = next(s for s in BASE.secciones if s.numero == "7")
    assert "vencida" in consultas.marcar_promos(promos.contenido, date(2026, 12, 1))


def test_la_app_muestra_consultas():
    at = AppTest.from_file(APP, default_timeout=60).run()
    caja = next(t for t in at.text_input if t.key == "consulta_txt")
    at.text_input(key="consulta_txt").input("osde"); at.button(key="btn_buscar").click().run()
    assert not at.exception
    assert any("OSDE" in m.value for m in at.markdown)
    at.text_input(key="consulta_txt").input("zzzqqq"); at.button(key="btn_buscar").click().run()
    assert any(consultas.SIN_DATO in i.value for i in at.info)
    at.text_input(key="consulta_txt").input(""); at.button(key="btn_buscar").click().run()
    cat = next(p for p in at.pills if p.key == "consulta_cat")
    nombres = {o.split(" ", 1)[-1] if not o[0].isalpha() else o for o in cat.options}
    assert nombres == {"Ofertas OTC", "Cajones"}
    cat.set_value("🗄️ Cajones").run()
    assert not at.exception and any("CAJON 2-A" in m.value for m in at.markdown)
    at.text_input(key="consulta_txt").input("alvetide"); at.button(key="btn_buscar").click().run()  # el PICC se sigue encontrando escribiendo
    assert any("Alvetide" in m.value for m in at.markdown)
    at.text_input(key="consulta_txt").input("andromaco"); at.button(key="btn_buscar").click().run()  # las promos se siguen encontrando escribiendo
    assert any("Andrómaco" in m.value for m in at.markdown)


def test_medicamento_de_cobertura():
    from lector.consultas import medicamento_de_cobertura
    assert medicamento_de_cobertura("ibuprofeno cobertura") == "ibuprofeno"
    assert medicamento_de_cobertura("Tafirol 1g cobertura pami") == "Tafirol 1g"
    assert medicamento_de_cobertura("ibuprofeno") is None
