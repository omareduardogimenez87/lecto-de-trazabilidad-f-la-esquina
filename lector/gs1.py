"""Interpretar los datos de trazabilidad (GTIN, serie, lote, vencimiento).

Hay dos fuentes posibles:

1. El DataMatrix (el cuadradito). Trae los datos en formato GS1, con
   "identificadores de aplicación" (AI) entre paréntesis:
       (01) GTIN   (21) serie   (10) lote   (17) vencimiento AAMMDD
   Esta fuente es exacta: si el DataMatrix se lee, los datos son correctos.

2. El texto impreso al lado, leído con OCR. Cada laboratorio lo imprime
   distinto ("LOT:", "L", "Lote/Batch:", "VEN:", "V", "Vto:", fechas
   MM/AAAA o DD/MM/AA, a veces sin ningún rótulo). Por eso acá hay
   reglas "heurísticas" (aproximadas) y el resultado siempre hay que revisarlo.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field, asdict

GS = "\x1d"  # separador de campos GS1 cuando el código viene "en crudo"

# Largo fijo de los AI que nos interesan (los de largo variable terminan en GS).
LARGO_FIJO = {"01": 14, "17": 6, "11": 6, "13": 6, "15": 6}


@dataclass
class Lectura:
    gtin: str = ""
    serie: str = ""
    lote: str = ""
    vencimiento: str = ""  # DD/MM/AAAA
    elaboracion: str = ""  # DD/MM/AAAA (si aparece)
    fuente: str = ""  # "DataMatrix" o "Texto (OCR)"
    avisos: list[str] = field(default_factory=list)

    @property
    def gtin_valido(self) -> bool:
        return gtin_es_valido(self.gtin)

    def como_dict(self) -> dict:
        d = asdict(self)
        d["gtin_valido"] = self.gtin_valido
        d["avisos"] = "; ".join(self.avisos)
        return d


# ---------------------------------------------------------------- GTIN

def digito_verificador(sin_dv: str) -> int:
    """Calcula el dígito verificador GS1 (el último número del GTIN)."""
    total = 0
    for i, c in enumerate(reversed(sin_dv)):
        total += int(c) * (3 if i % 2 == 0 else 1)
    return (10 - total % 10) % 10


def gtin_es_valido(gtin: str) -> bool:
    """True si el GTIN tiene 14 dígitos y el verificador cierra.

    Sirve para detectar errores de lectura: si el OCR confunde un 8 con
    un 9, la cuenta ya no da y lo marcamos para revisar.
    """
    if not re.fullmatch(r"\d{14}", gtin or ""):
        return False
    return digito_verificador(gtin[:-1]) == int(gtin[-1])


# ---------------------------------------------------------------- fechas

def _ultimo_dia(anio: int, mes: int) -> int:
    return calendar.monthrange(anio, mes)[1]


def _fecha(anio: int, mes: int, dia: int | None) -> str:
    """Arma DD/MM/AAAA. Si no hay día, usa el último día del mes."""
    if anio < 100:
        anio += 2000
    if not (1 <= mes <= 12) or not (2000 <= anio <= 2099):
        return ""
    if not dia:
        dia = _ultimo_dia(anio, mes)
    if dia > _ultimo_dia(anio, mes):
        return ""
    return f"{dia:02d}/{mes:02d}/{anio:04d}"


def fecha_gs1(aammdd: str) -> str:
    """Convierte la fecha GS1 AAMMDD. Día 00 = último día del mes."""
    if not re.fullmatch(r"\d{6}", aammdd):
        return ""
    aa, mm, dd = int(aammdd[:2]), int(aammdd[2:4]), int(aammdd[4:])
    return _fecha(aa, mm, dd or None)


RE_FECHA = re.compile(r"(?<!\d)(?:(\d{1,2})\s*[/.-]\s*)?(\d{1,2})\s*[/.-]\s*(\d{4}|\d{2})(?!\d)")


def fecha_texto(s: str) -> str:
    """Primera fecha que encuentre en el texto: DD/MM/AAAA, DD/MM/AA, MM/AAAA o MM/AA."""
    m = RE_FECHA.search(s)
    if not m:
        return ""
    dia, mes, anio = m.groups()
    return _fecha(int(anio), int(mes), int(dia) if dia else None)


def _clave_orden(fecha: str) -> tuple:
    d, m, a = fecha.split("/")
    return (int(a), int(m), int(d))


# ---------------------------------------------------------------- DataMatrix

def parsear_gs1(texto: str) -> Lectura:
    """Interpreta el contenido de un DataMatrix GS1.

    Acepta las dos formas en que lo entregan los lectores:
      "(01)07795312020770(21)11185T9C59E11T(17)280229(10)6F950A"
      "0107795312020770" + "21" + "11185T9C59E11T" + GS + "17280229..."
    """
    lec = Lectura(fuente="DataMatrix")
    datos: dict[str, str] = {}

    if "(" in texto:
        for ai, valor in re.findall(r"\((\d{2,4})\)([^(]*)", texto):
            datos[ai] = valor.strip()
    else:
        s = texto.lstrip("]d2").lstrip(GS)
        while len(s) >= 2:
            ai = s[:2]
            if ai in LARGO_FIJO:
                n = LARGO_FIJO[ai]
                datos[ai] = s[2 : 2 + n]
                s = s[2 + n :]
            elif ai in ("21", "10"):
                fin = s.find(GS, 2)
                fin = len(s) if fin == -1 else fin
                datos[ai] = s[2:fin]
                s = s[fin:]
            else:
                lec.avisos.append(f"Dato GS1 no reconocido: {s[:10]}…")
                break
            s = s.lstrip(GS)

    lec.gtin = datos.get("01", "")
    lec.serie = datos.get("21", "")
    lec.lote = datos.get("10", "")
    lec.vencimiento = fecha_gs1(datos.get("17", ""))
    lec.elaboracion = fecha_gs1(datos.get("11", ""))
    if lec.gtin and not lec.gtin_valido:
        lec.avisos.append("El GTIN no pasa el dígito verificador")
    return lec


# ---------------------------------------------------------------- Texto (OCR)

# Correcciones típicas del OCR dentro de números.
_A_DIGITO = str.maketrans({"O": "0", "o": "0", "D": "0", "Q": "0", "I": "1", "l": "1", "|": "1", "S": "5", "B": "8"})

RE_ROTULO_LOTE = re.compile(r"(?:\(10\)|\bLOTE?\b|\bBATCH\b|^L\b|\bL\s*[:.])", re.I)
RE_ROTULO_VTO = re.compile(r"(?:\(17\)|\bVEN\w*|\bVTO\b|\bVT0\b|\bV[I1]TO\b|\bCAD\w*|\bEXP\w*|^V\b)", re.I)
RE_ROTULO_ELAB = re.compile(r"(?:\(11\)|\bELAB\w*|\bFAB\w*|^E\b)", re.I)
RE_TOKEN = re.compile(r"[A-Z0-9]{4,}")


def _normalizar(linea: str) -> str:
    linea = linea.replace("<", "(").replace(">", ")").replace("{", "(").replace("}", ")")
    linea = re.sub(r"\(\s*(\d)\s*(\d)\s*\)", r"(\1\2)", linea)  # "( 0 1 )" -> "(01)"
    return linea.strip()


def _buscar_gtin(lineas: list[str]) -> tuple[str, int]:
    """Busca el GTIN. Devuelve (gtin, índice de línea) o ("", -1)."""
    candidatos: list[tuple[int, str, int]] = []  # (prioridad, gtin, linea)
    for i, linea in enumerate(lineas):
        # 1) Después de "(01)": junta dígitos, aunque sigan en la línea de abajo.
        m = re.search(r"\(?0[1l]\)\s*([0-9OoDIl|SB ]{6,})", linea)
        if m:
            digitos = re.sub(r"\D", "", m.group(1).translate(_A_DIGITO))
            if len(digitos) < 14 and i + 1 < len(lineas):
                siguiente = re.sub(r"\D", "", lineas[i + 1].translate(_A_DIGITO))
                if len(digitos) + len(siguiente) == 14:
                    digitos += siguiente
            if len(digitos) >= 14:
                g = digitos[:14]
                candidatos.append((0 if gtin_es_valido(g) else 2, g, i))
        # 2) Cualquier tira de 14 dígitos que cierre con el verificador.
        #    Se prefieren las que empiezan con 0: los GTIN de los medicamentos
        #    argentinos son 0 + el código de barras de 13 (ej. 0779...).
        for tira in re.findall(r"\d{14,17}", re.sub(r"[ ]", "", linea)):
            for k in range(len(tira) - 13):
                g = tira[k : k + 14]
                if gtin_es_valido(g):
                    candidatos.append((1 if g.startswith("0") else 3, g, i))
    if not candidatos:
        return "", -1
    candidatos.sort(key=lambda c: c[0])
    _, g, i = candidatos[0]
    return g, i


def parsear_texto(texto: str) -> Lectura:
    """Interpreta el texto impreso (leído con OCR). Siempre conviene revisarlo."""
    lec = Lectura(fuente="Texto (OCR)")
    lineas = [_normalizar(l) for l in texto.splitlines() if l.strip()]
    usadas: set[str] = set()

    # GTIN
    lec.gtin, linea_gtin = _buscar_gtin(lineas)
    if lec.gtin:
        usadas.add(lec.gtin)

    # Fechas con rótulo
    fechas_sueltas: list[str] = []
    for linea in lineas:
        f = fecha_texto(linea)
        if not f:
            continue
        if RE_ROTULO_VTO.search(linea) and not lec.vencimiento:
            lec.vencimiento = f
        elif RE_ROTULO_ELAB.search(linea) and not lec.elaboracion:
            lec.elaboracion = f
        else:
            fechas_sueltas.append(f)
        usadas.update(RE_TOKEN.findall(linea.upper()))
    # Fechas sin rótulo: la más lejana es el vencimiento, la más cercana la elaboración.
    if not lec.vencimiento and fechas_sueltas:
        fechas_sueltas.sort(key=_clave_orden)
        lec.vencimiento = fechas_sueltas.pop()
    if not lec.elaboracion and fechas_sueltas and _clave_orden(fechas_sueltas[0]) < _clave_orden(lec.vencimiento):
        lec.elaboracion = fechas_sueltas[0]

    # Serie: lo que sigue a "(21)"
    for linea in lineas:
        m = re.search(r"\(2[1l]\)\s*([A-Z0-9]{4,})", linea.upper())
        if m:
            lec.serie = m.group(1)
            break

    # Lote: lo que sigue a "LOT", "L", "Lote/Batch", "(10)"
    for linea in lineas:
        m = RE_ROTULO_LOTE.search(linea)
        if m and not fecha_texto(linea[m.end():]):
            resto = linea[m.end():].upper()
            t = RE_TOKEN.findall(resto)
            if t:
                lec.lote = t[0]
                break

    # Sin rótulos: tokens que quedan (ej. J&J o Novo Nordisk).
    sobrantes = []
    for i, linea in enumerate(lineas):
        if i == linea_gtin or fecha_texto(linea):
            continue
        for t in RE_TOKEN.findall(linea.upper()):
            if t in usadas or t == lec.serie or t == lec.lote:
                continue
            if not any(c.isdigit() for c in t):
                continue  # palabras sueltas como "GTIN", "LOTE"
            sobrantes.append(t)
    if not lec.serie and sobrantes:
        # El número de serie suele ser el dato más largo.
        lec.serie = max(sobrantes, key=len)
        sobrantes.remove(lec.serie)
    if not lec.lote and sobrantes:
        lec.lote = sobrantes[-1]

    # Avisos para revisar
    if not lec.gtin:
        lec.avisos.append("No se encontró el GTIN")
    elif not lec.gtin_valido:
        lec.avisos.append("El GTIN no pasa el dígito verificador: revisarlo")
    for campo in ("serie", "lote", "vencimiento"):
        if not getattr(lec, campo):
            lec.avisos.append(f"Falta {campo}")
    lec.avisos.append("Leído del texto: confirmar contra el envase")
    return lec


def combinar(lecturas: list[Lectura]) -> Lectura:
    """Junta varias lecturas OCR del mismo envase (normal e invertida),
    quedándose con el dato más confiable de cada campo."""
    if not lecturas:
        return Lectura()
    base = max(lecturas, key=lambda l: (l.gtin_valido, sum(bool(getattr(l, c)) for c in ("gtin", "serie", "lote", "vencimiento"))))
    resultado = Lectura(**{k: v for k, v in asdict(base).items() if k != "avisos"})
    for l in lecturas:
        for c in ("serie", "lote", "vencimiento", "elaboracion"):
            if not getattr(resultado, c) and getattr(l, c):
                setattr(resultado, c, getattr(l, c))
    resultado.avisos = []
    if not resultado.gtin:
        resultado.avisos.append("No se encontró el GTIN")
    elif not resultado.gtin_valido:
        resultado.avisos.append("El GTIN no pasa el dígito verificador: revisarlo")
    for campo in ("serie", "lote", "vencimiento"):
        if not getattr(resultado, campo):
            resultado.avisos.append(f"Falta {campo}")
    resultado.avisos.append("Leído del texto: confirmar contra el envase")
    return resultado
