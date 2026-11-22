"""Pruebas del archivo de registros, usando una carpeta temporal."""

from lector import registro


def _fila(**extra):
    base = dict(gtin="07795312020770", serie="11185T9C59E11T", lote="6F950A", vencimiento="29/02/2028", usuario="Omar")
    base.update(extra)
    return base


def test_guardar_buscar_y_reemplazar(tmp_path):
    archivo = tmp_path / "registros.csv"
    registro.guardar([_fila(), _fila(serie="OTRA")], archivo)
    previo = registro.buscar("07795312020770", "11185T9C59E11T", archivo)
    assert previo["usuario"] == "Omar" and previo["lote"] == "6F950A"
    assert registro.buscar("07795312020770", "NO-EXISTE", archivo) is None

    registro.reemplazar(_fila(lote="NUEVO", usuario="Yessi"), archivo)
    df = registro.leer(archivo)
    assert len(df) == 2  # no se duplicó
    fila = registro.buscar("07795312020770", "11185T9C59E11T", archivo)
    assert (fila["lote"], fila["usuario"]) == ("NUEVO", "Yessi")
    assert registro.buscar("07795312020770", "OTRA", archivo) is not None


def test_revision_por_farmaceutica(tmp_path):
    archivo = tmp_path / "registros.csv"
    registro.guardar([_fila(), _fila(serie="B")], archivo)
    assert registro.marcar_revisados([("07795312020770", "B")], "Claudia", archivo) == 1
    df = registro.leer(archivo)
    revisado = df[df["serie"] == "B"].iloc[0]
    assert revisado["revisado_por"] == "Claudia" and revisado["revisado_el"]
    assert df[df["serie"] == "11185T9C59E11T"].iloc[0]["revisado_por"] == ""
    registro.desmarcar_revisado("07795312020770", "B", archivo)
    assert (registro.leer(archivo)["revisado_por"] == "").all()


def test_archivo_de_version_anterior(tmp_path):
    archivo = tmp_path / "registros.csv"
    viejas = [c for c in registro.COLUMNAS if not c.startswith("revisado")]
    archivo.write_text(";".join(viejas) + "\n" + ";".join("x" for _ in viejas) + "\n", encoding="utf-8-sig")
    registro.guardar([_fila()], archivo)
    df = registro.leer(archivo)
    assert len(df) == 2 and list(df.columns) == registro.COLUMNAS
