"""Acción terapéutica por droga, solo desde un archivo con fuente verificable (nada generado).

Archivo: consultas/Accion_Terapeutica.csv con columnas droga;accion;fuente (indicacion es opcional).
Ej.: "propinox;Antiespasmódico;Alfabeta". Si una droga no está, la ficha dice "sin dato".
"""

from __future__ import annotations

import csv
from pathlib import Path

from .consultas import normalizar

ARCHIVO = Path(__file__).resolve().parent.parent / "consultas" / "Accion_Terapeutica.csv"
AVISO = "Dato de referencia del archivo cargado: no reemplaza la consulta con la farmacéutica y no indica dosis."


def leer(archivo: Path = ARCHIVO) -> dict[str, dict[str, str]]:
    if not archivo.exists():
        return {}
    with archivo.open(encoding="utf-8-sig", newline="") as f:
        muestra = f.read(4096)
        f.seek(0)
        filas = csv.DictReader(f, dialect=csv.Sniffer().sniff(muestra, delimiters=";,\t"))
        salida = {}
        for fila in filas:
            fila = {normalizar(k or "").strip(): (v or "").strip() for k, v in fila.items()}
            if fila.get("droga") and fila.get("accion"):
                salida[normalizar(fila["droga"])] = fila
        return salida


def de_la_droga(tabla: dict[str, dict[str, str]], droga: str) -> dict[str, str] | None:
    """Busca la droga tal cual figura en el vademécum ("diclofenac sódico"); no adivina."""
    return tabla.get(normalizar(droga.strip())) if droga else None
