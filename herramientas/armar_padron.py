"""Arma consultas/padron_osdop.json con los Excel de OSDOP del mes (sin datos personales).

Uso:  python herramientas/armar_padron.py CLAVE osdop.xlsx osdop_monotrib.xlsx cob_especiales.xlsx MES
Guarda solo un código de cada DNI (ver lector/padron.py). Los Excel NO se suben al repo.
"""

import json
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lector.padron import ARCHIVO, codigo  # noqa: E402


def filas(ruta):
    hoja = load_workbook(ruta, read_only=True, data_only=True).worksheets[0]
    todas = list(hoja.iter_rows(values_only=True))
    enc = [str(c or "").split(",")[0].strip().upper() for c in todas[0]]
    return [dict(zip(enc, f)) for f in todas[1:]]


def main(clave, osdop, monotrib, especiales, mes):
    nro_a_dni, listas = {}, {}
    for nombre, ruta in (("OSDOP", osdop), ("OSDOP Monotributo", monotrib)):
        cods = set()
        for f in filas(ruta):
            if f.get("DOC"):
                dni = str(int(f["DOC"]))
                nro_a_dni[str(f.get("NROSDOP") or "").split(".")[0]] = dni
                cods.add(codigo(dni, clave))
        listas[nombre] = sorted(cods)
    especial = set()
    for f in filas(especiales):
        dni = nro_a_dni.get(str(f.get("NROSDOP") or "").split(".")[0])
        if dni:
            especial.add(codigo(dni, clave))
    listas["Cobertura especial"] = sorted(especial)
    ARCHIVO.write_text(json.dumps({"mes": mes, "listas": listas}, ensure_ascii=False), encoding="utf-8")
    print({k: len(v) for k, v in listas.items()})


if __name__ == "__main__":
    main(*sys.argv[1:6])
