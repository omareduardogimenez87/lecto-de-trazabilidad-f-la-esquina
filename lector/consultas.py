"""Consultas rápidas del mostrador (sin IA).

Lee el archivo consultas/Base_Consultas_Mostrador_Mitre.md y responde buscando
palabras en él. No inventa nada: solo muestra lo que está escrito en el archivo,
y sigue sus reglas (sección 0):

- ⚠️ se responde agregando "a confirmar con Germán o la farmacéutica".
- Si no hay dato: "No tengo ese dato cargado...".
- Consultas de salud (dosis, para qué sirve, etc.) van a la farmacéutica.
- Promos: si la fecha "Hasta" ya pasó, se marca "vencida".
- Horarios: solo vale el período cargado en la sección 2.1.

Para actualizar el horario cada viernes se reemplaza el archivo .md (ver README).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

ARCHIVO = Path(__file__).resolve().parent.parent / "consultas" / "Base_Consultas_Mostrador_Mitre.md"

A_CONFIRMAR = "a confirmar con Germán o la farmacéutica"
SIN_DATO = "No tengo ese dato cargado. Consultá con Germán (ROC) o la farmacéutica."
SIN_HORARIO = "Todavía no está cargado el horario de esa fecha."
SALUD = (
    "Eso lo responde la farmacéutica (Claudia Spinnato o Fernanda Caro). "
    "La app no da dosis, indicaciones ni consejos de salud."
)

# Palabras que indican una consulta de salud de un paciente (regla 3).
PALABRAS_SALUD = (
    "dosis", "cuanto tomar", "cuantas veces", "cada cuanto", "para que sirve", "sirve para",
    "efecto", "contraindic", "embaraz", "lactancia", "amamant", "puedo tomar", "se puede tomar",
    "como se toma", "como tomar", "como se usa", "como usar", "indicacion", "mezclar con",
    "alcohol", "alergia a", "dolor de", "me duele", "le duele", "sintoma", "fiebre", "presion alta",
)

# Secciones que no son para consultar (reglas internas y registro de cambios).
SECCIONES_OCULTAS = ("0", "11")

# Íconos para los botones de categoría, según el número de sección.
ICONOS = {"1": "🏥", "2": "🕒", "3": "🏬", "4": "💳", "5": "🧪", "6": "💉", "7": "🏷️", "8": "⌨️", "9": "🛒", "10": "❓"}

# Nombres cortos para los botones (si una sección nueva no está acá, se usa su título).
CORTOS = {"1": "Sucursal Mitre", "2": "Horarios", "3": "Sucursales", "4": "Obras sociales", "5": "Programas",
          "6": "PICC Elea", "7": "Promos", "8": "Mostrador", "9": "Venta online", "10": "Pendientes"}

# Palabras vacías que no sirven para buscar.
VACIAS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a", "en", "y", "o", "que",
    "se", "es", "por", "para", "con", "como", "cual", "cuales", "donde", "quien", "quienes", "hay", "me",
    "mi", "tu", "su", "lo", "le", "si", "no", "esta", "estan", "son", "va", "van", "trabaja", "trabajan",
    "trabajamos", "tiene", "tienen", "sabes", "saber", "dato", "datos", "cuanto", "cuando", "que",
}


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para buscar sin importar cómo se escriba."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return sin_tildes.lower()


def _limpiar(texto: str) -> str:
    """Saca la marca de negrita y espacios de más (para comparar)."""
    return re.sub(r"\s+", " ", texto.replace("**", "")).strip()


@dataclass
class Dato:
    """Un renglón que se puede encontrar: una fila de tabla o un punto de lista."""

    seccion: str  # número de la sección principal ("4")
    titulo: str  # "4.1 ¿Se trabaja en la Mitre?" o el título de la sección
    texto: str  # lo que se muestra (Markdown)
    es_horario: bool = False


@dataclass
class Seccion:
    numero: str
    titulo: str
    contenido: str
    datos: list[Dato] = field(default_factory=list)

    @property
    def etiqueta(self) -> str:
        if self.numero in CORTOS:
            return f"{ICONOS[self.numero]} {CORTOS[self.numero]}"
        nombre = re.sub(r"\s*\(.*?\)", "", self.titulo).replace("✅", "").replace("⚠️", "")
        nombre = nombre.split("·")[0].split(":")[0].strip()
        return f"{ICONOS.get(self.numero, '📌')} {nombre}"


@dataclass
class Base:
    secciones: list[Seccion]
    periodo: tuple[date, date] | None
    tabla_horario: tuple[list[str], list[list[str]]] | None  # encabezados y filas de 2.1

    @property
    def datos(self) -> list[Dato]:
        return [d for s in self.secciones for d in s.datos]


# ------------------------------------------------------------ leer el archivo

def _celdas(linea: str) -> list[str]:
    return [c.strip() for c in linea.strip().strip("|").split("|")]


def _es_separador(linea: str) -> bool:
    return bool(re.fullmatch(r"\|?[\s:\-|]+\|?", linea.strip())) and "-" in linea


def _fecha(texto: str) -> date | None:
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", texto)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _datos_de(numero: str, titulo_seccion: str, contenido: str) -> tuple[list[Dato], list | None]:
    """Parte el contenido de una sección en renglones buscables."""
    datos: list[Dato] = []
    sub = titulo_seccion
    encabezado: list[str] | None = None
    tabla_horario = None
    lineas = contenido.splitlines()
    for i, linea in enumerate(lineas):
        s = linea.strip()
        if s.startswith("### "):
            sub = s[4:].strip()
            encabezado = None
            continue
        if s.startswith("|"):
            siguiente = lineas[i + 1].strip() if i + 1 < len(lineas) else ""
            if encabezado is None and _es_separador(siguiente):
                encabezado = _celdas(s)
                if sub.startswith("2.1"):
                    tabla_horario = (encabezado, [])
                continue
            if _es_separador(s):
                continue
            celdas = _celdas(s)
            if encabezado and len(celdas) == len(encabezado):
                partes = [f"**{h}:** {c}" for h, c in zip(encabezado, celdas) if c and c != "—"]
                texto = " · ".join(partes)
            else:
                texto = " · ".join(c for c in celdas if c)
            es_horario = sub.startswith("2.1")
            if es_horario and tabla_horario is not None:
                tabla_horario[1].append(celdas)
            datos.append(Dato(numero, sub, texto, es_horario=es_horario))
            continue
        encabezado = None
        if not s or s == "---" or s.startswith("#"):
            continue
        texto = re.sub(r"^(?:[-*]|\d+\.)\s+", "", s).lstrip("> ").strip()
        if texto:
            datos.append(Dato(numero, sub, texto, es_horario=sub.startswith("2.1")))
    return datos, tabla_horario


def leer(archivo: Path = ARCHIVO) -> Base:
    texto = archivo.read_text(encoding="utf-8")
    texto = re.sub(r"\A---\n.*?\n---\n", "", texto, flags=re.S)  # saca el encabezado del archivo
    partes = re.split(r"^## ", texto, flags=re.M)[1:]
    secciones: list[Seccion] = []
    periodo = None
    tabla_horario = None
    for parte in partes:
        titulo, _, contenido = parte.partition("\n")
        m = re.match(r"(\d+)\.\s*(.*)", titulo.strip())
        numero, nombre = (m.group(1), m.group(2)) if m else ("", titulo.strip())
        datos, tabla = _datos_de(numero, nombre, contenido)
        if tabla:
            tabla_horario = tabla
        if numero == "2":
            mp = re.search(r"Per[ií]odo:\**\s*(.+)", contenido)
            if mp:
                fechas = re.findall(r"\d{1,2}/\d{1,2}/\d{4}", mp.group(1))
                if len(fechas) >= 2:
                    periodo = (_fecha(fechas[0]), _fecha(fechas[1]))
        if numero in SECCIONES_OCULTAS:
            continue
        secciones.append(Seccion(numero, nombre, contenido.strip().rstrip("-").strip(), datos))
    return Base(secciones, periodo, tabla_horario)


# ------------------------------------------------------------ reglas

def horario_vigente(base: Base, dia: date) -> bool:
    return bool(base.periodo) and base.periodo[0] <= dia <= base.periodo[1]


def columna_del_dia(base: Base, dia: date) -> int | None:
    """Índice de la columna de la tabla de horarios que corresponde a ese día."""
    if not base.tabla_horario or not horario_vigente(base, dia):
        return None
    for i, h in enumerate(base.tabla_horario[0]):
        m = re.search(r"\b(\d{1,2})\b", h)
        if i >= 2 and m and int(m.group(1)) == dia.day:
            return i
    return None


def quien_trabaja(base: Base, dia: date) -> tuple[str, list[tuple[str, str, str]]] | None:
    """(título de la columna, [(persona, puesto, horario)]) o None si ese día no está cargado."""
    col = columna_del_dia(base, dia)
    if col is None:
        return None
    encabezado, filas = base.tabla_horario
    gente = []
    for f in filas:
        if len(f) > col and f[col] and f[col] != "—":
            gente.append((f[0], f[1], f[col]))
    return encabezado[col], gente


def marcar_promos(contenido: str, hoy: date) -> str:
    """En las tablas con columna "Hasta", marca como vencidas las promos cuya fecha ya pasó."""
    salida = []
    encabezado = None
    for linea in contenido.splitlines():
        s = linea.strip()
        if s.startswith("|") and not _es_separador(s):
            celdas = _celdas(s)
            if encabezado is None:
                encabezado = celdas
            elif "Hasta" in encabezado and len(celdas) == len(encabezado):
                i = encabezado.index("Hasta")
                hasta = _fecha(celdas[i])
                if hasta and hasta < hoy:
                    celdas[i] = f"{celdas[i]} ❌ **vencida**"
                    if "Estado" in encabezado:
                        celdas[encabezado.index("Estado")] = "❌ vencida"
                    linea = "| " + " | ".join(celdas) + " |"
        elif not s.startswith("|"):
            encabezado = None
        salida.append(linea)
    return "\n".join(salida)


def _promo_vencida(dato: Dato, hoy: date) -> bool:
    m = re.search(r"\*\*Hasta:\*\*\s*([^·]+)", dato.texto)
    hasta = _fecha(m.group(1)) if m else None
    return bool(hasta and hasta < hoy)


PALABRAS_COBERTURA = ("cobertura", "coberturas", "cubre", "cubren", "cobertu", "cober")
# Palabras que eligen una sola fuente de cobertura: "clinal cobertura vale" -> solo Vale Salud.
FUENTES_COBERTURA = {
    "vale": ("vale", "valesalud", "vale+"),
    "pami": ("pami", "alfabeta"),
    "osdop": ("osdop",),
}
_DESCARTAR = ("de", "del", "la", "el", "en", "salud", "para")


def medicamento_de_cobertura(pregunta: str, fuentes_q: dict | None = None) -> tuple[str, list[str]] | None:
    """"clinal cobertura vale salud" -> ("clinal", ["vale"]). Sin fuente nombrada -> todas.

    None si no pregunta por cobertura.
    """
    todas = {**FUENTES_COBERTURA, **(fuentes_q or {})}
    palabras_q = pregunta.split()
    if not any(normalizar(w).startswith(PALABRAS_COBERTURA) for w in palabras_q):
        return None
    fuentes, resto = [], []
    for w in palabras_q:
        n = normalizar(w)
        fuente = next((f for f, claves in todas.items() if n in claves), None)
        if fuente:
            fuentes.append(fuente)
        elif not n.startswith(PALABRAS_COBERTURA) and n not in _DESCARTAR:
            resto.append(w)
    medicamento = " ".join(resto).strip()
    if not medicamento:
        return None
    return medicamento, (sorted(set(fuentes), key=list(todas).index) or list(todas))


def es_consulta_de_salud(pregunta: str) -> bool:
    p = normalizar(pregunta)
    return any(palabra in p for palabra in PALABRAS_SALUD)


def con_aviso(dato: Dato, hoy: date) -> str:
    """El texto del dato con los avisos que piden las reglas (⚠️ y promos vencidas)."""
    texto = dato.texto
    if dato.seccion == "7" and _promo_vencida(dato, hoy):
        texto += " · ❌ **vencida**"
    if "⚠️" in texto:
        texto += f" _({A_CONFIRMAR})_"
    return texto


def palabras(pregunta: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9+]+", normalizar(pregunta)) if w not in VACIAS and len(w) > 1]


def buscar(base: Base, pregunta: str, hoy: date, limite: int = 12) -> dict:
    """Busca la pregunta en la base. Devuelve un diccionario para mostrar en la app:

    - "salud": True si es una consulta de salud (se deriva a la farmacéutica).
    - "hoy": (columna, gente) si preguntó quién trabaja hoy.
    - "sin_horario": True si preguntó por horarios y no hay horario cargado para hoy.
    - "datos": [(título, texto)] con los renglones encontrados.
    """
    resultado = {"salud": False, "hoy": None, "sin_horario": False, "datos": []}
    if es_consulta_de_salud(pregunta):
        resultado["salud"] = True
        return resultado
    p = normalizar(pregunta)
    claves = palabras(pregunta)
    pide_horario = any(w in p for w in ("horario", "turno", "trabaja", "hoy", "franco", "quien esta"))
    vigente = horario_vigente(base, hoy)
    if pide_horario and "atencion" not in p and "abre" not in p and "cierra" not in p:
        if vigente:
            resultado["hoy"] = quien_trabaja(base, hoy)
        else:
            resultado["sin_horario"] = True
    claves = [w for w in claves if w not in ("hoy", "horario", "horarios", "turno", "turnos")]
    if not claves:
        return resultado
    puntajes = []
    for d in base.datos:
        if d.es_horario and not vigente:
            continue
        donde = normalizar(d.titulo + " " + d.texto)
        encontradas = sum(1 for w in claves if w in donde)
        if encontradas == len(claves):
            # Primero lo que tiene la palabra en el texto, y lo más corto (más directo).
            en_texto = sum(1 for w in claves if w in normalizar(d.texto))
            puntajes.append((-en_texto, len(d.texto), d))
    puntajes.sort(key=lambda x: (x[0], x[1]))
    resultado["datos"] = [(d.titulo, con_aviso(d, hoy)) for _, _, d in puntajes[:limite]]
    if not vigente:
        # ¿Preguntó por alguien del horario? Si el horario no está vigente, avisarlo.
        if any(all(w in normalizar(d.texto) for w in claves) for d in base.datos if d.es_horario):
            resultado["sin_horario"] = True
    return resultado


def hoy_argentina() -> date:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    except Exception:  # pragma: no cover
        return date.today()
