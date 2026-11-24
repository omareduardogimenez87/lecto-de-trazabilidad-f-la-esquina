"""Ofertas OTC: lee consultas/Ofertas_OTC_completo.xlsx y busca productos.

El Excel se reemplaza subiéndolo con el mismo nombre (ver README). La app no
inventa precios: si la celda "Precio regular" está vacía dice "sin precio cargado".
Lo que paga el cliente se calcula igual que las fórmulas del Excel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .consultas import normalizar, palabras

ARCHIVO = Path(__file__).resolve().parent.parent / "consultas" / "Ofertas_OTC_completo.xlsx"
SIN_PRECIO = "sin precio cargado"
NO_CARGADO = "Producto no cargado."


@dataclass
class Oferta:
    id: str
    producto: str
    presentacion: str
    codigo: str
    laboratorio: str
    oferta: str
    descuento: float | None  # 0.4 = 40 %
    precio: float | None
    desde: date | None
    hasta: date | None
    nota: str
    precio_oferta: float | None = None  # precio final ya calculado (lista de precios de la quincena)

    def unidades(self) -> int:
        return {"2x1": 2, "3x2": 3}.get(self.oferta.lower(), 1)

    def paga_el_cliente(self) -> float | None:
        """Mismo cálculo que la columna "Paga el cliente" del Excel."""
        if self.precio_oferta is not None:
            return self.precio_oferta
        if self.precio is None:
            return None
        o, d = self.oferta.lower(), self.descuento or 0
        if o == "2x1":
            return self.precio
        if o == "3x2":
            return self.precio * 2
        if o == "2da unidad":
            return self.precio + self.precio * (1 - d)
        return self.precio * (1 - d)

    def texto_oferta(self) -> str:
        if self.oferta.lower() in ("2x1", "3x2"):
            return self.oferta
        if self.oferta.lower() == "2da unidad" and self.descuento:
            return f"{_pct(self.descuento)} en la 2da unidad"
        return f"{_pct(self.descuento)} de descuento" if self.descuento else (self.oferta or "—")

    def vigencia(self, hoy: date) -> str:
        if self.hasta and hoy > self.hasta:
            return "vencida"
        if self.desde and hoy < self.desde:
            return "todavía no empieza"
        return "vigente"


def _pct(valor: float | None) -> str:
    return f"{round(valor * 100):g} %" if valor is not None else ""


def pesos(valor: float) -> str:
    """$ 6.905,75 (formato argentino; sin centavos si es entero)."""
    entero = round(valor, 2)
    texto = f"{entero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "$ " + texto.removesuffix(",00")


def _a_fecha(valor) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", str(valor or ""))
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def _a_numero(valor) -> float | None:
    if valor is None or valor == "" or (isinstance(valor, str) and valor.startswith("=")):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).replace("$", "").replace("%", "").strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def solo_digitos(codigo) -> str:
    return re.sub(r"\D", "", str(codigo or ""))


def mismo_codigo(a: str, b: str) -> bool:
    """EAN-13 y GTIN-14 del mismo producto difieren solo en ceros a la izquierda."""
    a, b = solo_digitos(a).lstrip("0"), solo_digitos(b).lstrip("0")
    return bool(a) and a == b


def leer(archivo: Path = ARCHIVO) -> list[Oferta]:
    from openpyxl import load_workbook

    hoja = load_workbook(archivo, read_only=True, data_only=False).worksheets[0]
    filas = list(hoja.iter_rows(values_only=True))
    encabezado, inicio = None, 0
    for i, fila in enumerate(filas):
        nombres = [normalizar(str(c or "")).strip() for c in fila]
        if any("cod" in n and "barra" in n for n in nombres):
            encabezado, inicio = nombres, i + 1
            break
    if encabezado is None:
        return []

    def col(*claves):
        for j, n in enumerate(encabezado):
            if any(c in n for c in claves):
                return j
        return None

    c = {
        "id": col("id"), "producto": col("producto"), "presentacion": col("presentacion"),
        "codigo": col("barra"), "laboratorio": col("laboratorio"), "oferta": col("oferta"),
        "descuento": col("% desc", "desc"), "precio": col("precio regular"), "desde": col("desde"),
        "hasta": col("hasta"), "nota": col("nota"),
    }

    def dato(fila, clave):
        j = c[clave]
        return fila[j] if j is not None and j < len(fila) else None

    ofertas = []
    for fila in filas[inicio:]:
        codigo = solo_digitos(dato(fila, "codigo"))
        producto = str(dato(fila, "producto") or "").strip()
        if not codigo or not producto:
            continue
        descuento = _a_numero(dato(fila, "descuento"))
        if descuento is not None and descuento > 1:  # escrito como 40 en vez de 40 %
            descuento /= 100
        ofertas.append(Oferta(
            id=str(dato(fila, "id") or "").strip(),
            producto=producto,
            presentacion=str(dato(fila, "presentacion") or "").strip(),
            codigo=codigo,
            laboratorio=str(dato(fila, "laboratorio") or "").strip(),
            oferta=str(dato(fila, "oferta") or "").strip(),
            descuento=descuento,
            precio=_a_numero(dato(fila, "precio")),
            desde=_a_fecha(dato(fila, "desde")),
            hasta=_a_fecha(dato(fila, "hasta")),
            nota=str(dato(fila, "nota") or "").strip(),
        ))
    return ofertas


def por_codigo(ofertas: list[Oferta], codigo: str) -> list[Oferta]:
    return [o for o in ofertas if mismo_codigo(o.codigo, codigo)]


def buscar(ofertas: list[Oferta], pregunta: str, limite: int = 10) -> list[Oferta]:
    """Por código (si escribe números de 8 o más) o por palabras del producto/laboratorio."""
    numeros = [n for n in re.findall(r"\d{8,14}", pregunta)]
    if numeros:
        return [o for n in numeros for o in por_codigo(ofertas, n)][:limite]
    claves = [w for w in palabras(pregunta) if w not in ("oferta", "ofertas", "promo", "promos", "precio", "otc")]
    if not claves:
        return []
    return [
        o for o in ofertas
        if all(w in normalizar(f"{o.producto} {o.presentacion} {o.laboratorio} {o.id} {o.nota}") for w in claves)
    ][:limite]


def ficha(o: Oferta, hoy: date) -> str:
    """Texto en Markdown para mostrar una oferta."""
    lineas = [f"**{o.producto}** · {o.presentacion}".rstrip(" ·"),
              " · ".join(x for x in (o.laboratorio, f"Código {o.codigo}" if o.codigo else "") if x)]
    estado = o.vigencia(hoy)
    hasta = o.hasta.strftime("%d/%m/%Y") if o.hasta else "sin fecha"
    marca = {"vigente": "🏷️", "vencida": "❌", "todavía no empieza": "⏳"}[estado]
    lineas.append(f"{marca} **{o.texto_oferta()}** · hasta {hasta}" + ("" if estado == "vigente" else f" · **{estado}**"))
    if o.precio is None and o.precio_oferta is not None:
        lineas.append(f"💲 Precio oferta **{pesos(o.precio_oferta)}**")
    elif o.precio is None:
        lineas.append(f"💲 Precio: _{SIN_PRECIO}_")
    else:
        paga = o.paga_el_cliente()
        detalle = f"💲 Precio regular {pesos(o.precio)} → paga **{pesos(paga)}**"
        if o.unidades() > 1:
            detalle += f" llevando {o.unidades()} ({pesos(paga / o.unidades())} c/u)"
        lineas.append(detalle)
    if o.nota:
        lineas.append(f"📝 {o.nota}")
    return "  \n".join(l for l in lineas if l)
