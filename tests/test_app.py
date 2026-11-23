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


def _item(n, estado, gtin="07795312020770", serie=None):
    import io

    from PIL import Image

    foto = io.BytesIO()
    Image.new("RGB", (10, 10), "white").save(foto, "PNG")
    return dict(
        id=f"id{n}", foto=foto.getvalue(), archivo_foto=f"foto{n}.jpg", fecha_foto="22/11/2026 10:00:00",
        origen_fecha_foto="prueba", estado=estado, motivos=[], nitidez=100.0,
        lectura=dict(gtin=gtin, serie=serie or f"S{n}", lote="L", vencimiento="", elaboracion="", fuente="DataMatrix"),
    )


def test_guardar_varias_fotos_menos_las_malas(tmp_path, monkeypatch):
    from lector import registro
    from lector.calidad import ESTADO_OK, ESTADO_OTRA_FOTO

    monkeypatch.setattr(registro, "ARCHIVO", tmp_path / "registros.csv")
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["items"] = [_item(1, ESTADO_OK), _item(2, ESTADO_OK), _item(3, ESTADO_OTRA_FOTO, gtin="123")]
    at.run()
    at.pills[0].set_value("Omar").run()
    boton = next(b for b in at.button if b.key == "guardar_todas")
    assert boton.label == "💾 Guardar 2 foto(s)"
    aviso = next(w.value for w in at.warning if "excepto" in w.value)
    assert "excepto 1" in aviso and "foto3.jpg" in aviso
    boton.click().run()
    assert not at.exception
    assert sorted(registro.leer()["serie"]) == ["S1", "S2"]
    assert [it["archivo_foto"] for it in at.session_state["items"]] == ["foto3.jpg"]


def test_avatares_en_los_botones_y_nombre_solo_en_el_registro(tmp_path, monkeypatch):
    from lector import registro
    from lector.calidad import ESTADO_OK

    monkeypatch.setattr(registro, "ARCHIVO", tmp_path / "registros.csv")
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["items"] = [_item(1, ESTADO_OK)]
    at.run()
    assert at.pills[0].format_func("Claudia") == "👱🏻‍♀️ Claudia"
    at.pills[0].set_value("Omar").run()
    next(b for b in at.button if b.key == "guardar_id1").click().run()
    assert list(registro.leer()["usuario"]) == ["Omar"]


def test_revisados_sin_columna_estado(tmp_path, monkeypatch):
    from lector import registro

    monkeypatch.setattr(registro, "ARCHIVO", tmp_path / "registros.csv")
    registro.guardar([dict(gtin="07795312020770", serie="A1", usuario="Omar", estado="Leído del DataMatrix")])
    registro.marcar_revisados([("07795312020770", "A1")], "Claudia")
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.pills[0].set_value("Claudia").run()
    columnas = list(at.tabs[2].dataframe[0].value.columns)
    assert "Revisado por" in columnas and "Estado" not in columnas


def test_seleccionar_todo_y_pasar_a_revisados(tmp_path, monkeypatch):
    from lector import registro

    monkeypatch.setattr(registro, "ARCHIVO", tmp_path / "registros.csv")
    registro.guardar([dict(gtin="07795312020770", serie=s, usuario="Omar") for s in ("A1", "A2", "A3")])
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.pills[0].set_value("Fernanda").run()
    at.checkbox(key="todos_pend").check().run()
    boton = at.button(key="pasar_revisados")
    assert boton.label == "✅ Pasar 3 a Revisados"
    boton.click().run()
    assert not at.exception
    assert (registro.leer()["revisado_por"] == "Fernanda").all()


def test_archivar_y_eliminar_desde_revisados(tmp_path, monkeypatch):
    from lector import registro

    monkeypatch.setattr(registro, "ARCHIVO", tmp_path / "registros.csv")
    registro.guardar([dict(gtin="07795312020770", serie=s, usuario="Omar") for s in ("A1", "A2")])
    registro.marcar_revisados([("07795312020770", "A1")], "Claudia")
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.pills[0].set_value("Claudia").run()
    at.button(key="btn_archivar").click().run()
    assert not at.exception
    assert any("Archivados: 1 en" in s.value for s in at.success)
    assert registro.meses_archivados() and at.selectbox(key="mes_archivo").value

    registro.guardar([dict(gtin="07795312020770", serie="A3", usuario="Omar")])
    registro.marcar_revisados([("07795312020770", "A3")], "Claudia")
    at.run()
    at.button(key="eliminar_rev_0").click().run()
    at.button(key="eliminar_rev_1_no").click().run()  # cancelar en la primera pregunta: no borra
    assert len(registro.leer()) == 2
    at.button(key="eliminar_rev_0").click().run()
    at.button(key="eliminar_rev_1_si").click().run()
    assert len(registro.leer()) == 2  # todavía falta la segunda pregunta
    at.button(key="eliminar_rev_2_si").click().run()
    assert not at.exception
    assert list(registro.leer()["serie"]) == ["A2"]


def test_eliminar_mes_terminado_desde_la_pantalla(tmp_path, monkeypatch):
    from lector import registro

    monkeypatch.setattr(registro, "ARCHIVO", tmp_path / "registros.csv")
    registro.guardar([dict(gtin="07795312020770", serie="V", usuario="Omar", fecha_registro="15/10/2020 10:00:00")])
    registro.marcar_revisados([("07795312020770", "V")], "Claudia")
    registro.archivar_revisados()
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.pills[0].set_value("Claudia").run()
    assert any("octubre 2020" in i.value for i in at.info)
    at.button(key="eliminar_mes_2020-10_0").click().run()
    at.button(key="eliminar_mes_2020-10_1_si").click().run()
    at.button(key="eliminar_mes_2020-10_2_si").click().run()
    assert not at.exception and registro.meses_archivados() == []


def test_botones_de_foto_visibles_sin_nombre_y_pie_de_pagina():
    # Sin nombre elegido: los botones de foto ya se ven, y el pie de página también.
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert not at.pills[0].value  # nadie elegido todavía
    claves = [u.key for u in at.get("file_uploader")]
    assert any(k and k.startswith("camara") for k in claves)
    assert any(k and k.startswith("galeria") for k in claves)
    assert any("Omar Eduardo Giménez" in m.value for m in at.markdown)


def test_hay_ayuda_sin_ia():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("Ayuda" in e.label for e in at.expander)
