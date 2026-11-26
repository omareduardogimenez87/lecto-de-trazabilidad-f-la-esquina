"""Acción terapéutica por droga, solo desde un archivo con fuente verificable (nada generado).

Archivo: consultas/Accion_Terapeutica.csv con columnas sku;droga;accion;indicacion;fuente
(sku o droga, al menos uno; indicacion es opcional). El texto se copia tal cual de la fuente.
Ej.: "0000044525;;Antinflamatorio y Analgésico;...;farmacialaesquina.com.ar". Si no está, "sin dato".
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
        filas = csv.DictReader(f, delimiter=";")  # textos con ";" van entre comillas
        salida = {}
        for fila in filas:
            fila = {normalizar(k or "").strip(): (v or "").strip() for k, v in fila.items()}
            if not fila.get("accion"):
                continue
            if fila.get("droga"):
                salida[normalizar(fila["droga"])] = fila
            if fila.get("sku"):
                salida["sku:" + fila["sku"].lstrip("0")] = fila
        return salida


def de_la_droga(tabla: dict[str, dict[str, str]], droga: str) -> dict[str, str] | None:
    """Busca la droga tal cual figura en el vademécum ("diclofenac sódico"); no adivina."""
    return tabla.get(normalizar(droga.strip())) if droga else None


def del_sku(tabla: dict[str, dict[str, str]], sku: str) -> dict[str, str] | None:
    """Por el código interno del catálogo (el mismo SKU que usa la página de La Esquina)."""
    return tabla.get("sku:" + sku.lstrip("0")) if sku else None


def texto(dato: dict[str, str]) -> str:
    salida = f"💡 Acción terapéutica: **{dato['accion']}**"
    if dato.get("indicacion"):
        salida += f" · Indicado para: {dato['indicacion']}"
    return salida + (f" _(fuente: {dato['fuente']})_" if dato.get("fuente") else "")
