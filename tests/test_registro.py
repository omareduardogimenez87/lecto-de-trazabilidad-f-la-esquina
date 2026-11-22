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
