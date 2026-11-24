"""Médicos de la provincia: nombre, matrícula y si está en el convenio ISSPSE (consultas/Matriculas_Medicos.xlsx).

Sirve para verificar la matrícula de una receta. Se busca con "matricula 2911" o
"medico abalos" / "dr abalos". Se reemplaza subiendo el Excel nuevo con el mismo nombre.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .cajones import _parecido
from .consultas import normalizar

ARCHIVO = Path(__file__).resolve().parent.parent / "consultas" / "Matriculas_Medicos.xlsx"
DISPARADORES = ("matricula", "matriculas", "mat", "medico", "medica", "medicos", "dr", "dra", "doctor", "doctora")


@dataclass
class Medico:
    nombre: str
    matricula: str
    isspse: str = ""  # "Sí", "Probable" (el nombre coincide en parte) o ""


def leer(archivo: Path = ARCHIVO) -> list[Medico]:
    from openpyxl import load_workbook

    filas = list(load_workbook(archivo, read_only=True, data_only=True).worksheets[0].iter_rows(values_only=True))
    salida = []
    for f in filas[1:]:
        if f and f[0]:
            mat = str(f[1]).split(".")[0].strip() if len(f) > 1 and f[1] is not None else ""
            isspse = str(f[2]).strip() if len(f) > 2 and f[2] else ""
            salida.append(Medico(re.sub(r"\s+", " ", str(f[0])).strip(), mat, isspse))
    return salida


def es_consulta(pregunta: str) -> bool:
    palabras = re.findall(r"[a-z0-9]+", normalizar(pregunta))
    return bool(palabras) and palabras[0] in DISPARADORES and len(palabras) > 1


def buscar(medicos: list[Medico], pregunta: str, limite: int = 10) -> list[Medico]:
    palabras = [w for w in re.findall(r"[a-z0-9]+", normalizar(pregunta)) if w not in DISPARADORES]
    numeros = [w for w in palabras if w.isdigit()]
    if numeros:
        return [m for m in medicos if m.matricula.lstrip("0") in {n.lstrip("0") for n in numeros}][:limite]
    claves = [w for w in palabras if len(w) >= 2]
    if not claves:
        return []
    exactos = [m for m in medicos if all(w in normalizar(m.nombre) for w in claves)]
    if exactos:
        return exactos[:limite]
    return [m for m in medicos
            if all(max(_parecido(w, p) for p in re.findall(r"[a-z0-9]+", normalizar(m.nombre))) >= 0.85 for w in claves)][:limite]
