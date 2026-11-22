"""¿La foto sirve? Detectar fotos desenfocadas o con lecturas dudosas.

La idea: si la app no está segura de haber leído bien, pide otra foto
en lugar de guardar un dato que puede estar mal.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from .gs1 import Lectura

# Nitidez mínima. Se calibró con las 8 fotos de muestra (22/11/2026): las fotos
# nítidas dieron entre 190 y 2000, y las mismas fotos desenfocadas a propósito
# dieron menos de 15. Si pide otra foto demasiado seguido, bajar este número.
NITIDEZ_MINIMA = 80

ESTADO_OK = "✅ Lista"
ESTADO_REVISAR = "⚠️ Revisar"
ESTADO_OTRA_FOTO = "❌ Sacar otra foto"


@dataclass
class Calidad:
    nitidez: float
    brillo: float
    problemas: list[str] = field(default_factory=list)

    @property
    def desenfocada(self) -> bool:
        return self.nitidez < NITIDEZ_MINIMA


def _laplaciano(g: np.ndarray) -> float:
    """Mide cuántos bordes marcados hay. Foto movida o fuera de foco = pocos bordes."""
    g = g.astype(float)
    lap = g[1:-1, :-2] + g[1:-1, 2:] + g[:-2, 1:-1] + g[2:, 1:-1] - 4 * g[1:-1, 1:-1]
    return float(lap.var())


def medir(img: Image.Image) -> Calidad:
    """Mide la nitidez de la zona más nítida de la foto (donde suele estar el código;
    el fondo de las fotos de mostrador casi siempre está borroso, y eso está bien)."""
    gris = img.convert("L")
    gris = gris.resize((1000, max(1, int(1000 * gris.height / gris.width))))
    g = np.asarray(gris)
    alto, ancho = g.shape
    t = 200
    nitidez = max(
        (_laplaciano(g[y : y + t, x : x + t]) for y in range(0, max(1, alto - t), 100) for x in range(0, max(1, ancho - t), 100)),
        default=_laplaciano(g),
    )
    c = Calidad(nitidez=round(nitidez, 1), brillo=round(float(g.mean()), 1))
    if c.desenfocada:
        c.problemas.append("La foto está desenfocada o movida")
    if c.brillo < 50:
        c.problemas.append("La foto está muy oscura")
    elif c.brillo > 235:
        c.problemas.append("La foto está muy clara o con reflejo")
    return c


def estado(lectura: Lectura, calidad: Calidad) -> tuple[str, list[str]]:
    """Decide qué hacer con la lectura: guardarla, revisarla o pedir otra foto."""
    motivos = list(calidad.problemas)
    if lectura.fuente == "DataMatrix" and lectura.gtin_valido and lectura.serie:
        return ESTADO_OK, []  # el DataMatrix es exacto, aunque la foto no sea perfecta
    if not lectura.gtin:
        motivos.append("No se pudo leer el GTIN")
    elif not lectura.gtin_valido:
        motivos.append("El GTIN leído no cierra (dígito verificador)")
    if not lectura.serie:
        motivos.append("No se pudo leer el número de serie")
    if motivos:
        return ESTADO_OTRA_FOTO, motivos
    return ESTADO_REVISAR, ["Leído del texto impreso: compará con la foto antes de guardar"]
