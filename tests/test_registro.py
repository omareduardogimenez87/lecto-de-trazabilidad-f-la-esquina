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


class HojaFalsa:
    """Imita una hoja de Google Sheets (gspread) para probar sin internet."""

    def __init__(self):
        self.celdas = []

    def get_all_values(self):
        return [list(f) for f in self.celdas]

    def row_values(self, n):
        return list(self.celdas[n - 1]) if len(self.celdas) >= n else []

    def clear(self):
        self.celdas = []

    def update(self, valores, rango, value_input_option=None):
        assert rango == "A1"
        self.celdas[: len(valores)] = [list(v) for v in valores]

    def append_rows(self, filas, value_input_option=None):
        self.celdas.extend(list(f) for f in filas)


def test_planilla_de_google():
    hoja = HojaFalsa()
    registro.usar_planilla(hoja)
    try:
        assert registro.en_la_nube()
        registro.guardar([_fila(), _fila(serie="B")])
        assert hoja.celdas[0] == registro.COLUMNAS and len(hoja.celdas) == 3
        assert registro.ya_registrado("07795312020770", "B")
        assert registro.leer()["gtin"].iloc[0] == "07795312020770"  # no pierde el 0
        registro.reemplazar(_fila(lote="NUEVO", usuario="Yessi"))
        assert len(registro.leer()) == 2
        assert registro.buscar("07795312020770", "11185T9C59E11T")["lote"] == "NUEVO"
        assert registro.marcar_revisados([("07795312020770", "B")], "Fernanda") == 1
        assert registro.buscar("07795312020770", "B")["revisado_por"] == "Fernanda"
    finally:
        registro.usar_planilla(None)
    assert not registro.en_la_nube()


def test_excel_guarda_numeros_largos_como_texto():
    import io

    import openpyxl
    import pandas as pd

    df = pd.DataFrame({"GTIN": ["07795312020770"], "Serie": ["130925000000"]}, dtype=str)
    hoja = openpyxl.load_workbook(io.BytesIO(registro.a_excel(df))).active
    for celda in hoja[2]:
        assert celda.data_type == "s" and celda.number_format == "@"
    assert hoja["A2"].value == "07795312020770"


def test_rango_de_fechas():
    assert registro.rango_de_fechas(["27/11/2026 10:00:00", "22/11/2026 09:00:00"]) == "desde el domingo 22/11 al viernes 27/11"
    assert registro.rango_de_fechas(["22/11/2026 09:00:00", "22/11/2026 18:00:00"]) == "del domingo 22/11"
    assert registro.rango_de_fechas(["", "cualquier cosa"]) == ""


def test_excel_con_titulo():
    import io

    import openpyxl
    import pandas as pd

    df = pd.DataFrame({"GTIN": ["07795312020770"], "Serie": ["A1"]}, dtype=str)
    hoja = openpyxl.load_workbook(io.BytesIO(registro.a_excel(df, "Listado de revisados del domingo 22/11"))).active
    assert hoja["A1"].value == "Listado de revisados del domingo 22/11"
    assert hoja["A1"].font.size == 16 and hoja["A1"].fill.fgColor.rgb.endswith("8B5A9E")
    assert hoja["A3"].value == "GTIN" and hoja["A4"].value == "07795312020770" and hoja["A4"].number_format == "@"
