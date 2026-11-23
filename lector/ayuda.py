"""Ayuda de la app (preguntas frecuentes, sin IA).

Se responde desde el mismo buscador de Consultas ("Chatear con el ayudante").
"""

from __future__ import annotations

import re

from .consultas import normalizar, palabras

AYUDA = """
**📷 ¿Cómo cargo un envase?**
Tocá tu nombre arriba. Después tocá **Sacar foto** (abre la cámara) o **Galería** (elegís una foto que ya tenés). La app la lee sola, no hace falta tocar nada más.

**✅ ⚠️ ❌ ¿Qué significan?**
- **✅ Lista**: se leyó del cuadradito (DataMatrix) y es exacta. Se guarda sola.
- **⚠️ Revisar**: se leyó del texto impreso. Puede tener algún error, así que compará con el envase y tocá **Guardar**.
- **❌ Sacar otra foto**: no se pudo leer bien. Tocá **📷 Sacar de nuevo** (más de cerca y con buena luz) o **🗑️ Cancelar y eliminar** para quitarla sin guardar.

**📸 La foto no se lee, ¿qué hago?**
Sacá otra: un solo envase, de cerca, con buena luz, sin reflejos y **sin marcar ni tapar** el cuadradito.

**🔁 Me avisa que ya estaba cargado.**
Ese envase (mismo código y serie) ya se había registrado. Elegí **Reemplazar** (si querés dejar los datos nuevos) o **Descartar** (si dejás el anterior).

**👀 ¿Dónde veo lo cargado? (solo farmacéuticas)**
En **Registros** está lo que cargó el equipo y falta revisar. **Seleccionar todo** tilda todos, y **Pasar a Revisados** mueve los tildados a la pestaña **Revisados**.

**📦 Archivar por mes (Revisados)**
Guarda todos los revisados en un archivo de su mes y limpia la lista. No se pierde nada: cada mes se puede ver y bajar en **Excel** abajo, en **Meses archivados**.

**🗑️ Eliminar**
Borra para siempre y no se puede deshacer, por eso pregunta dos veces. Si querés conservar los datos, usá **Archivar por mes** en vez de eliminar. Bajá el Excel antes de borrar.

**⬇️ Descargar Excel**
En Registros y Revisados, el botón **Descargar Excel** baja la lista con el GTIN y la serie completos.
"""

# Palabras que se usan al preguntar por la app y no siempre están en el texto de la ayuda.
SINONIMOS = {
    "subir": "cargo", "cargar": "cargo", "escanear": "foto", "camara": "foto", "leer": "lee",
    "repetido": "cargado", "duplicado": "cargado", "borrar": "eliminar", "bajar": "descargar",
    "planilla": "excel", "revisar": "revisados", "error": "otra foto",
}


def preguntas() -> list[tuple[str, str]]:
    """[(pregunta, respuesta)] a partir del texto: cada pregunta es una línea en negrita."""
    salida, actual, cuerpo = [], None, []
    for linea in AYUDA.strip().splitlines():
        m = re.fullmatch(r"\*\*(.+)\*\*", linea.strip())
        if m:
            if actual:
                salida.append((actual, "\n".join(cuerpo).strip()))
            actual, cuerpo = m.group(1), []
        elif actual:
            cuerpo.append(linea)
    if actual:
        salida.append((actual, "\n".join(cuerpo).strip()))
    return salida


def buscar(pregunta: str) -> list[tuple[str, str]]:
    """Las preguntas frecuentes que tienen al menos la mitad de las palabras buscadas."""
    claves = [w for w in palabras(pregunta) if len(w) >= 3]
    claves = [SINONIMOS.get(w, w) for w in claves]
    if not claves:
        return []
    necesarias = max(1, (len(claves) + 1) // 2)
    puntajes = []
    for q, r in preguntas():
        donde = normalizar(q + " " + r)
        en_pregunta = sum(1 for w in claves if w in normalizar(q))
        total = sum(1 for w in claves if w in donde)
        if total >= necesarias:
            puntajes.append((-(en_pregunta * 2 + total), q, r))
    puntajes.sort()
    return [(q, r) for _, q, r in puntajes[:3]]
