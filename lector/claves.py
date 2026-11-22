"""PIN de las farmacéuticas para entrar a Registros.

Elegir un nombre no protege nada (cualquiera puede tocar "Fernanda"), así que
para ver y revisar los registros cada farmacéutica usa un PIN propio.

- La primera vez que entra, la app le pide que cree su PIN.
- El PIN no se guarda tal cual: se guarda una "huella" (hash) que no se puede
  volver atrás, en registros/claves.json (en la PC, nunca se sube a GitHub).
- Si una se olvida el PIN: borrar registros/claves.json y cada una crea uno nuevo.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path

from .registro import CARPETA

ARCHIVO_CLAVES = CARPETA / "claves.json"


def _leer(archivo: Path) -> dict:
    if not archivo.exists():
        return {}
    return json.loads(archivo.read_text(encoding="utf-8"))


def _huella(pin: str, sal: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), sal, 200_000).hex()


def pin_valido(pin: str) -> bool:
    """El PIN tiene que ser de 4 a 6 números."""
    return pin.isdigit() and 4 <= len(pin) <= 6


def tiene_pin(nombre: str, archivo: Path = ARCHIVO_CLAVES) -> bool:
    return nombre in _leer(archivo)


def crear_pin(nombre: str, pin: str, archivo: Path = ARCHIVO_CLAVES) -> None:
    if not pin_valido(pin):
        raise ValueError("El PIN tiene que ser de 4 a 6 números")
    claves = _leer(archivo)
    sal = os.urandom(16)
    claves[nombre] = {"sal": sal.hex(), "huella": _huella(pin, sal)}
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps(claves, indent=2), encoding="utf-8")


def verificar(nombre: str, pin: str, archivo: Path = ARCHIVO_CLAVES) -> bool:
    dato = _leer(archivo).get(nombre)
    if not dato:
        return False
    return hmac.compare_digest(_huella(pin, bytes.fromhex(dato["sal"])), dato["huella"])
